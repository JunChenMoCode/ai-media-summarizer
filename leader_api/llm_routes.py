import json
from fastapi import APIRouter, HTTPException, WebSocket
from openai import AsyncOpenAI, BadRequestError

from .models import ConfigModel, MindMapRequest, NotesRequest
from .mysql_store import load_app_config

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
    video_md5 = ""
    transcript = ""
    summary = ""
    messages = []
    used_model = ""
    assistant_reasoning = ""
    assistant_content = ""
    try:
        data = await websocket.receive_json()

        if "messages" in data:
            messages = data["messages"]
            transcript = data.get("transcript", "")
            summary = data.get("summary", "")
        else:
            messages = [{"role": "user", "content": "Hello"}]
            transcript = ""
            summary = ""

        video_md5 = (data.get("video_md5", "") or "").strip().lower()

        # 仅提取我们真正会用到的字段，避免把旧字段带进来造成困扰
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
            used_model = current_model
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
                        used_model = fallback
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
                assistant_reasoning += reasoning
                await websocket.send_json({"type": "reasoning", "delta": reasoning})

            if delta.content:
                assistant_content += delta.content
                await websocket.send_json({"type": "content", "delta": delta.content})

    except Exception as e:
        await websocket.send_json({"type": "error", "content": str(e)})
    finally:
        try:
            if video_md5 and len(video_md5) == 32 and assistant_content:
                from .mysql_store import _sanitize_config, append_artifact_event_by_md5

                def _extract_think_blocks(text: str) -> tuple[str, str]:
                    if not text:
                        return "", ""
                    s = str(text)
                    think_parts: list[str] = []
                    out_parts: list[str] = []
                    i = 0
                    while i < len(s):
                        start = s.find("<think>", i)
                        if start < 0:
                            out_parts.append(s[i:])
                            break
                        out_parts.append(s[i:start])
                        end = s.find("</think>", start + len("<think>"))
                        if end < 0:
                            out_parts.append(s[start:])
                            break
                        think_parts.append(s[start + len("<think>") : end])
                        i = end + len("</think>")
                    clean = "".join(out_parts)
                    think = "".join(think_parts)
                    return clean, think

                clean_content, think_from_content = _extract_think_blocks(assistant_content)
                merged_reasoning = assistant_reasoning or ""
                if think_from_content.strip():
                    merged_reasoning = (merged_reasoning + "\n" + think_from_content).strip() if merged_reasoning else think_from_content.strip()

                normalized_messages = []
                for msg in messages or []:
                    if not isinstance(msg, dict):
                        continue
                    role = (msg.get("role") or "").strip()
                    content = msg.get("content", "")
                    if not role:
                        continue
                    normalized = {"role": role, "content": content}
                    if "kind" in msg and msg.get("kind") is not None:
                        normalized["kind"] = msg.get("kind")
                    normalized_messages.append(normalized)

                if merged_reasoning:
                    normalized_messages.append(
                        {"role": "assistant", "kind": "reasoning", "content": merged_reasoning, "reasoningExpanded": False}
                    )
                normalized_messages.append({"role": "assistant", "kind": "content", "content": clean_content})

                append_artifact_event_by_md5(
                    video_md5,
                    artifact_type="chat_session",
                    content_json={
                        "model": used_model,
                        "messages": normalized_messages,
                        "assistant": {"content": clean_content, "reasoning": merged_reasoning},
                        "context": {"transcript": transcript, "summary": summary},
                    },
                    artifact_meta={"config": _sanitize_config(config_data)},
                )
        except Exception:
            pass
        await websocket.close()


@router.post("/generate_mindmap")
async def generate_mindmap(request: MindMapRequest):
    """
    根据字幕生成思维导图（G6 TreeGraph JSON）。

    注意：
    - 该接口要求“只返回 JSON”，因此这里会做一次代码块围栏清理，再 json.loads。
    """
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
    client = AsyncOpenAI(api_key=config.openai_api_key, base_url=config.openai_base_url)

    system_prompt = """
你是一个思维导图专家。请根据用户提供的视频字幕内容，生成一个结构化的思维导图数据。
返回格式必须是符合 G6 TreeGraph 的 JSON 数据结构。

结构示例：
{
  "id": "root",
  "label": "🎥 核心主题",
  "children": [
    {
      "id": "c1",
      "label": "🌟 分支1",
      "children": [
        {"id": "c1-1", "label": "💡 子节点1"}
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
6. 请在每个节点的 label 中适当增加 Emoji 表情符号进行修饰，使思维导图更加生动直观。
"""

    try:
        model_name = config.llm_model

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

        result = json.loads(content)
        try:
            if request.video_md5:
                from .mysql_store import _sanitize_config, save_artifact_by_md5

                save_artifact_by_md5(
                    request.video_md5,
                    artifact_type="mindmap_g6",
                    artifact_version=1,
                    content_json=result,
                    artifact_meta={"config": _sanitize_config(config.model_dump())},
                )
        except Exception:
            pass
        return result
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
    model_name = config.llm_model
    client = AsyncOpenAI(api_key=config.openai_api_key, base_url=config.openai_base_url)

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
    try:
        if request.video_md5:
            from .mysql_store import _sanitize_config, save_artifact_by_md5

            save_artifact_by_md5(
                request.video_md5,
                artifact_type="notes_markdown",
                artifact_version=1,
                content_text=content,
                artifact_meta={"config": _sanitize_config(config.model_dump())},
            )
    except Exception:
        pass
    return {"notes": content}
