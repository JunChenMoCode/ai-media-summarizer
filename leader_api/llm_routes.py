import json
import os

from fastapi import APIRouter, HTTPException, WebSocket
from openai import AsyncOpenAI, BadRequestError

from .models import ConfigModel, MindMapRequest, NotesRequest

router = APIRouter()


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    前端聊天面板的 WebSocket 接口（流式输出）。

    协议约定（前端已实现对应解析）：
    - 发送: { messages, transcript, summary, config }
    - 接收:
      - {"type":"reasoning","delta":"..."}（部分模型可能返回）
      - {"type":"content","delta":"..."}（标准增量 token）
      - {"type":"error","content":"..."}（异常）
    """
    await websocket.accept()
    try:
        data = await websocket.receive_json()

        if "messages" in data:
            messages = data["messages"]
            transcript = data.get("transcript", "")
            summary = data.get("summary", "")
            config_data = data.get("config", {})
        else:
            messages = [{"role": "user", "content": "Hello"}]
            transcript = ""
            summary = ""
            config_data = {}

        # 仅提取我们真正会用到的字段，避免把旧字段带进来造成困扰
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

        client = AsyncOpenAI(api_key=config.openai_api_key, base_url=config.openai_base_url)

        system_prompt = (
            "你是一个专业的视频内容助手。你可以根据视频的字幕内容和摘要回答用户的问题。\n"
            f"视频摘要：{summary}\n"
            f"视频字幕片段：{transcript[:5000]}...\n"
            "请以Markdown格式回答。如果需要进行详细解释，请使用 <think>...</think> 包裹思考过程。"
        )

        chat_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            chat_messages.append({"role": msg["role"], "content": msg["content"]})

        response = None
        current_model = config.llm_model
        fallbacks = ["deepseek-ai/DeepSeek-V2.5", "Qwen/Qwen2.5-7B-Instruct", "deepseek-ai/DeepSeek-V3"]

        async def create_chat_stream(model_name: str):
            return await client.chat.completions.create(model=model_name, messages=chat_messages, stream=True)

        try:
            response = await create_chat_stream(current_model)
        except Exception as e:
            error_str = str(e)
            if "Model does not exist" in error_str or "400" in error_str:
                print(f"Chat model {current_model} failed, trying fallbacks...")
                success = False
                for fallback in fallbacks:
                    if fallback == current_model:
                        continue
                    try:
                        print(f"Trying fallback chat model: {fallback}")
                        response = await create_chat_stream(fallback)
                        success = True
                        break
                    except Exception as inner_e:
                        print(f"Fallback {fallback} failed: {inner_e}")
                if not success:
                    raise e
            else:
                raise e

        async for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            # 部分模型（例如 DeepSeek R1 风格）可能会返回“推理内容”
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                await websocket.send_json({"type": "reasoning", "delta": reasoning})

            if delta.content:
                await websocket.send_json({"type": "content", "delta": delta.content})

    except Exception as e:
        await websocket.send_json({"type": "error", "content": str(e)})
    finally:
        await websocket.close()


@router.post("/generate_mindmap")
async def generate_mindmap(request: MindMapRequest):
    """
    根据字幕生成思维导图（G6 TreeGraph JSON）。

    注意：
    - 该接口要求“只返回 JSON”，因此这里会做一次代码块围栏清理，再 json.loads。
    """
    client = AsyncOpenAI(api_key=request.config.openai_api_key, base_url=request.config.openai_base_url)

    system_prompt = """
你是一个思维导图专家。请根据用户提供的视频字幕内容，生成一个结构化的思维导图数据。
返回格式必须是符合 G6 TreeGraph 的 JSON 数据结构。

结构示例：
{
  "id": "root",
  "label": "核心主题",
  "children": [
    {
      "id": "c1",
      "label": "分支1",
      "children": [
        {"id": "c1-1", "label": "子节点1"}
      ]
    }
  ]
}

要求：
1. 根节点应该是视频的主题。
2. 第一层子节点是主要章节或关键话题。
3. 后续子节点是详细知识点。
4. 确保 id 唯一。
5. 只返回 JSON，不要包含 Markdown 格式标记 (如 ```json)。
"""

    try:
        model_name = request.config.llm_model
        fallback_model = os.getenv("LLM_MODEL", "").strip()

        try:
            response = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"视频字幕内容如下：\n{request.transcript[:20000]}"},
                ],
            )
        except Exception as e:
            error_str = str(e)
            if "Model does not exist" in error_str or "400" in error_str:
                if fallback_model and fallback_model != model_name:
                    print(f"Primary model {model_name} failed, trying fallback: {fallback_model}")
                    response = await client.chat.completions.create(
                        model=fallback_model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"视频字幕内容如下：\n{request.transcript[:20000]}"},
                        ],
                    )
                else:
                    raise e
            else:
                raise e

        content = response.choices[0].message.content
        if content.startswith("```json"):
            content = content.replace("```json", "", 1).replace("```", "", 1).strip()
        elif content.startswith("```"):
            content = content.replace("```", "", 1).strip()
            if content.endswith("```"):
                content = content[:-3].strip()

        return json.loads(content)
    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"Error generating mindmap: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate_notes")
async def generate_notes(request: NotesRequest):
    """
    根据字幕生成 Markdown 课程笔记。

    说明：
    - 该接口不强制返回 JSON，因此直接返回 content 文本；
    - 增加 “模型不存在” 的自动回退逻辑，减少前端看到 400/20012 的概率。
    """
    print(">>> Generating notes...")

    system_prompt = """你是一个专业的课程笔记整理助手。请根据提供的视频字幕内容，整理出一份结构清晰、重点突出的Markdown格式笔记。

要求：
1. 使用一级标题、二级标题等Markdown语法组织内容。
2. 提取关键概念和定义，并用加粗显示。
3. 总结每个章节的核心要点。
4. 如果有列表内容，请使用无序或有序列表。
5. 保持语言简洁流畅，适合复习和查阅。
6. 不要包含“视频”、“字幕”等词汇，直接呈现知识内容。
"""

    model_name = request.config.llm_model
    client = AsyncOpenAI(api_key=request.config.openai_api_key, base_url=request.config.openai_base_url)

    async def call_llm(model: str):
        return await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"视频字幕内容如下：\n{request.transcript[:25000]}"},
            ],
        )

    try:
        response = await call_llm(model_name)
    except BadRequestError as e:
        is_model_error = "Model does not exist" in str(e) or (e.body and e.body.get("code") == 20012)
        if is_model_error:
            print(f"Model {model_name} failed, trying fallbacks...")
            fallbacks = ["deepseek-ai/DeepSeek-V2.5", "Qwen/Qwen2.5-7B-Instruct", "deepseek-ai/DeepSeek-V3"]
            success = False
            for fallback in fallbacks:
                if fallback == model_name:
                    continue
                try:
                    print(f"Trying fallback model: {fallback}")
                    response = await call_llm(fallback)
                    success = True
                    break
                except Exception as inner_e:
                    print(f"Fallback {fallback} failed: {inner_e}")
            if not success:
                raise e
        else:
            raise e

    content = response.choices[0].message.content
    return {"notes": content}

