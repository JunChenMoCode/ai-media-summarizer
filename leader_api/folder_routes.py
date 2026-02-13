from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from .mysql_store import (
    create_folder,
    list_folders,
    update_folder,
    delete_folder,
    move_asset_to_folder
)

router = APIRouter()

class FolderCreate(BaseModel):
    name: str
    parent_id: int | None = None

class FolderUpdate(BaseModel):
    name: str | None = None
    parent_id: int | None = None

class MoveAssetRequest(BaseModel):
    folder_id: int | None

@router.post("/folders")
async def create_new_folder(folder: FolderCreate):
    try:
        folder_id = create_folder(folder.name, folder.parent_id)
        return {"status": "success", "id": folder_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/folders")
async def get_folders():
    try:
        folders = list_folders()
        # Build tree structure
        folder_map = {f["id"]: {**f, "children": []} for f in folders}
        roots = []
        for f in folders:
            node = folder_map[f["id"]]
            if f["parent_id"] and f["parent_id"] in folder_map:
                folder_map[f["parent_id"]]["children"].append(node)
            else:
                roots.append(node)
        return {"status": "success", "folders": roots}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/folders/{folder_id}")
async def update_existing_folder(folder_id: int, update: FolderUpdate):
    try:
        success = update_folder(folder_id, update.name, update.parent_id)
        if not success:
            raise HTTPException(status_code=404, detail="Folder not found or update failed")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/folders/{folder_id}")
async def delete_existing_folder(folder_id: int):
    try:
        success = delete_folder(folder_id)
        if not success:
            raise HTTPException(status_code=404, detail="Folder not found")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/assets/{video_md5}/move")
async def move_asset(video_md5: str, req: MoveAssetRequest):
    try:
        success = move_asset_to_folder(video_md5, req.folder_id)
        if not success:
             raise HTTPException(status_code=404, detail="Asset not found")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
