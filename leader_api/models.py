from pydantic import BaseModel


class ConfigModel(BaseModel):
    """
    前端“设置页”下发的配置对象。

    这个配置会被多个能力复用：
    - LLM（摘要/聊天/思维导图/笔记）
    - OCR（VL 模型 / Tesseract）
    - 翻译（transformers 机器翻译模型）
    """

    openai_api_key: str
    openai_base_url: str
    llm_model: str

    ocr_engine: str = "vl"
    vl_model: str = "Pro/Qwen/Qwen2-VL-7B-Instruct"
    vl_base_url: str = "https://api.siliconflow.cn/v1"
    vl_api_key: str = ""

    model_size: str
    device: str
    compute_type: str
    capture_offset: float


class TranscriptLine(BaseModel):
    timestamp: float
    text: str


class TranslateRequest(BaseModel):
    lines: list[TranscriptLine]
    config: ConfigModel


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    transcript: str | None = None
    summary: str | None = None
    config: ConfigModel


class MindMapRequest(BaseModel):
    transcript: str
    config: ConfigModel


class NotesRequest(BaseModel):
    transcript: str
    config: ConfigModel


class CoursewareOcrItem(BaseModel):
    url: str
    timestamp: float
    name: str


class CoursewareOcrRequest(BaseModel):
    items: list[CoursewareOcrItem]
    config: ConfigModel


class ImportVideoUrlRequest(BaseModel):
    url: str


class AnalyzePathRequest(BaseModel):
    video_path: str
    config: ConfigModel


class PresignUploadRequest(BaseModel):
    filename: str
    content_type: str | None = None


class CaptureRequest(BaseModel):
    video_filename: str
    timestamp: float

