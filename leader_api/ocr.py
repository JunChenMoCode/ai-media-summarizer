import base64
import mimetypes
import os
import shutil
import subprocess
import tempfile
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException
from openai import OpenAI

from .models import ConfigModel, CoursewareOcrRequest
from .mysql_store import load_app_config

router = APIRouter()


def _encode_image_to_base64(image_path: str) -> str:
    """
    将本地图片编码为 base64 字符串，供 VL 模型以 data URL 形式输入。
    """
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def analyze_image_with_vl_model(config: ConfigModel, image_path: str, prompt: str = "OCR:") -> str:
    """
    使用视觉语言模型（VL）做 OCR。

    说明：
    - 这里复用 OpenAI SDK 的 chat.completions 接口；
    - 若配置了 VL 专用的 base_url / api_key，则优先使用；
      否则退回到通用 openai_base_url / openai_api_key。
    """
    api_key = config.vl_api_key if config.vl_api_key else config.openai_api_key
    base_url = config.vl_base_url if config.vl_base_url else config.openai_base_url
    model = config.vl_model

    if not api_key:
        raise ValueError("API Key is required for VL model")

    client = OpenAI(api_key=api_key, base_url=base_url)
    base64_image = _encode_image_to_base64(image_path)

    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type or not mime_type.startswith("image"):
        mime_type = "image/jpeg"

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    return response.choices[0].message.content


def analyze_image_with_vl_model_bytes(config: ConfigModel, image_bytes: bytes, mime_type: str, prompt: str = "OCR:") -> str:
    """
    VL OCR 的 bytes 版本：用于 URL 下载到内存后直接提交给模型。
    """
    api_key = config.vl_api_key if config.vl_api_key else config.openai_api_key
    base_url = config.vl_base_url if config.vl_base_url else config.openai_base_url
    model = config.vl_model

    if not api_key:
        raise ValueError("API Key is required for VL model")

    client = OpenAI(api_key=api_key, base_url=base_url)
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    mt = (mime_type or "").strip().lower()
    if not mt.startswith("image/"):
        mt = "image/jpeg"

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mt};base64,{base64_image}"}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    return response.choices[0].message.content


def tesseract_ocr_file(image_path: str) -> str:
    """
    调用本机 tesseract 可执行文件，对图片做 OCR。

    tessdata 目录选择策略：
    - 优先读环境变量 TESSDATA_PREFIX（你当前启动命令里就设置了它）；
    - 如果没设置，则默认使用 <cwd>/model/tessdata；
    - 通过 `--tessdata-dir` 显式传给 tesseract，避免使用系统默认语言包路径。
    """
    exe = shutil.which("tesseract")
    if not exe:
        raise RuntimeError("未找到 tesseract 可执行文件，请安装 Tesseract 并加入 PATH")

    lang = (os.getenv("TESSERACT_LANG", "") or "").strip() or "chi_sim+eng"
    tessdata_dir = (os.getenv("TESSDATA_PREFIX", "") or "").strip()
    if not tessdata_dir:
        tessdata_dir = os.path.join(os.getcwd(), "model", "tessdata")

    cmd = [exe, image_path, "stdout", "-l", lang, "--oem", "1", "--psm", "6"]
    if tessdata_dir and os.path.isdir(tessdata_dir):
        cmd.extend(["--tessdata-dir", tessdata_dir])

    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        err = (p.stderr or p.stdout or "").strip()
        raise RuntimeError(err or f"Tesseract 运行失败，退出码 {p.returncode}")
    return (p.stdout or "").strip()


def tesseract_ocr_bytes(image_bytes: bytes, mime_type: str) -> str:
    """
    Tesseract OCR 的 bytes 版本。

    说明：
    - tesseract CLI 主要面向文件输入，所以这里用临时文件桥接；
    - 该临时文件会在 finally 中删除，避免落盘残留。
    """
    mt = (mime_type or "").split(";", 1)[0].strip().lower()
    suffix = ".png" if mt == "image/png" else ".jpg"
    with tempfile.NamedTemporaryFile(prefix="leader-ocr-", suffix=suffix, delete=False) as tf:
        tmp_path = tf.name
        tf.write(image_bytes)
        tf.flush()
    try:
        return tesseract_ocr_file(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


def download_image_bytes(url: str) -> tuple[bytes, str]:
    """
    下载图片到内存并返回 (bytes, content-type)。

    - OCR_IMAGE_DOWNLOAD_TIMEOUT：超时时间（秒）
    - OCR_MAX_IMAGE_BYTES：最大下载字节数，避免错误 URL 拉爆内存
    """
    timeout_s = float(os.getenv("OCR_IMAGE_DOWNLOAD_TIMEOUT", "20"))
    max_bytes = int(os.getenv("OCR_MAX_IMAGE_BYTES", str(8 * 1024 * 1024)))
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=timeout_s) as resp:
        content_type = (resp.headers.get("Content-Type") or "").strip()
        buf = bytearray()
        while True:
            chunk = resp.read(64 * 1024)
            if not chunk:
                break
            buf.extend(chunk)
            if len(buf) > max_bytes:
                raise RuntimeError(f"图片过大: {len(buf)} bytes")
        if not buf:
            raise RuntimeError("图片下载为空")
        return bytes(buf), content_type


OCR_PROMPT = """
**任务要求** 
请作为专业级OCR处理引擎，对输入的图像执行以下精准操作： 

**核心功能** 

1. **多字体解析** 
   - 准确识别20+中文字体（如宋体、黑体、楷体等）及15+英文字体（如Arial、Times New Roman等）。 
2. **版式还原技术** 
   - 自动检测文本方向（支持0-360度旋转校正）。 
   - 保留段落间距（精度±1像素），还原原始分栏结构。 
   - 支持复杂版式解析，包括混合布局、倾斜文本及分栏页面。 
3. **智能纠错系统** 
   - 模糊文本增强处理（当分辨率低于150dpi时自动启用）。 
   - 相似字符差分校验（如0/O、1/l/i等，自动进行上下文校正）。 
   - 搭载智能语言模型，自动纠正常见拼写和语法错误。 
4. **格式识别与还原** 
   - **代码块**：支持Markdown格式代码块的识别，自动识别代码块的起始和结束标记（如```），并保留代码块内的格式、缩进和注释。 
   - **标题**：识别各级标题（如#、##、###等），并保留其格式。 
   - **列表**：支持有序列表（如1.、a.）和无序列表（如-、*）的识别，保留列表结构。 
   - **引用**：识别引用文本（如>），并保留其格式。 
   - **加粗与斜体**：识别加粗（如**bold**）和斜体（如*italic*）文本，并保留其格式。 
   - **表格**：支持Markdown格式表格的识别，保留表格结构和对齐方式。 

**处理标准** 

- **中英混合文本识别准确率**：≥99.5%（符合GB/T 37094-2018标准）。 
- **表格识别**：支持合并单元格检测，列宽对齐误差小于2字符。 
- **特殊内容处理**： 
  - 数学公式保持LaTeX格式。 
  - 程序代码保留缩进与注释，支持Markdown格式代码块的识别。 
  - 手写体标注[Handwritten]标签。 
  - 对扫描件进行深度增强处理，支持多页文档整合。 

**输出规范** 

- **编码格式**：纯文本输出，编码为UTF-8 with BOM。 
- **禁忌事项**：不添加识别置信度说明，不修改原始内容顺序。 
- **渲染要求**：不要将整个输出包裹在代码块围栏（```）中；仅当原图内容本身是代码块时才保留围栏。表格请输出标准 Markdown 表格（`|` + `---` 分隔行），不要用 ASCII 画线表格。 
- **最终要求**：输出仅为OCR后的原始文本，确保无任何附加信息，且完全保留原格式，包括Markdown代码块、标题、列表、引用、加粗与斜体等格式。 
"""


@router.post("/ocr_courseware")
async def ocr_courseware(request: CoursewareOcrRequest):
    """
    课件 OCR 批处理接口。

    输入：
    - items: [{url, timestamp, name}, ...]
    - config: 包含 ocr_engine（tesseract 或 vl）与对应鉴权/模型信息

    输出：
    - results: 按 timestamp 排序的 OCR 文本列表
    """
    items = request.items or []
    if not items:
        return {"results": []}

    config_data = load_app_config()
    if not config_data:
        raise RuntimeError("数据库配置为空，请先在前端设置并保存")
    config = ConfigModel(
        openai_api_key=config_data.get("openai_api_key", ""),
        openai_base_url=config_data.get("openai_base_url", ""),
        llm_model=config_data.get("llm_model", ""),
        ocr_engine=str(config_data.get("ocr_engine", "vl")),
        vl_model=str(config_data.get("vl_model", "Pro/Qwen/Qwen2-VL-7B-Instruct")),
        vl_base_url=str(config_data.get("vl_base_url", "https://api.siliconflow.cn/v1")),
        vl_api_key=str(config_data.get("vl_api_key", "")),
        model_size=config_data.get("model_size", "medium"),
        device=config_data.get("device", "cuda"),
        compute_type=config_data.get("compute_type", "float16"),
        capture_offset=float(config_data.get("capture_offset", 5.0)),
    )

    def run():
        results = []
        engine = (getattr(config, "ocr_engine", "") or "vl").strip().lower()
        for item in items:
            try:
                parsed = urlparse(item.url)
                if parsed.scheme not in ("http", "https"):
                    raise RuntimeError(f"不支持的图片 URL: {item.url}")

                image_bytes, content_type = download_image_bytes(item.url)
                mime_type = (content_type.split(";", 1)[0].strip() if content_type else "").lower()
                if not mime_type.startswith("image/"):
                    guessed = mimetypes.guess_type(unquote(parsed.path or ""))[0] or ""
                    mime_type = guessed.lower() if guessed else "image/jpeg"

                if engine == "tesseract":
                    text = tesseract_ocr_bytes(image_bytes, mime_type=mime_type)
                else:
                    text = analyze_image_with_vl_model_bytes(
                        config,
                        image_bytes,
                        mime_type=mime_type,
                        prompt=OCR_PROMPT,
                    )
            except Exception as e:
                print(f"OCR failed for {item.url}: {e}")
                text = f"[Error: {e}]"

            results.append(
                {
                    "timestamp": float(item.timestamp),
                    "name": item.name,
                    "url": item.url,
                    "text": text,
                }
            )
        results.sort(key=lambda x: x.get("timestamp", 0))
        return results

    try:
        import asyncio

        results = await asyncio.to_thread(run)
        try:
            video_md5 = (request.video_md5 or "").strip().lower()
            if video_md5 and len(video_md5) == 32:
                from .mysql_store import _sanitize_config, append_artifact_event_by_md5

                append_artifact_event_by_md5(
                    video_md5,
                    artifact_type="courseware_ocr",
                    content_json={"items": [i.model_dump() for i in items], "results": results},
                    artifact_meta={"config": _sanitize_config(config.model_dump())},
                )
        except Exception:
            pass
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
