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
        CREATE TABLE IF NOT EXISTS media_assets (
          id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
          md5 CHAR(32) NOT NULL,
          asset_type VARCHAR(32) NOT NULL DEFAULT '',
          mime_type VARCHAR(128) NULL,
          display_name VARCHAR(255) NULL,
          is_read TINYINT(1) NOT NULL DEFAULT 0,
          media_type VARCHAR(16) NOT NULL DEFAULT '',
          source_kind VARCHAR(16) NOT NULL DEFAULT '',
          source_ref VARCHAR(1024) NULL,
          meta_json JSON NULL,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          UNIQUE KEY uq_media_assets_md5 (md5)
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
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
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
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT
                  a.md5,
                  a.asset_type,
                  a.mime_type,
                  a.display_name,
                  a.is_read,
                  a.media_type,
                  a.source_kind,
                  a.source_ref,
                  a.meta_json,
                  a.created_at,
                  a.updated_at,
                  ar.content_json
                FROM media_assets a
                JOIN media_artifacts ar ON ar.asset_id = a.id
                WHERE ar.artifact_type = :artifact_type
                ORDER BY a.updated_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {"artifact_type": a_type, "limit": lim, "offset": off},
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