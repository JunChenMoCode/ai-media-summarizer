import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core import bootstrap_env
from .analyze import router as analyze_router
from .capture import router as capture_router
from .llm_routes import router as llm_router
from .minio_routes import router as minio_router
from .ocr import router as ocr_router
from .translate_routes import router as translate_router
from .video import router as video_router


def create_app() -> FastAPI:
    """
    创建 FastAPI 应用。

    之所以用工厂函数：
    - 便于未来做测试（可以在测试里 create_app()）；
    - main.py 只负责导出 app，让入口更干净。
    """
    bootstrap_env()

    app = FastAPI()

    # 允许跨域：当前前端与后端可能在不同端口运行（vite dev server + uvicorn）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 路由按模块拆分，每个模块只关注自己的职责
    app.include_router(minio_router)
    app.include_router(video_router)
    app.include_router(analyze_router)
    app.include_router(translate_router)
    app.include_router(ocr_router)
    app.include_router(llm_router)
    app.include_router(capture_router)

    return app


# uvicorn 默认用 `main:app`，因此这里提供一个 module-level 的 app 实例
app = create_app()

