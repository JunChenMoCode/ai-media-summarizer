import os
import json
import tempfile
import asyncio
import hashlib
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pypdf import PdfReader
from docx import Document
from pptx import Presentation
from openai import AsyncOpenAI
from .minio_store import (
    minio_enabled,
    minio_upload_file,
    minio_object_key,
    minio_presigned_url
)
from .mysql_store import save_artifact_by_md5, _sanitize_config

router = APIRouter()

def _file_md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _extract_text(file_path: str, ext: str) -> str:
    text = ""
    try:
        if ext == '.pdf':
            reader = PdfReader(file_path)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        elif ext in ['.docx', '.doc']:
            doc = Document(file_path)
            for para in doc.paragraphs:
                text += para.text + "\n"
        elif ext in ['.pptx', '.ppt']:
            prs = Presentation(file_path)
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text += shape.text + "\n"
        elif ext in ['.txt', '.md']:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
    except Exception as e:
        print(f"Error extracting text: {e}")
        return f"Error extracting text: {str(e)}"
    return text

@router.post("/analyze_file")
async def analyze_file(
    file: UploadFile = File(...),
    config: str = Form(...)
):
    """
    Upload a file (PDF, DOCX, PPTX, TXT, MD) and analyze it using LLM.
    Returns a stream of progress updates and finally the result.
    """
    async def event_generator():
        tmp_path = None
        try:
            # Parse config
            config_data = json.loads(config)
            # Ensure required fields
            conf = ConfigModel(
                openai_api_key=config_data.get("openai_api_key", ""),
                openai_base_url=config_data.get("openai_base_url", ""),
                llm_model=config_data.get("llm_model", ""),
                # Default other fields if missing
                ocr_engine=str(config_data.get("ocr_engine", "vl")),
                vl_model=str(config_data.get("vl_model", "")),
                vl_base_url=str(config_data.get("vl_base_url", "")),
                vl_api_key=str(config_data.get("vl_api_key", "")),
                model_size=str(config_data.get("model_size", "base")),
                device=str(config_data.get("device", "cpu")),
                compute_type=str(config_data.get("compute_type", "int8")),
                capture_offset=float(config_data.get("capture_offset", 0.0)),
            )

            yield json.dumps({"status": "progress", "message": f"Processing file: {file.filename}..."}) + "\n"

            # Save file temporarily to calculate MD5
            ext = os.path.splitext(file.filename)[1].lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                content = await file.read()
                tmp.write(content)
                tmp_path = tmp.name
            
            # Calculate MD5
            file_md5 = await asyncio.to_thread(_file_md5, tmp_path)

            source_ref_path = ""
            if minio_enabled():
                # Upload to MinIO
                object_key = minio_object_key("files", file_md5, file.filename)
                await asyncio.to_thread(minio_upload_file, tmp_path, object_key)
                source_ref_path = object_key
                # Also we can generate a presigned url if needed, but for source_ref we keep object_key usually
                # or we can rely on the frontend to know how to fetch it.
                # However, previous logic used "files/md5/filename" which maps to /static/files/...
                # If we want to maintain compatibility without fast_output, we might need to be careful.
                # Let's check how 'source_ref' is used. It's passed to 'save_artifact_by_md5'.
            else:
                # Save file permanently for preview
                fast_output_dir = os.path.join(os.getcwd(), "fast_output", "files", file_md5)
                os.makedirs(fast_output_dir, exist_ok=True)
                saved_filename = file.filename
                saved_path = os.path.join(fast_output_dir, saved_filename)
                
                import shutil
                shutil.copy2(tmp_path, saved_path)
                
                # Calculate relative path for source_ref (e.g., files/md5/filename)
                # app.py mounts fast_output as /static, so /static/files/md5/filename will be the URL
                source_ref_path = f"files/{file_md5}/{saved_filename}"
            
            # Use tmp_path for text extraction (we have it locally anyway)
            # Clean up temp file later


            yield json.dumps({"status": "progress", "message": "Extracting text content..."}) + "\n"
            
            # Extract text
            # If we uploaded to MinIO, we still have tmp_path. If we saved to fast_output, we have saved_path.
            # But we might have skipped saving to fast_output.
            # So let's rely on tmp_path for extraction which is always available here.
            text_content = await asyncio.to_thread(_extract_text, tmp_path, ext)
            
            if not text_content.strip():
                 yield json.dumps({"status": "error", "message": "Failed to extract text or file is empty."}) + "\n"
                 return

            yield json.dumps({"status": "progress", "message": "Analyzing content with LLM..."}) + "\n"

            # Call LLM
            client = AsyncOpenAI(api_key=conf.openai_api_key, base_url=conf.openai_base_url)
            
            system_prompt = (
                "You are a helpful assistant that summarizes documents. "
                "Please provide a comprehensive summary of the following content in Markdown format. "
                "Structure it with '## Summary', '## Key Points', and '## Conclusion'."
                "If the document is technical or educational, try to extract key concepts."
            )
            
            # Truncate text if too long (simple heuristic, can be improved)
            max_chars = 100000 
            truncated_text = text_content[:max_chars]
            if len(text_content) > max_chars:
                truncated_text += "\n...(content truncated)..."

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Here is the document content:\n\n{truncated_text}"}
            ]

            response = await client.chat.completions.create(
                model=conf.llm_model,
                messages=messages,
                stream=True
            )

            full_report = ""
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_report += content

            # Construct response data similar to video analysis structure for frontend compatibility
            data = {
                "summary": full_report[:200] + "...",
                "segments": [], 
                "mind_map": {}, 
                "raw_transcript": text_content # Pass full text so frontend can display it if needed
            }

            # Save to MySQL
            try:
                meta = {
                    "config": _sanitize_config(config_data),
                    "original_filename": file.filename
                }
                # Save asset and ai_analysis
                await asyncio.to_thread(save_artifact_by_md5,
                    video_md5=file_md5,
                    media_type="document",
                    asset_type="document",
                    mime_type=file.content_type,
                    display_name=file.filename,
                    source_kind="minio" if minio_enabled() else "local",
                    source_ref=source_ref_path,
                    meta=meta,
                    artifact_type="ai_analysis",
                    content_json=data
                )
                # Save report
                await asyncio.to_thread(save_artifact_by_md5,
                    video_md5=file_md5,
                    media_type="document",
                    asset_type="document",
                    source_kind="upload",
                    source_ref=file.filename,
                    meta=meta,
                    artifact_type="report_markdown",
                    content_text=full_report
                )
                # Save transcript
                await asyncio.to_thread(save_artifact_by_md5,
                    video_md5=file_md5,
                    media_type="document",
                    asset_type="document",
                    source_kind="minio" if minio_enabled() else "local",
                    source_ref=source_ref_path,
                    meta=meta,
                    artifact_type="raw_transcript",
                    content_text=text_content
                )
            except Exception as e:
                print(f"Error saving to MySQL: {e}")
            
            yield json.dumps({
                "status": "success", 
                "report": full_report,
                "data": data,
                "video_url": "", 
                "video_md5": file_md5,
                "message": "Analysis completed!"
            }) + "\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield json.dumps({"status": "error", "message": str(e)}) + "\n"
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except:
                    pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/import_file_url")
async def import_file_url(data: dict):
    url = data.get("url")
    if not url:
        return {"error": "URL is required"}
    
    # Simple download logic (supports PDF, DOCX, PPTX, TXT, MD)
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                     return {"error": f"Failed to download file: {resp.status}"}
                
                content = await resp.read()
                
                # Determine extension from URL or Content-Type
                from urllib.parse import urlparse
                path = urlparse(url).path
                ext = os.path.splitext(path)[1].lower()
                if not ext:
                    # Try to guess from content-type
                    ct = resp.headers.get('Content-Type', '').lower()
                    if 'pdf' in ct: ext = '.pdf'
                    elif 'word' in ct: ext = '.docx'
                    elif 'presentation' in ct or 'powerpoint' in ct: ext = '.pptx'
                    elif 'text' in ct: ext = '.txt'
                    elif 'markdown' in ct: ext = '.md'
                    else: ext = '.txt' # Default
                
                # Extract text
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                
                text = await asyncio.to_thread(_extract_text, tmp_path, ext)
                
                # Clean up temp file
                try:
                    os.remove(tmp_path)
                except:
                    pass
                
                return {
                    "status": "success",
                    "file_url": url, # Return original URL for PDF iframe if applicable
                    "file_content": text,
                    "file_type": ext,
                    "message": "File imported successfully"
                }
    except Exception as e:
        return {"error": str(e)}
