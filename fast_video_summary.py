import os
import cv2
import time
import json
import re
import ffmpeg
import subprocess
from concurrent.futures import ThreadPoolExecutor
from faster_whisper import WhisperModel
from openai import OpenAI
from dotenv import load_dotenv

# 尝试自动配置 ffmpeg 路径
try:
    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg_exe)
except ImportError:
    pass

# 加载环境变量
load_dotenv()

# 设置 HF 镜像，解决国内网络连接问题
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# ================= 配置区域 =================
VIDEO_PATH = os.getenv("VIDEO_PATH", "input.mp4")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1")

# ASR 设置
MODEL_SIZE = os.getenv("MODEL_SIZE", "medium")    # 追求速度可用 "small"，追求质量用 "medium", "large-v3"
DEVICE = os.getenv("DEVICE", "cuda")              # 必须用 cuda 才能快
DEFAULT_COMPUTE_TYPE = "int8_float16" if DEVICE == "cuda" else "int8"
COMPUTE_TYPE = os.getenv("COMPUTE_TYPE", DEFAULT_COMPUTE_TYPE)

# LLM 设置
LLM_MODEL = os.getenv("LLM_MODEL", "zai-org/GLM-4.6")

# 截图优化设置
CAPTURE_OFFSET = float(os.getenv("CAPTURE_OFFSET", "5.0"))  # 默认向后偏移 5 秒
# ===========================================

# 全局模型缓存，避免重复加载
_MODEL_CACHE = {}

class FastVideoAnalyzer:
    def __init__(self, video_path, output_dir, config=None, progress_callback=None, selected_images=None):
        self.video_path = video_path
        self.output_dir = output_dir
        self.progress_callback = progress_callback
        self.selected_images = selected_images or []
        
        # 尝试从数据库加载最新配置
        db_config = {}
        try:
            from leader_api.mysql_store import load_app_config
            db_config = load_app_config() or {}
        except ImportError:
            pass # 可能不在 leader_api 环境下运行
        except Exception as e:
            print(f">>> [Warning] Load DB config failed: {e}")

        # 辅助函数：优先级 config > db_config > env > default
        def get_conf(key, env_key, default):
            # 1. Check passed config
            if config and config.get(key) is not None:
                return config[key]
            # 2. Check DB config (lowercase keys usually)
            if db_config.get(key) is not None:
                return db_config[key]
            # 3. Check Env
            val = os.getenv(env_key)
            if val is not None:
                return val
            # 4. Default
            return default

        # 解析配置
        self.config = {
            "openai_api_key": get_conf("openai_api_key", "OPENAI_API_KEY", OPENAI_API_KEY),
            "openai_base_url": get_conf("openai_base_url", "OPENAI_BASE_URL", OPENAI_BASE_URL),
            "llm_model": get_conf("llm_model", "LLM_MODEL", LLM_MODEL),
            "model_size": get_conf("model_size", "MODEL_SIZE", MODEL_SIZE),
            "device": get_conf("device", "DEVICE", DEVICE),
            "compute_type": get_conf("compute_type", "COMPUTE_TYPE", COMPUTE_TYPE),
            "capture_offset": float(get_conf("capture_offset", "CAPTURE_OFFSET", CAPTURE_OFFSET)),
            
            # Additional DB configs (optional)
            "ocr_engine": get_conf("ocr_engine", "OCR_ENGINE", "vl"),
            "vl_model": get_conf("vl_model", "VL_MODEL", "Pro/Qwen/Qwen2-VL-7B-Instruct"),
            "vl_base_url": get_conf("vl_base_url", "VL_BASE_URL", "https://api.siliconflow.cn/v1"),
            "vl_api_key": get_conf("vl_api_key", "VL_API_KEY", ""),
        }
        
        # 如果传入了自定义配置，则覆盖默认值 (Legacy logic, kept for compatibility but redundant with get_conf)
        if config:
            for k, v in config.items():
                if v is not None and str(v).strip():
                    self.config[k] = v
            
        # 检查本地是否有预下载的 Whisper 模型
        local_whisper_path = os.path.join(os.getcwd(), "model", "whisper")
        if self.config["model_size"] == "medium" and os.path.exists(os.path.join(local_whisper_path, "model.bin")):
            print(f">>> 检测到本地预下载模型: {local_whisper_path}")
            self.config["model_size"] = local_whisper_path

        self.client = OpenAI(
            api_key=self.config["openai_api_key"], 
            base_url=self.config["openai_base_url"]
        )
        
        # DEBUG LOG
        key = self.config["openai_api_key"]
        masked = f"{key[:8]}...{key[-4:]}" if key and len(key) > 12 else "EMPTY"
        print(f">>> FastVideoAnalyzer Config: Key={masked}, BaseURL={self.config['openai_base_url']}, Model={self.config['llm_model']}")
        
        os.makedirs(self.output_dir, exist_ok=True)
        self.img_dir = os.path.join(self.output_dir, "images")
        os.makedirs(self.img_dir, exist_ok=True)

    def get_model(self):
        """
        单例模式获取 ASR 模型
        """
        m_key = f"{self.config['model_size']}_{self.config['device']}_{self.config['compute_type']}"
        if m_key not in _MODEL_CACHE:
            self.log(f">>> 正在初始化 Whisper 模型 ({m_key})...")
            _MODEL_CACHE[m_key] = WhisperModel(
                self.config['model_size'], 
                device=self.config['device'], 
                compute_type=self.config['compute_type']
            )
        return _MODEL_CACHE[m_key]

    def extract_audio_stream_copy(self):
        """
        【极致优化】不转码，直接拷贝音频流。
        速度比转 MP3 快 10-20 倍。
        """
        print(">>> 1. 快速抽取音频流...")
        # 尝试使用 m4a (AAC流通常存为m4a)
        audio_path = os.path.join(self.output_dir, "temp_audio.m4a")
        
        try:
            (
                ffmpeg
                .input(self.video_path)
                .output(audio_path, acodec='copy', map='a', loglevel="error", y=None)
                .run(cmd=ffmpeg_exe if 'ffmpeg_exe' in globals() else 'ffmpeg')
            )
            return audio_path
        except Exception as e:
            print(f"直接流拷贝失败，回退到转码模式: {e}")
            # 回退到标准 MP3 转码
            audio_path = os.path.join(self.output_dir, "temp_audio.mp3")
            (
                ffmpeg
                .input(self.video_path)
                .output(audio_path, acodec='libmp3lame', q=4, loglevel="error", y=None)
                .run(cmd=ffmpeg_exe if 'ffmpeg_exe' in globals() else 'ffmpeg')
            )
            return audio_path


    def has_video_stream(self):
        try:
            print(f">>> Checking video stream for: {self.video_path}")
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                print(f"DEBUG: cv2.VideoCapture failed to open {self.video_path}")
                cap.release()
                return False
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            cap.release()
            
            print(f"DEBUG: Video Probe: fps={fps}, frames={frame_count}, w={width}, h={height}")

            # 宽松检查：如果分辨率正常，通常就是视频
            if width > 0 and height > 0:
                return True

            if not fps or fps <= 0.1:
                return False
            if not frame_count or frame_count <= 0:
                return False
            return True
        except Exception as e:
            print(f"DEBUG: has_video_stream exception: {e}")
            return False

    def capture_frame(self, timestamp, output_subfolder="courseware"):
        """截取指定时间戳的帧"""
        print(f">>> 截取帧 at {timestamp}s...")
        cw_dir = os.path.join(self.output_dir, output_subfolder)
        os.makedirs(cw_dir, exist_ok=True)
        
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            print("Error: Could not open video.")
            return None

        # Calculate frame number
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        frame_no = int(timestamp * fps)
        
        print(f"DEBUG: fps={fps}, total_frames={total_frames}, target_timestamp={timestamp}, target_frame={frame_no}")
        
        if frame_no >= total_frames:
             print(f"Warning: Timestamp {timestamp}s is out of bounds (max {total_frames/fps:.2f}s). Clamping to last frame.")
             frame_no = int(total_frames - 1)

        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            print("Error: Could not read frame.")
            return None

        # Save frame
        filename = f"manual_{int(timestamp * 1000)}.jpg"
        filepath = os.path.join(cw_dir, filename)
        cv2.imwrite(filepath, frame)
        
        return os.path.join(output_subfolder, filename)

    def fast_transcribe(self, audio_path):
        """
        【极致优化】整段识别 + VAD 过滤 + 贪婪解码
        """
        model_size = self.config["model_size"]
        device = self.config["device"]
        compute_type = self.config["compute_type"]
        
        # print(f">>> 2. 加载 Whisper 模型 ({model_size}) on {device}...")
        try:
            # 使用 get_model 获取缓存的模型，避免重复加载和销毁导致的崩溃
            model = self.get_model()
        except Exception as e:
            print(f"模型加载失败 (可能是 CUDA 不可用): {e}")
            print("尝试切换到 CPU 模式...")
            # 如果 CUDA 失败，强制切换配置并重试
            self.config["device"] = "cpu"
            self.config["compute_type"] = "int8"
            model = self.get_model()

        print(">>> 正在进行 ASR 加速转录...")
        # vad_filter=True: 跳过静音，极大提升速度
        # beam_size=1: 贪婪解码，比默认 5 快很多，精度略降但足够做总结
        segments, info = model.transcribe(
            audio_path, 
            beam_size=1, 
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )

        full_text_list = []
        for segment in segments:
            start = round(segment.start, 2)
            text = segment.text.strip()
            if text:
                full_text_list.append(f"[{start}s] {text}")
        
        print(f">>> 转录完成，共 {len(full_text_list)} 句字幕。")
        return "\n".join(full_text_list)

    def _describe_images(self):
        if not self.selected_images:
            return ""
        
        print(f">>> Processing {len(self.selected_images)} selected images for context...")
        
        # Use VL model to describe images
        vl_model = self.config.get("vl_model", "Pro/Qwen/Qwen2-VL-7B-Instruct")
        vl_base_url = self.config.get("vl_base_url", "https://api.siliconflow.cn/v1")
        vl_api_key = self.config.get("vl_api_key") or self.config.get("openai_api_key")
        
        if not vl_api_key:
            print("Warning: No API key for VL model.")
            return ""

        descriptions = []
        try:
            # Use a separate client for VL if needed, or reuse if same base_url (but usually VL has different config)
            # Here we create a new client to be safe with VL config
            client = OpenAI(api_key=vl_api_key, base_url=vl_base_url)
            
            for idx, img_url in enumerate(self.selected_images):
                try:
                    self.log(f"Analyzing image {idx+1}/{len(self.selected_images)}...")
                    response = client.chat.completions.create(
                        model=vl_model,
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "image_url", "image_url": {"url": img_url}},
                                    {"type": "text", "text": "Describe this image in detail, focusing on text and key visual elements related to the presentation/content."}
                                ]
                            }
                        ],
                        max_tokens=500
                    )
                    desc = response.choices[0].message.content
                    descriptions.append(f"Image {idx+1} Content: {desc}")
                except Exception as e:
                    print(f"Failed to describe image {img_url}: {e}")
                    
        except Exception as e:
            print(f"VL Client init failed: {e}")
            
        if descriptions:
            return "\n\n[Visual Context from Selected Courseware Images]:\n" + "\n".join(descriptions) + "\n"
        return ""

    def analyze_segments_with_llm(self, transcript):
        """
        让 AI 决定分段点和总结。
        要求 AI 返回 JSON 格式，包含时间点、小标题、摘要。
        """
        print(">>> 3. 发送给 LLM 进行逻辑分段与规划...")
        
        # Check for selected images and generate descriptions
        image_context = self._describe_images()
        if image_context:
            self.log(">>> 已生成图片上下文，将合并到 Prompt 中...")
        
        system_prompt = (
            "你是一个专业的教育内容创作者和视频分析专家。我将提供带有时间戳的视频字幕。"
            "请将其转化为一份结构精美、易于学习的“深度学习笔记”。"
            "1. 标题：为视频拟定一个正式的学术/教育标题。\n"
            "2. 逻辑分段：将视频划分为 5-10 个关键教学环节，每个环节需包含：\n"
            "   - timestamp: 段落开始的时间点（秒）。\n"
            "   - title: 环节标题。\n"
            "   - points: 3-5个关于该段内容的详细逻辑要点（如状态描述、变化过程、解决方案等）。\n"
            "3. 知识小结表：提取视频中的核心知识点，以列表形式返回，包含知识点名称、核心内容、学习/应用重点、难度系数（用星星表示，如 ⭐⭐）。\n"
            "4. 关键标签：提取视频的3个核心关键词或分类标签。\n"
            "5. 专业术语表：提取视频中的专业术语、难懂词汇或行业黑话，并提供通俗易懂的解释。\n"
            "请严格以 JSON 格式输出，不要使用 Markdown 代码块；不要在字符串里插入未转义的换行/制表符；输出必须是可被标准 JSON 解析器解析的合法 JSON。\n"
            "格式如下：\n"
            "{\n"
            '  "title": "视频课程标题",\n'
            '  "summary": "全视频的总体摘要",\n'
            '  "tags": ["标签1", "标签2", "标签3"],\n'
            '  "terms": [\n'
            '    {"term": "专业术语", "definition": "通俗易懂的解释"}\n'
            '  ],\n'
            '  "segments": [\n'
            '    {"timestamp": 12.5, "title": "段落标题", "points": ["要点1", "要点2"]}\n'
            '  ],\n'
            '  "knowledge_table": [\n'
            '    {"point": "知识点名称", "content": "核心内容", "key_note": "学习重点", "difficulty": "⭐⭐"}\n'
            '  ]\n'
            "}"
        )

        # 截断过长文本，防止 token 溢出 (视模型能力调整)
        user_input = transcript[:15000]
        if image_context:
             user_input += image_context

        models = []
        primary_model = self.config.get("llm_model")
        if primary_model:
            models.append(primary_model)
        fallback_model = os.getenv("LLM_MODEL", "").strip()
        if fallback_model and fallback_model not in models:
            models.append(fallback_model)

        last_error = None
        last_preview = ""
        for model_name in models:
            try:
                def _strip_code_fences(text: str) -> str:
                    t = (text or "").strip()
                    if not t:
                        return t
                    if t.startswith("```"):
                        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
                        t = re.sub(r"\s*```$", "", t)
                    return t.strip()

                def _extract_json_object(text: str) -> str:
                    if not text:
                        return ""
                    start = text.find("{")
                    end = text.rfind("}")
                    if start == -1 or end == -1 or end <= start:
                        return ""
                    return text[start : end + 1]

                def _escape_newlines_in_strings(text: str) -> str:
                    if not text:
                        return ""
                    out = []
                    in_str = False
                    esc = False
                    for ch in text:
                        if in_str:
                            if esc:
                                out.append(ch)
                                esc = False
                                continue
                            if ch == "\\":
                                out.append(ch)
                                esc = True
                                continue
                            if ch == '"':
                                in_str = False
                                out.append(ch)
                                continue
                            if ch in ("\n", "\r"):
                                out.append("\\n")
                                continue
                            if ch == "\t":
                                out.append("\\t")
                                continue
                            out.append(ch)
                        else:
                            if ch == '"':
                                in_str = True
                            out.append(ch)
                    return "".join(out)

                def _repair_json_text(text: str) -> str:
                    t = (text or "").strip()
                    if not t:
                        return t
                    t = t.replace("\ufeff", "")
                    t = t.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
                    t = _escape_newlines_in_strings(t)
                    t = re.sub(r",\s*([}\]])", r"\1", t)
                    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", t)
                    return t.strip()

                def _parse_json_best_effort(text: str):
                    candidates = []
                    base = _strip_code_fences(text)
                    candidates.append(base)
                    extracted = _extract_json_object(base)
                    if extracted and extracted != base:
                        candidates.append(extracted)
                    candidates.append(_escape_newlines_in_strings(base))
                    if extracted:
                        candidates.append(_escape_newlines_in_strings(extracted))
                    candidates.append(_repair_json_text(base))
                    if extracted:
                        candidates.append(_repair_json_text(extracted))

                    parse_error = None
                    for c in candidates:
                        c = (c or "").strip()
                        if not c:
                            continue
                        try:
                            return json.loads(c)
                        except Exception as e:
                            parse_error = e
                    raise parse_error or ValueError("empty json content")

                def _call(with_response_format: bool):
                    kwargs = {}
                    if with_response_format:
                        kwargs["response_format"] = {"type": "json_object"}
                    return self.client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_input},
                        ],
                        **kwargs,
                    )

                response = None
                try:
                    response = _call(with_response_format=True)
                except Exception:
                    response = _call(with_response_format=False)

                content = (response.choices[0].message.content or "").strip()
                try:
                    return _parse_json_best_effort(content)
                except Exception as e:
                    last_preview = re.sub(r"\s+", " ", content)[:600]
                    raise e
            except Exception as e:
                last_error = e
                continue
        if last_preview:
            print(f"LLM 输出片段: {last_preview}")
        print(f"LLM 调用失败: {last_error}")
        return None

    def capture_best_frame(self, timestamp, output_name):
        """
        【优化版】多点采样筛选最佳帧
        在起始点后的一段窗口内寻找“信息量最大”（方差最高）的一帧，避免截到转场或黑屏
        """
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            return None
            
        best_frame = None
        max_variance = -1
        
        # 采样点：起始时间 + 偏移量，以及偏移量前后的点
        # 目的：跳过说话前奏，寻找画面稳定的瞬间
        base_ts = float(timestamp) + self.config["capture_offset"]
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
        duration_s = (frame_count / fps) if fps > 0.1 and frame_count > 1 else None
        end_guard = 0.25
        if duration_s is not None and duration_s > end_guard:
            base_ts = max(0.0, min(base_ts, duration_s - end_guard))

        sample_offsets = [-1.0, 0.0, 1.5, 3.0]  # 采样范围：相对于 base_ts
        if duration_s is not None and duration_s > end_guard:
            if base_ts + max(sample_offsets) > duration_s - end_guard:
                sample_offsets = [-3.0, -1.5, -0.5, 0.0]
        
        for offset in sample_offsets:
            target_ts = base_ts + offset
            if duration_s is not None and duration_s > end_guard:
                target_ts = max(0.0, min(target_ts, duration_s - end_guard))
            if target_ts < 0:
                continue
            
            cap.set(cv2.CAP_PROP_POS_MSEC, target_ts * 1000)
            ret, frame = cap.read()
            if ret:
                # 计算拉普拉斯方差（Laplacian Variance）作为画面丰富度/清晰度的指标
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                variance = cv2.Laplacian(gray, cv2.CV_64F).var()
                
                if variance > max_variance:
                    max_variance = variance
                    best_frame = frame
        
        cap.release()
        if best_frame is not None:
            cv2.imwrite(output_name, best_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            return output_name

        def _ffmpeg_grab(ts: float) -> bool:
            try:
                args = [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    str(max(0.0, ts)),
                    "-i",
                    self.video_path,
                    "-frames:v",
                    "1",
                    "-q:v",
                    "4",
                    "-y",
                    output_name,
                ]
                r = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return r.returncode == 0 and os.path.exists(output_name) and os.path.getsize(output_name) > 0
            except Exception:
                return False

        fallback_ts = base_ts
        if duration_s is not None and duration_s > end_guard:
            fallback_ts = max(0.0, min(fallback_ts, duration_s - end_guard))
        if _ffmpeg_grab(fallback_ts):
            return output_name
        if _ffmpeg_grab(max(0.0, fallback_ts - 1.0)):
            return output_name

        if duration_s is not None:
            print(f"无法在 {timestamp}s 附近截取有效帧（视频时长≈{duration_s:.2f}s，capture_offset={self.config.get('capture_offset')}）")
        else:
            print(f"无法在 {timestamp}s 附近截取有效帧")
        return None

    def parallel_screenshots(self, segments):
        """
        【速度优化】多线程并发截取图片
        """
        print(f">>> 4. 并行截取 {len(segments)} 张关键帧...")
        
        tasks = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            for i, seg in enumerate(segments):
                if not isinstance(seg, dict) or "timestamp" not in seg:
                    continue
                ts = seg["timestamp"]
                img_name = f"keyframe_{i:02d}_{int(ts)}s.jpg"
                img_path = os.path.join(self.img_dir, img_name)
                # 提交任务
                tasks.append(executor.submit(self.capture_best_frame, ts, img_path))
                # 将图片路径回填到数据结构中，方便生成 MD
                seg["image_path"] = f"images/{img_name}"
            
            # 等待所有截图完成
            for task in tasks:
                task.result()

    def generate_markdown(self, data, filename="final_report.md"):
        print(">>> 5. 生成最终 Markdown 报告...")
        path = os.path.join(self.output_dir, filename)
        segments = data.get("segments", [])
        if isinstance(segments, dict):
            try:
                segments = [segments[k] for k in sorted(segments.keys(), key=lambda x: float(x))]
            except Exception:
                segments = list(segments.values())
        if not isinstance(segments, list):
            segments = []
        
        with open(path, "w", encoding="utf-8") as f:
            # 1. 标题与摘要
            f.write(f"# {data.get('title', '视频深度分析报告')}\n\n")
            f.write(f"**生成时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## 💡 核心摘要\n")
            f.write(f"{data.get('summary', '无摘要')}\n\n")
            
            f.write("---\n\n")
            
            # 2. 详细剧情解析 (笔记流模式)
            f.write("## 🎬 教学/剧情解析\n\n")
            
            for i, seg in enumerate(segments):
                if not isinstance(seg, dict):
                    continue
                timestamp = seg.get("timestamp", 0)
                t_str = time.strftime('%H:%M:%S', time.gmtime(timestamp if isinstance(timestamp, (int, float)) else 0))
                img = seg.get('image_path', '')
                title = seg.get("title", "未命名段落")
                f.write(f"### {i+1}. {title} `{t_str}`\n\n")
                
                if img:
                    f.write(f"![{title}]({img})\n\n")
                
                # 要点列表
                points = seg.get('points', [])
                if not isinstance(points, list):
                    points = []
                for pt in points:
                    f.write(f"- {pt}\n")
                f.write("\n")

            # 3. 知识小结表
            knowledge_table = data.get("knowledge_table")
            if isinstance(knowledge_table, dict):
                knowledge_table = list(knowledge_table.values())
            if isinstance(knowledge_table, list) and knowledge_table:
                f.write("---\n\n")
                f.write("## 📚 知识小结\n\n")
                f.write("| 知识点 | 核心内容 | 学习/应用重点 | 难度系数 |\n")
                f.write("| :--- | :--- | :--- | :--- |\n")
                for item in knowledge_table:
                    if not isinstance(item, dict):
                        item = {"point": str(item), "content": "", "key_note": "", "difficulty": ""}
                    # 确保内容中没有换行符，否则会破坏 Markdown 表格结构
                    p = str(item.get('point', '')).replace("\n", " ")
                    c = str(item.get('content', '')).replace("\n", " ")
                    k = str(item.get('key_note', '')).replace("\n", " ")
                    d = str(item.get('difficulty', '')).replace("\n", " ")
                    f.write(f"| **{p}** | {c} | {k} | {d} |\n")
        
        return path

    def log(self, message):
        print(message)
        if self.progress_callback:
            self.progress_callback(message)

    def run(self):
        overall_start = time.time()
        
        try:
            # 1. 极速提取音频
            self.log(">>> 1. 快速抽取音频流...")
            t0 = time.time()
            audio_path = self.extract_audio_stream_copy()
            self.log(f"   [耗时] 音频提取: {time.time() - t0:.2f} 秒")
            
            # 2. 极速转录
            t1 = time.time()
            transcript = self.fast_transcribe(audio_path)
            self.log(f"   [耗时] ASR 转录: {time.time() - t1:.2f} 秒")
            
            if not transcript or not transcript.strip():
                self.log("❌ 未检测到有效字幕，停止分析")
                has_video = self.has_video_stream()
                return {
                    "title": "未检测到字幕",
                    "summary": "视频中未检测到有效语音或字幕。",
                    "segments": [],
                    "knowledge_table": [],
                    "raw_transcript": "",
                    "media_type": "video" if has_video else "audio",
                    "no_subtitles": True
                }
            
            # 3. AI 规划分段 (核心逻辑)
            t2 = time.time()
            ai_analysis = self.analyze_segments_with_llm(transcript)
            self.log(f"   [耗时] LLM 分析: {time.time() - t2:.2f} 秒")
            
            if ai_analysis:
                has_video = self.has_video_stream()
                ai_analysis["media_type"] = "video" if has_video else "audio"
                # 4. 并行截图
                if has_video:
                    t3 = time.time()
                    self.parallel_screenshots(ai_analysis.get("segments", []))
                    self.log(f"   [耗时] 并行截图: {time.time() - t3:.2f} 秒")
                
                # 5. 输出报告
                t4 = time.time()
                md_path = self.generate_markdown(ai_analysis)
                self.log(f"   [耗时] 报告生成: {time.time() - t4:.2f} 秒")
                
                self.log(f"\n✅ 全部完成！总耗时: {time.time() - overall_start:.2f} 秒")
                
                # 清理临时音频
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                
                # 在结果中包含原始转录内容
                ai_analysis["raw_transcript"] = transcript
                return ai_analysis
            else:
                self.log("❌ LLM 分析失败，无法生成报告")
                return None
        except Exception as e:
            self.log(f"运行过程中发生错误: {e}")
            return None

if __name__ == "__main__":
    if not os.path.exists(VIDEO_PATH):
        print(f"视频文件不存在: {VIDEO_PATH}")
        print("请在 .env 中设置 VIDEO_PATH 或确保当前目录下有 input.mp4")
    else:
        analyzer = FastVideoAnalyzer(VIDEO_PATH, OUTPUT_DIR)
        analyzer.run()
