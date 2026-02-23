import json
import os
from datetime import datetime


def _mysql_dsn() -> str:
    host = (os.getenv("MYSQL_HOST", "") or "127.0.0.1").strip()
    port = int(os.getenv("MYSQL_PORT", "3306") or "3306")
    user = (os.getenv("MYSQL_USER", "") or "root").strip()
    password = os.getenv("MYSQL_PASSWORD", "") or "root"
    db = (os.getenv("MYSQL_DATABASE", "") or "zongjie").strip()
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}?charset=utf8mb4"


def mysql_enabled() -> bool:
    v = (os.getenv("MYSQL_ENABLED", "") or "").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    return True


_ENGINE = None
_INITED = False


def mysql_engine():
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE
    try:
        from sqlalchemy import create_engine
    except Exception as e:
        raise RuntimeError("缺少 sqlalchemy 依赖，请先安装 requirements.txt") from e
    try:
        import pymysql  # noqa: F401
    except Exception as e:
        raise RuntimeError("缺少 pymysql 依赖，请先安装 requirements.txt") from e

    _ENGINE = create_engine(
        _mysql_dsn(),
        pool_pre_ping=True,
        pool_recycle=3600,
        future=True,
    )
    return _ENGINE


def _mysql_db_name() -> str:
    db = (os.getenv("MYSQL_DATABASE", "") or "zongjie").strip()
    return db or "zongjie"


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    from sqlalchemy import text

    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = :db
            AND table_name = :table
            AND column_name = :col
            LIMIT 1
            """
        ),
        {"db": _mysql_db_name(), "table": table_name, "col": column_name},
    ).first()
    return bool(row)


def _migrate_schema(conn) -> None:
    from sqlalchemy import text

    alters: list[str] = []

    if not _column_exists(conn, "media_assets", "asset_type"):
        alters.append("ALTER TABLE media_assets ADD COLUMN asset_type VARCHAR(32) NOT NULL DEFAULT '' AFTER md5")
    if not _column_exists(conn, "media_assets", "mime_type"):
        alters.append("ALTER TABLE media_assets ADD COLUMN mime_type VARCHAR(128) NULL AFTER asset_type")
    if not _column_exists(conn, "media_assets", "display_name"):
        alters.append("ALTER TABLE media_assets ADD COLUMN display_name VARCHAR(255) NULL AFTER mime_type")
    if not _column_exists(conn, "media_assets", "is_read"):
        alters.append("ALTER TABLE media_assets ADD COLUMN is_read TINYINT(1) NOT NULL DEFAULT 0 AFTER display_name")
    if not _column_exists(conn, "media_assets", "folder_id"):
        alters.append("ALTER TABLE media_assets ADD COLUMN folder_id BIGINT UNSIGNED NULL AFTER is_read")
        alters.append("ALTER TABLE media_assets ADD CONSTRAINT fk_media_assets_folder_id FOREIGN KEY (folder_id) REFERENCES media_folders(id) ON DELETE SET NULL")

    if not _column_exists(conn, "media_artifacts", "meta_json"):
        alters.append("ALTER TABLE media_artifacts ADD COLUMN meta_json JSON NULL AFTER content_json")

    for stmt in alters:
        conn.execute(text(stmt))


def mysql_init() -> None:
    global _INITED
    if _INITED:
        return
    if not mysql_enabled():
        _INITED = True
        return

    from sqlalchemy import text

    engine = mysql_engine()
    ddl = [
        """
        CREATE TABLE IF NOT EXISTS app_config (
          id INT NOT NULL PRIMARY KEY,
          config_json JSON NULL,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS media_folders (
          id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
          parent_id BIGINT UNSIGNED NULL,
          name VARCHAR(255) NOT NULL,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          KEY idx_media_folders_parent_id (parent_id),
          CONSTRAINT fk_media_folders_parent_id FOREIGN KEY (parent_id) REFERENCES media_folders(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS media_assets (
          id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
          md5 CHAR(32) NOT NULL,
          asset_type VARCHAR(32) NOT NULL DEFAULT '',
          mime_type VARCHAR(128) NULL,
          display_name VARCHAR(255) NULL,
          is_read TINYINT(1) NOT NULL DEFAULT 0,
          folder_id BIGINT UNSIGNED NULL,
          media_type VARCHAR(16) NOT NULL DEFAULT '',
          source_kind VARCHAR(16) NOT NULL DEFAULT '',
          source_ref VARCHAR(1024) NULL,
          meta_json JSON NULL,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          UNIQUE KEY uq_media_assets_md5 (md5),
          KEY idx_media_assets_folder_id (folder_id),
          CONSTRAINT fk_media_assets_folder_id FOREIGN KEY (folder_id) REFERENCES media_folders(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS media_artifacts (
          id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
          asset_id BIGINT UNSIGNED NOT NULL,
          artifact_type VARCHAR(32) NOT NULL,
          artifact_version INT NOT NULL DEFAULT 1,
          content_text LONGTEXT NULL,
          content_json JSON NULL,
          meta_json JSON NULL,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          UNIQUE KEY uq_media_artifacts_asset_type_ver (asset_id, artifact_type, artifact_version),
          KEY idx_media_artifacts_asset_id (asset_id),
          CONSTRAINT fk_media_artifacts_asset_id FOREIGN KEY (asset_id) REFERENCES media_assets(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS task_queue (
          id VARCHAR(36) NOT NULL PRIMARY KEY,
          url TEXT NOT NULL,
          task_type VARCHAR(32) NOT NULL DEFAULT 'video',
          status VARCHAR(32) NOT NULL DEFAULT 'pending',
          progress INT NOT NULL DEFAULT 0,
          created_at DOUBLE NOT NULL,
          result_json JSON NULL,
          error_msg TEXT NULL,
          config_json JSON NULL,
          logs_json JSON NULL,
          updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
    ]

    with engine.begin() as conn:
        for stmt in ddl:
            conn.execute(text(stmt))
        _migrate_schema(conn)

    _INITED = True


def _json_or_none(v):
    if v is None:
        return None
    try:
        return json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return json.dumps({"_raw": str(v)}, ensure_ascii=False, separators=(",", ":"))


def _sanitize_config(config: dict) -> dict:
    if not isinstance(config, dict):
        return {}
    clean = dict(config)
    for k in ("openai_api_key", "vl_api_key"):
        if k in clean:
            clean[k] = ""
    return clean


def save_app_config(config: dict) -> None:
    if not mysql_enabled():
        raise RuntimeError("MySQL 未启用")
    mysql_init()
    from sqlalchemy import text
    engine = mysql_engine()
    cfg_json = _json_or_none(config)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO app_config (id, config_json, created_at, updated_at)
                VALUES (1, CAST(:config_json AS JSON), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                  config_json = VALUES(config_json),
                  updated_at = CURRENT_TIMESTAMP
                """
            ),
            {"config_json": cfg_json},
        )


def load_app_config() -> dict:
    if not mysql_enabled():
        raise RuntimeError("MySQL 未启用")
    mysql_init()
    from sqlalchemy import text
    engine = mysql_engine()
    with engine.begin() as conn:
        row = conn.execute(text("SELECT config_json FROM app_config WHERE id=1")).first()
    if not row:
        return {}
    cfg = row[0]
    if isinstance(cfg, str):
        try:
            cfg = json.loads(cfg)
        except Exception:
            cfg = {}
    if not isinstance(cfg, dict):
        cfg = {}
    return cfg


def save_artifact_by_md5(
    video_md5: str,
    *,
    media_type: str = "",
    asset_type: str = "",
    mime_type: str | None = None,
    display_name: str | None = None,
    source_kind: str = "",
    source_ref: str | None = None,
    meta: dict | None = None,
    artifact_type: str,
    artifact_version: int = 1,
    content_text: str | None = None,
    content_json: dict | None = None,
    artifact_meta: dict | None = None,
) -> None:
    if not mysql_enabled():
        return

    mysql_init()

    md5 = (video_md5 or "").strip().lower()
    if len(md5) != 32:
        raise ValueError("video_md5 必须是 32 位 md5")

    from sqlalchemy import text

    engine = mysql_engine()
    meta_json = _json_or_none(meta)
    content_json_str = _json_or_none(content_json)
    artifact_meta_json = _json_or_none(artifact_meta)

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO media_assets (
                  md5, asset_type, mime_type, display_name, media_type, source_kind, source_ref, meta_json, created_at, updated_at
                )
                VALUES (
                  :md5, :asset_type, :mime_type, :display_name, :media_type, :source_kind, :source_ref,
                  CAST(:meta_json AS JSON), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                ON DUPLICATE KEY UPDATE
                  asset_type = COALESCE(NULLIF(VALUES(asset_type), ''), asset_type),
                  mime_type = COALESCE(VALUES(mime_type), mime_type),
                  display_name = COALESCE(VALUES(display_name), display_name),
                  media_type = COALESCE(NULLIF(VALUES(media_type), ''), media_type),
                  source_kind = COALESCE(NULLIF(VALUES(source_kind), ''), source_kind),
                  source_ref = COALESCE(VALUES(source_ref), source_ref),
                  meta_json = COALESCE(VALUES(meta_json), meta_json),
                  updated_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "md5": md5,
                "asset_type": (asset_type or "").strip(),
                "mime_type": mime_type,
                "display_name": display_name,
                "media_type": (media_type or "").strip(),
                "source_kind": (source_kind or "").strip(),
                "source_ref": source_ref,
                "meta_json": meta_json,
            },
        )

        asset_id = conn.execute(text("SELECT id FROM media_assets WHERE md5=:md5"), {"md5": md5}).scalar_one()

        conn.execute(
            text(
                """
                INSERT INTO media_artifacts (
                  asset_id, artifact_type, artifact_version, content_text, content_json, meta_json, created_at, updated_at
                )
                VALUES (
                  :asset_id, :artifact_type, :artifact_version, :content_text,
                  CAST(:content_json AS JSON),
                  CAST(:artifact_meta_json AS JSON),
                  CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                ON DUPLICATE KEY UPDATE
                  content_text = VALUES(content_text),
                  content_json = COALESCE(VALUES(content_json), content_json),
                  meta_json = COALESCE(VALUES(meta_json), meta_json),
                  updated_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "asset_id": int(asset_id),
                "artifact_type": (artifact_type or "").strip(),
                "artifact_version": int(artifact_version or 1),
                "content_text": content_text,
                "content_json": content_json_str,
                "artifact_meta_json": artifact_meta_json,
            },
        )


def append_artifact_event_by_md5(
    video_md5: str,
    *,
    media_type: str = "",
    asset_type: str = "",
    mime_type: str | None = None,
    display_name: str | None = None,
    source_kind: str = "",
    source_ref: str | None = None,
    meta: dict | None = None,
    artifact_type: str,
    content_text: str | None = None,
    content_json: dict | None = None,
    artifact_meta: dict | None = None,
) -> int:
    if not mysql_enabled():
        return 0

    mysql_init()

    md5 = (video_md5 or "").strip().lower()
    if len(md5) != 32:
        raise ValueError("video_md5 必须是 32 位 md5")

    from sqlalchemy import text

    engine = mysql_engine()
    meta_json = _json_or_none(meta)
    content_json_str = _json_or_none(content_json)
    artifact_meta_json = _json_or_none(artifact_meta)

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO media_assets (
                  md5, asset_type, mime_type, display_name, media_type, source_kind, source_ref, meta_json, created_at, updated_at
                )
                VALUES (
                  :md5, :asset_type, :mime_type, :display_name, :media_type, :source_kind, :source_ref,
                  CAST(:meta_json AS JSON), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                ON DUPLICATE KEY UPDATE
                  asset_type = COALESCE(NULLIF(VALUES(asset_type), ''), asset_type),
                  mime_type = COALESCE(VALUES(mime_type), mime_type),
                  display_name = COALESCE(VALUES(display_name), display_name),
                  media_type = COALESCE(NULLIF(VALUES(media_type), ''), media_type),
                  source_kind = COALESCE(NULLIF(VALUES(source_kind), ''), source_kind),
                  source_ref = COALESCE(VALUES(source_ref), source_ref),
                  meta_json = COALESCE(VALUES(meta_json), meta_json),
                  updated_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "md5": md5,
                "asset_type": (asset_type or "").strip(),
                "mime_type": mime_type,
                "display_name": display_name,
                "media_type": (media_type or "").strip(),
                "source_kind": (source_kind or "").strip(),
                "source_ref": source_ref,
                "meta_json": meta_json,
            },
        )
        asset_id = conn.execute(text("SELECT id FROM media_assets WHERE md5=:md5"), {"md5": md5}).scalar_one()
        max_ver = conn.execute(
            text(
                """
                SELECT MAX(artifact_version)
                FROM media_artifacts
                WHERE asset_id=:asset_id AND artifact_type=:artifact_type
                """
            ),
            {"asset_id": int(asset_id), "artifact_type": (artifact_type or "").strip()},
        ).scalar_one()
        next_ver = int(max_ver or 0) + 1
        conn.execute(
            text(
                """
                INSERT INTO media_artifacts (
                  asset_id, artifact_type, artifact_version, content_text, content_json, meta_json, created_at, updated_at
                )
                VALUES (
                  :asset_id, :artifact_type, :artifact_version, :content_text,
                  CAST(:content_json AS JSON),
                  CAST(:artifact_meta_json AS JSON),
                  CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "asset_id": int(asset_id),
                "artifact_type": (artifact_type or "").strip(),
                "artifact_version": next_ver,
                "content_text": content_text,
                "content_json": content_json_str,
                "artifact_meta_json": artifact_meta_json,
            },
        )
        return next_ver


def load_latest_by_md5(video_md5: str) -> dict | None:
    if not mysql_enabled():
        return None

    mysql_init()

    md5 = (video_md5 or "").strip().lower()
    if len(md5) != 32:
        raise ValueError("video_md5 必须是 32 位 md5")

    from sqlalchemy import text

    engine = mysql_engine()
    with engine.begin() as conn:
        asset = conn.execute(
            text(
                """
                SELECT id, md5, media_type, source_kind, source_ref, meta_json, created_at, updated_at
                FROM media_assets
                WHERE md5=:md5
                """
            ),
            {"md5": md5},
        ).mappings().first()
        if not asset:
            return None
        rows = conn.execute(
            text(
                """
                SELECT artifact_type, artifact_version, content_text, content_json, meta_json, created_at, updated_at
                FROM media_artifacts
                WHERE asset_id=:asset_id
                ORDER BY artifact_type ASC, artifact_version DESC
                """
            ),
            {"asset_id": asset["id"]},
        ).mappings().all()

    artifacts = {}
    for r in rows:
        t = r["artifact_type"]
        if t not in artifacts:
            artifacts[t] = []
        
        cj = r["content_json"]
        if isinstance(cj, str):
            try:
                cj = json.loads(cj)
            except Exception:
                pass

        mj = r.get("meta_json")
        if isinstance(mj, str):
            try:
                mj = json.loads(mj)
            except Exception:
                pass

        artifacts[t].append(
            {
                "version": r["artifact_version"],
                "text": r["content_text"],
                "json": cj,
                "meta": mj,
                "created_at": str(r["created_at"]),
                "updated_at": str(r["updated_at"]),
            }
        )

    mj_asset = asset["meta_json"]
    if isinstance(mj_asset, str):
        try:
            mj_asset = json.loads(mj_asset)
        except Exception:
            pass

    return {
        "asset": {
            "md5": asset["md5"],
            "asset_type": asset.get("asset_type", ""),
            "mime_type": asset.get("mime_type"),
            "display_name": asset.get("display_name"),
            "media_type": asset["media_type"],
            "source_kind": asset["source_kind"],
            "source_ref": asset["source_ref"],
            "meta": mj_asset,
            "created_at": str(asset["created_at"]),
            "updated_at": str(asset["updated_at"]),
        },
        "artifacts": artifacts,
    }


def mark_asset_as_read(video_md5: str) -> bool:
    if not mysql_enabled():
        return False
    
    mysql_init()
    md5 = (video_md5 or "").strip().lower()
    if not md5:
        return False

    from sqlalchemy import text
    engine = mysql_engine()
    
    with engine.begin() as conn:
        result = conn.execute(
            text("UPDATE media_assets SET is_read = 1 WHERE md5 = :md5"),
            {"md5": md5}
        )
        return result.rowcount > 0


def list_assets_with_artifact(
    *,
    artifact_type: str = "ai_analysis",
    limit: int = 50,
    offset: int = 0,
    folder_id: int | str | None = None
) -> list[dict]:
    if not mysql_enabled():
        return []

    mysql_init()

    from sqlalchemy import text

    lim = max(1, min(int(limit or 50), 200))
    off = max(0, int(offset or 0))
    a_type = (artifact_type or "").strip()
    if not a_type:
        a_type = "ai_analysis"

    engine = mysql_engine()
    
    where_clauses = ["ar.artifact_type = :artifact_type"]
    params = {"artifact_type": a_type, "limit": lim, "offset": off}
    
    if folder_id is not None:
        if str(folder_id).lower() in ("null", "uncategorized", "none"):
            where_clauses.append("a.folder_id IS NULL")
        else:
            try:
                fid = int(folder_id)
                where_clauses.append("a.folder_id = :folder_id")
                params["folder_id"] = fid
            except:
                pass # Ignore invalid folder_id

    where_sql = " AND ".join(where_clauses)

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT
                  a.md5,
                  a.asset_type,
                  a.mime_type,
                  a.display_name,
                  a.is_read,
                  a.folder_id,
                  a.media_type,
                  a.source_kind,
                  a.source_ref,
                  a.meta_json,
                  a.created_at,
                  a.updated_at,
                  ar.content_json
                FROM media_assets a
                JOIN media_artifacts ar ON ar.asset_id = a.id
                WHERE {where_sql}
                ORDER BY a.updated_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()

    out: list[dict] = []
    for r in rows:
        cj = r.get("content_json")
        if isinstance(cj, str):
            try:
                cj = json.loads(cj)
            except Exception:
                pass

        mj = r.get("meta_json")
        if isinstance(mj, str):
            try:
                mj = json.loads(mj)
            except Exception:
                pass

        out.append(
            {
                "md5": r.get("md5"),
                "asset_type": r.get("asset_type", ""),
                "mime_type": r.get("mime_type"),
                "display_name": r.get("display_name"),
                "is_read": bool(r.get("is_read") or 0),
                "folder_id": r.get("folder_id"),
                "media_type": r.get("media_type", ""),
                "source_kind": r.get("source_kind", ""),
                "source_ref": r.get("source_ref"),
                "meta": mj,
                "created_at": str(r.get("created_at")),
                "updated_at": str(r.get("updated_at")),
                "content_json": cj,
            }
        )
    return out


def delete_asset_by_md5(video_md5: str) -> bool:
    if not mysql_enabled():
        return False

    mysql_init()
    md5 = (video_md5 or "").strip().lower()
    if not md5:
        return False

    from sqlalchemy import text
    engine = mysql_engine()
    
    with engine.begin() as conn:
        # First get asset id
        row = conn.execute(
            text("SELECT id FROM media_assets WHERE md5=:md5"),
            {"md5": md5}
        ).first()
        
        if not row:
            return False
            
        asset_id = row[0]
        
        # Delete artifacts first (foreign key usually handles this but let's be explicit if needed, 
        # though usually ON DELETE CASCADE is preferred. Assuming standard setup.)
        # If no cascade, we must delete child rows.
        conn.execute(
            text("DELETE FROM media_artifacts WHERE asset_id=:asset_id"),
            {"asset_id": asset_id}
        )
        
        # Delete asset
        conn.execute(
            text("DELETE FROM media_assets WHERE id=:asset_id"),
            {"asset_id": asset_id}
        )
        
    return True


def move_asset_to_folder(video_md5: str, folder_id: int | None) -> bool:
    if not mysql_enabled():
        return False
    mysql_init()
    
    from sqlalchemy import text
    engine = mysql_engine()
    with engine.begin() as conn:
        res = conn.execute(
            text("UPDATE media_assets SET folder_id = :folder_id WHERE md5 = :md5"),
            {"folder_id": folder_id, "md5": video_md5}
        )
        return res.rowcount > 0


def get_all_analysis_tags() -> list[dict]:
    if not mysql_enabled():
        return []
    mysql_init()

    from sqlalchemy import text
    engine = mysql_engine()

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT content_json
                FROM media_artifacts
                WHERE artifact_type = 'ai_analysis'
                """
            )
        ).mappings().all()

    tag_counts = {}
    for r in rows:
        cj = r["content_json"]
        if isinstance(cj, str):
            try:
                cj = json.loads(cj)
            except Exception:
                continue

        if isinstance(cj, dict):
            tags = cj.get("tags")
            if isinstance(tags, list):
                for t in tags:
                    if isinstance(t, str):
                        t_str = t.strip()
                        if t_str:
                            tag_counts[t_str] = tag_counts.get(t_str, 0) + 1
    
    result = [
        {"name": k, "value": v}
        for k, v in tag_counts.items()
    ]
    result.sort(key=lambda x: x["value"], reverse=True)
    return result


# Folder methods

def create_folder(name: str, parent_id: int | None = None) -> int:
    if not mysql_enabled():
        return 0
    mysql_init()
    
    from sqlalchemy import text
    engine = mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                INSERT INTO media_folders (name, parent_id, created_at, updated_at)
                VALUES (:name, :parent_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {"name": name, "parent_id": parent_id},
        )
        return result.lastrowid


def list_folders() -> list[dict]:
    if not mysql_enabled():
        return []
    mysql_init()
    
    from sqlalchemy import text
    engine = mysql_engine()
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT id, parent_id, name, created_at, updated_at FROM media_folders ORDER BY name ASC")
        ).mappings().all()
        
    return [
        {
            "id": r["id"],
            "parent_id": r["parent_id"],
            "name": r["name"],
            "created_at": str(r["created_at"]),
            "updated_at": str(r["updated_at"]),
        }
        for r in rows
    ]


def update_folder(folder_id: int, name: str | None = None, parent_id: int | None = None) -> bool:
    if not mysql_enabled():
        return False
    mysql_init()
    
    from sqlalchemy import text
    engine = mysql_engine()
    
    updates = []
    params = {"id": folder_id}
    
    if name is not None:
        updates.append("name = :name")
        params["name"] = name
    if parent_id is not None:
        if parent_id == folder_id:
             return False
        updates.append("parent_id = :parent_id")
        params["parent_id"] = parent_id
        
    if not updates:
        return False
        
    updates.append("updated_at = CURRENT_TIMESTAMP")
    sql = f"UPDATE media_folders SET {', '.join(updates)} WHERE id = :id"
    
    with engine.begin() as conn:
        res = conn.execute(text(sql), params)
        return res.rowcount > 0


def delete_folder(folder_id: int) -> bool:
    if not mysql_enabled():
        return False
    mysql_init()
    
    from sqlalchemy import text
    engine = mysql_engine()
    
    with engine.begin() as conn:
        res = conn.execute(
            text("DELETE FROM media_folders WHERE id = :id"),
            {"id": folder_id}
        )
        return res.rowcount > 0


def db_add_task(
    task_id: str,
    url: str,
    task_type: str = "video",
    created_at: float = 0.0,
    config: dict | None = None,
) -> None:
    if not mysql_enabled():
        return
    mysql_init()
    
    from sqlalchemy import text
    engine = mysql_engine()
    
    config_json = _json_or_none(config)
    
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO task_queue (
                  id, url, task_type, status, progress, created_at, config_json, updated_at
                )
                VALUES (
                  :id, :url, :task_type, 'pending', 0, :created_at, CAST(:config_json AS JSON), CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "id": task_id,
                "url": url,
                "task_type": task_type,
                "created_at": created_at,
                "config_json": config_json,
            },
        )


def db_get_all_tasks(limit: int = 100, offset: int = 0) -> list[dict]:
    if not mysql_enabled():
        return []
    mysql_init()
    
    from sqlalchemy import text
    engine = mysql_engine()
    
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, url, task_type, status, progress, created_at, result_json, error_msg, config_json, logs_json, updated_at
                FROM task_queue
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {"limit": limit, "offset": offset}
        ).mappings().all()
        
    out = []
    for r in rows:
        cfg = r["config_json"]
        if isinstance(cfg, str):
            try:
                cfg = json.loads(cfg)
            except:
                pass
                
        res = r["result_json"]
        if isinstance(res, str):
            try:
                res = json.loads(res)
            except:
                pass
                
        logs = r["logs_json"]
        if isinstance(logs, str):
            try:
                logs = json.loads(logs)
            except:
                logs = []
        if not isinstance(logs, list):
            logs = []
            
        out.append({
            "id": r["id"],
            "url": r["url"],
            "type": r["task_type"],
            "status": r["status"],
            "progress": r["progress"],
            "created_at": r["created_at"],
            "result": res,
            "error": r["error_msg"],
            "config": cfg,
            "logs": logs,
        })
    return out


def db_count_tasks() -> int:
    if not mysql_enabled():
        return 0
    mysql_init()
    
    from sqlalchemy import text
    engine = mysql_engine()
    
    with engine.begin() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM task_queue")
        ).scalar()
        
    return count or 0


def db_get_task(task_id: str) -> dict | None:
    if not mysql_enabled():
        return None
    mysql_init()
    
    from sqlalchemy import text
    engine = mysql_engine()
    
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT id, url, task_type, status, progress, created_at, result_json, error_msg, config_json, logs_json, updated_at
                FROM task_queue
                WHERE id = :id
                """
            ),
            {"id": task_id}
        ).mappings().first()
        
    if not row:
        return None
        
    cfg = row["config_json"]
    if isinstance(cfg, str):
        try:
            cfg = json.loads(cfg)
        except:
            pass
            
    res = row["result_json"]
    if isinstance(res, str):
        try:
            res = json.loads(res)
        except:
            pass
            
    logs = row["logs_json"]
    if isinstance(logs, str):
        try:
            logs = json.loads(logs)
        except:
            logs = []
    if not isinstance(logs, list):
        logs = []
        
    return {
        "id": row["id"],
        "url": row["url"],
        "type": row["task_type"],
        "status": row["status"],
        "progress": row["progress"],
        "created_at": row["created_at"],
        "result": res,
        "error": row["error_msg"],
        "config": cfg,
        "logs": logs,
    }


def db_update_task(
    task_id: str,
    status: str | None = None,
    progress: int | None = None,
    result: dict | None = None,
    error: str | None = None,
    logs: list[str] | None = None,
) -> bool:
    if not mysql_enabled():
        return False
    mysql_init()
    
    from sqlalchemy import text
    engine = mysql_engine()
    
    updates = []
    params = {"id": task_id}
    
    if status is not None:
        updates.append("status = :status")
        params["status"] = status
    if progress is not None:
        updates.append("progress = :progress")
        params["progress"] = progress
    if result is not None:
        updates.append("result_json = CAST(:result_json AS JSON)")
        params["result_json"] = _json_or_none(result)
    if error is not None:
        updates.append("error_msg = :error")
        params["error"] = error
    if logs is not None:
        updates.append("logs_json = CAST(:logs_json AS JSON)")
        params["logs_json"] = _json_or_none(logs)
        
    if not updates:
        return False
        
    updates.append("updated_at = CURRENT_TIMESTAMP")
    sql = f"UPDATE task_queue SET {', '.join(updates)} WHERE id = :id"
    
    with engine.begin() as conn:
        res = conn.execute(text(sql), params)
        return res.rowcount > 0


def db_delete_task(task_id: str) -> bool:
    if not mysql_enabled():
        return False
    mysql_init()
    
    from sqlalchemy import text
    engine = mysql_engine()
    
    with engine.begin() as conn:
        res = conn.execute(
            text("DELETE FROM task_queue WHERE id = :id"),
            {"id": task_id}
        )
        return res.rowcount > 0
