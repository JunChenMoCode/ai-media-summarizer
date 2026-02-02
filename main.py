"""
后端服务入口（尽量保持精简）。

说明：
- 以前 main.py 里同时包含：MinIO、OCR、翻译、视频分析、LLM 聊天等全部逻辑，文件过大不利于维护。
- 现在把实现按职责拆分到 leader_api/ 包内：
  - leader_api/app.py：应用创建与路由注册
  - leader_api/minio_store.py：MinIO 访问封装
  - leader_api/ocr.py：Tesseract/VL OCR
  - leader_api/analyze.py：视频分析流式接口
  - leader_api/video.py：URL 导入视频
  - leader_api/translate.py：字幕翻译
  - leader_api/llm_routes.py：聊天/思维导图/笔记
  - leader_api/capture.py：按时间点截图

兼容性：
- uvicorn 仍可用 `python -m uvicorn main:app --host 0.0.0.0 --port 18000`
"""

import os

from leader_api.app import app


if __name__ == "__main__":
    import uvicorn

    port_raw = (os.getenv("PORT", "") or "").strip()
    try:
        port = int(port_raw) if port_raw else 18000
    except Exception:
        port = 18000
    host = (os.getenv("HOST", "") or "").strip() or "0.0.0.0"
    uvicorn.run(app, host=host, port=port)

