import os
import cv2
import time
import json
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

# ================= 配置区域 =================
VIDEO_PATH = os.getenv("VIDEO_PATH", "input.mp4")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "fast_output")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-...")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1")

# ASR 设置
MODEL_SIZE = os.getenv("MODEL_SIZE", "medium")    # 追求速度可用 "small"，追求质量用 "medium", "large-v3"
DEVICE = os.getenv("DEVICE", "cuda")              # 必须用 cuda 才能快
COMPUTE_TYPE = os.getenv("COMPUTE_TYPE", "float16")

# LLM 设置
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-V3")

# 截图优化设置
CAPTURE_OFFSET = float(os.getenv("CAPTURE_OFFSET", "5.0"))  # 默认向后偏移 5 秒
# ===========================================

class FastVideoAnalyzer:
    def __init__(self, video_path, output_dir):
        self.video_path = video_path
        self.output_dir = output_dir
        self.client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        
        os.makedirs(self.output_dir, exist_ok=True)
        self.img_dir = os.path.join(self.output_dir, "images")
        os.makedirs(self.img_dir, exist_ok=True)

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
                .output(audio_path, acodec='copy', vn=None, loglevel="error")
                .overwrite_output()
                .run()
            )
            return audio_path
        except Exception as e:
            print(f"流拷贝失败，尝试快速转码为 wav 模式: {e}")
            # 备用方案：如果源封装格式不支持直接拷贝，则快速转码为 wav
            audio_path = os.path.join(self.output_dir, "temp_audio.wav")
            try:
                (
                    ffmpeg
                    .input(self.video_path)
                    .output(audio_path, acodec='pcm_s16le', ac=1, ar='16k', vn=None, loglevel="error")
                    .overwrite_output()
                    .run()
                )
                return audio_path
            except Exception as e2:
                print(f"音频提取完全失败: {e2}")
                raise

    def fast_transcribe(self, audio_path):
        """
        【极致优化】整段识别 + VAD 过滤 + 贪婪解码
        """
        print(f">>> 2. 加载 Whisper 模型 ({MODEL_SIZE}) on {DEVICE}...")
        try:
            model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
        except Exception as e:
            print(f"模型加载失败 (可能是 CUDA 不可用): {e}")
            print("尝试切换到 CPU 模式...")
            model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

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

    def analyze_segments_with_llm(self, transcript):
        """
        让 AI 决定分段点和总结。
        要求 AI 返回 JSON 格式，包含时间点、小标题、摘要。
        """
        print(">>> 3. 发送给 LLM 进行逻辑分段与规划...")
        
        system_prompt = (
            "你是一个专业的教育内容创作者和视频分析专家。我将提供带有时间戳的视频字幕。"
            "请将其转化为一份结构精美、易于学习的“深度学习笔记”。"
            "1. 标题：为视频拟定一个正式的学术/教育标题。\n"
            "2. 逻辑分段：将视频划分为 5-10 个关键教学环节，每个环节需包含：\n"
            "   - timestamp: 段落开始的时间点（秒）。\n"
            "   - title: 环节标题。\n"
            "   - points: 3-5个关于该段内容的详细逻辑要点（如状态描述、变化过程、解决方案等）。\n"
            "3. 知识小结表：提取视频中的核心知识点，以列表形式返回，包含知识点名称、核心内容、学习/应用重点、难度系数（用星星表示，如 ⭐⭐）。\n"
            "请严格以 JSON 格式输出，格式如下：\n"
            "{\n"
            '  "title": "视频课程标题",\n'
            '  "summary": "全视频的总体摘要",\n'
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

        try:
            response = self.client.chat.completions.create(
                model=LLM_MODEL, 
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                response_format={"type": "json_object"} if "DeepSeek" not in LLM_MODEL else None # 硅基流动的 DeepSeek 模型有时对 json_object 支持有差异，视情况调整
            )
            content = response.choices[0].message.content
            # 硅基流动的某些模型可能在内容前后包含 ```json ... ```
            if content.startswith("```json"):
                content = content.replace("```json", "", 1).replace("```", "", 1).strip()
            return json.loads(content)
        except Exception as e:
            print(f"LLM 调用失败: {e}")
            return None

    def capture_frame(self, timestamp, output_name):
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
        base_ts = float(timestamp) + CAPTURE_OFFSET
        sample_offsets = [-1.0, 0.0, 1.5, 3.0] # 采样范围：相对于 base_ts
        
        for offset in sample_offsets:
            target_ts = base_ts + offset
            if target_ts < 0: continue
            
            cap.set(cv2.CAP_PROP_POS_MSEC, target_ts * 1000)
            ret, frame = cap.read()
            if ret:
                # 计算拉普拉斯方差（Laplacian Variance）作为画面丰富度/清晰度的指标
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                variance = cv2.Laplacian(gray, cv2.CV_64F).var()
                
                if variance > max_variance:
                    max_variance = variance
                    best_frame = frame
        
        if best_frame is not None:
            cv2.imwrite(output_name, best_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        else:
            print(f"无法在 {timestamp}s 附近截取有效帧")
            
        cap.release()
        return output_name

    def parallel_screenshots(self, segments):
        """
        【速度优化】多线程并发截取图片
        """
        print(f">>> 4. 并行截取 {len(segments)} 张关键帧...")
        
        tasks = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            for i, seg in enumerate(segments):
                ts = seg["timestamp"]
                img_name = f"keyframe_{i:02d}_{int(ts)}s.jpg"
                img_path = os.path.join(self.img_dir, img_name)
                # 提交任务
                tasks.append(executor.submit(self.capture_frame, ts, img_path))
                # 将图片路径回填到数据结构中，方便生成 MD
                seg["image_path"] = f"images/{img_name}"
            
            # 等待所有截图完成
            for task in tasks:
                task.result()

    def generate_markdown(self, data, filename="final_report.md"):
        print(">>> 5. 生成最终 Markdown 报告...")
        path = os.path.join(self.output_dir, filename)
        
        with open(path, "w", encoding="utf-8") as f:
            # 1. 标题与摘要
            f.write(f"# {data.get('title', '视频深度分析报告')}\n\n")
            f.write(f"**生成时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## 💡 核心摘要\n")
            f.write(f"{data.get('summary', '无摘要')}\n\n")
            
            f.write("---\n\n")
            
            # 2. 详细剧情解析 (笔记流模式)
            f.write("## 🎬 教学/剧情解析\n\n")
            
            for i, seg in enumerate(data.get("segments", [])):
                t_str = time.strftime('%H:%M:%S', time.gmtime(seg['timestamp']))
                img = seg.get('image_path', '')
                f.write(f"### {i+1}. {seg['title']} `{t_str}`\n\n")
                
                # 图片展示
                f.write(f"![{seg['title']}]({img})\n\n")
                
                # 要点列表
                for pt in seg.get('points', []):
                    f.write(f"- {pt}\n")
                f.write("\n")

            # 3. 知识小结表
            if data.get("knowledge_table"):
                f.write("---\n\n")
                f.write("## 📚 知识小结\n\n")
                f.write("| 知识点 | 核心内容 | 学习/应用重点 | 难度系数 |\n")
                f.write("| :--- | :--- | :--- | :--- |\n")
                for item in data["knowledge_table"]:
                    f.write(f"| **{item['point']}** | {item['content']} | {item['key_note']} | {item['difficulty']} |\n")
        
        return path

    def run(self):
        overall_start = time.time()
        
        try:
            # 1. 极速提取音频
            t0 = time.time()
            audio_path = self.extract_audio_stream_copy()
            print(f"   [耗时] 音频提取: {time.time() - t0:.2f} 秒")
            
            # 2. 极速转录
            t1 = time.time()
            transcript = self.fast_transcribe(audio_path)
            print(f"   [耗时] ASR 转录: {time.time() - t1:.2f} 秒")
            
            # 3. AI 规划分段 (核心逻辑)
            t2 = time.time()
            ai_analysis = self.analyze_segments_with_llm(transcript)
            print(f"   [耗时] LLM 分析: {time.time() - t2:.2f} 秒")
            
            if ai_analysis:
                # 4. 并行截图
                t3 = time.time()
                self.parallel_screenshots(ai_analysis.get("segments", []))
                print(f"   [耗时] 并行截图: {time.time() - t3:.2f} 秒")
                
                # 5. 输出报告
                t4 = time.time()
                md_path = self.generate_markdown(ai_analysis)
                print(f"   [耗时] 报告生成: {time.time() - t4:.2f} 秒")
                
                print(f"\n✅ 全部完成！总耗时: {time.time() - overall_start:.2f} 秒")
                print(f"📄 报告位置: {md_path}")
                
                # 清理临时音频
                if os.path.exists(audio_path):
                    os.remove(audio_path)
            else:
                print("❌ LLM 分析失败，无法生成报告")
        except Exception as e:
            print(f"运行过程中发生错误: {e}")

if __name__ == "__main__":
    if not os.path.exists(VIDEO_PATH):
        print(f"视频文件不存在: {VIDEO_PATH}")
        print("请在 .env 中设置 VIDEO_PATH 或确保当前目录下有 input.mp4")
    else:
        analyzer = FastVideoAnalyzer(VIDEO_PATH, OUTPUT_DIR)
        analyzer.run()
