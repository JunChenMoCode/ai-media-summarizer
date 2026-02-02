from fastapi import APIRouter, HTTPException

from .models import TranslateRequest
from .translate import translate_lines

router = APIRouter()


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

        translated_texts = await asyncio.to_thread(translate_lines, lines, request.config.device)
        translations = [{"index": i, "text": text} for i, text in enumerate(translated_texts)]
        return {"translations": translations}
    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"Translation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

