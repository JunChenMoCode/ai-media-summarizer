from fastapi import APIRouter, HTTPException

from .models import TranslateRequest
from .translate import translate_lines

router = APIRouter()

def _detect_source_lang(lines) -> str:
    import re

    texts = [(getattr(line, "text", "") or "") for line in (lines or [])]
    if not texts:
        return "zh"
    sample = "\n".join(texts[:200])
    cjk = len(re.findall(r"[\u4e00-\u9fff]", sample))
    latin = len(re.findall(r"[A-Za-z]", sample))
    return "zh" if cjk >= latin else "en"


@router.post("/translate")
async def translate_subtitles(request: TranslateRequest):
    """
    翻译字幕的 HTTP 接口。

    说明：
    - 真正的翻译逻辑在 translate.translate_lines；
    - 这里用 asyncio.to_thread 把 CPU/GPU 密集任务丢到线程池，避免阻塞事件循环。
    """
    lines = request.lines or []
    if not lines:
        return {"translations": []}

    try:
        import asyncio

        source_lang = _detect_source_lang(lines)
        target_lang = "en" if source_lang == "zh" else "zh"
        translated_texts = await asyncio.to_thread(translate_lines, lines, request.config.device)
        translations = [{"index": i, "text": text} for i, text in enumerate(translated_texts)]
        try:
            if request.video_md5:
                from .mysql_store import save_artifact_by_md5

                translated_lines = []
                for i, line in enumerate(lines):
                    translated_lines.append(
                        {"timestamp": float(getattr(line, "timestamp", 0.0) or 0.0), "text": translations[i]["text"]}
                    )
                save_artifact_by_md5(
                    request.video_md5,
                    artifact_type=f"subtitle_translation_{target_lang}",
                    artifact_version=1,
                    content_json={"source_lang": source_lang, "target_lang": target_lang, "lines": translated_lines},
                )
        except Exception:
            pass
        return {"translations": translations}
    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"Translation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
