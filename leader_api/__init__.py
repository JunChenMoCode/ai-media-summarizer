"""
后端 API 包。

目标：
- 把原本堆在 main.py 的逻辑按职责拆分成多个模块，便于维护与扩展。
- 保持对外行为不变：路由路径、请求/响应结构、uvicorn 启动方式仍可用 `main:app`。
"""

from .app import app, create_app

