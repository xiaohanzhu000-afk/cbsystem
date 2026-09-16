"""数据备份与恢复：把业务数据打包成 .zip 数据包，或从数据包整体还原。

数据包结构::

    backup.json      业务数据（分组、CB、收藏记录、网址、站点名称）
    images/xxx.png   上述记录实际引用到的图片文件

几个刻意的取舍：

- **不含 users 表**：恢复后仍用当前账号登录，避免把自己锁在门外。
- **不含 image_dir**：图片目录属于目标机器的本地配置，由「网站设置」单独维护，
  数据包里的图片一律还原到目标机器当前配置的目录。
- **恢复是整体覆盖**：先清空 groups / cb / favorites / sites，再按数据包写入；
  过程中任何一步失败都会整体回滚，不会留下半套数据。
- **不含 operation_logs**：日志属于审计数据，恢复历史数据不该把日志一起回滚掉；
  恢复动作本身会另记一条新日志。
"""
import io
import json
import os
import zipfile
from typing import List, Optional

from database import (
    SITE_DEFAULT_STATUS,
    SITE_LEVEL_MAX,
    SITE_LEVEL_MIN,
    SITE_STATUSES,
    get_conn,
    get_image_dir,
    get_site_name,
    now_str,
)
from image_store import URL_PREFIX, cleanup_unreferenced, collect_referenced, parse_urls

BACKUP_VERSION = 1
MANIFEST_NAME = "backup.json"
IMAGE_PREFIX = "images/"

# 站点名称最长 50 字，与 routers/settings.py 保持一致
MAX_SITE_NAME_LEN = 50

GROUP_COLUMNS = ("id", "name", "sort", "created_at")
CB_COLUMNS = (
    "id",
    "name",
    "group_id",
    "remark",
    "event_date",
    "aliases",
    "images",
    "created_at",
    "updated_at",
)
FAVORITE_COLUMNS = (
    "id",
    "cb_id",
    "name",
    "group_id",
    "remark",
    "event_date",
    "aliases",
    "images",
    "created_at",
    "updated_at",
)
SITE_COLUMNS = (
    "id",
    "url",
    "event_date",
    "test_url",
    "level",
    "downloadable",
    "status",
    "remark",
    "created_at",
    "updated_at",
)

# 这两个字段在库里都是 JSON 数组，导出时统一转成可读的列表
JSON_LIST_COLUMNS = ("images", "aliases")


# --------------------------------------------------------------------------- #
# 导出
# --------------------------------------------------------------------------- #
def _rows(conn, sql: str) -> List[dict]:
    return [dict(row) for row in conn.execute(sql).fetchall()]


def build_backup() -> bytes:
    """生成数据包内容（zip 二进制）。"""
    conn = get_conn()
    try:
        groups = _rows(conn, "SELECT id, name, sort, created_at FROM groups ORDER BY id")
        cb_rows = _rows(
            conn,
            """
            SELECT id, name, group_id, remark, event_date, aliases, images,
                   created_at, updated_at
            FROM cb ORDER BY id
            """,
        )
        favorite_rows = _rows(
            conn,
            """
            SELECT id, cb_id, name, group_id, remark, event_date, aliases, images,
                   created_at, updated_at
            FROM favorites ORDER BY id
            """,
        )
        site_rows = _rows(
            conn,
            """
            SELECT id, url, event_date, test_url, level, downloadable, status,
                   remark, created_at, updated_at
            FROM sites ORDER BY id
            """,
        )
        # 只打包真正还被引用到的图片
        used = sorted(collect_referenced(conn))
    finally:
        conn.close()

    # images / aliases 存成数组，数据包可读性更好
    for row in cb_rows + favorite_rows:
        for col in JSON_LIST_COLUMNS:
            row[col] = parse_urls(row[col])

    # 「创建日期」留空的记录用创建时间补上（老数据包 / 手工导入都可能出现）
    for row in cb_rows + favorite_rows + site_rows:
        row["event_date"] = row["event_date"] or row["created_at"][:10]

    image_dir = get_image_dir()
    files = []
    for url in used:
        if not url.startswith(URL_PREFIX):
            continue
        name = os.path.basename(url)
        path = os.path.join(image_dir, name)
        if name and os.path.isfile(path):
            files.append((name, path))

    manifest = {
        "app": "cbsystem",
        "version": BACKUP_VERSION,
        "created_at": now_str(),
        "site_name": get_site_name(),
        "counts": {
            "groups": len(groups),
            "cb": len(cb_rows),
            "favorites": len(favorite_rows),
            "sites": len(site_rows),
            "images": len(files),
        },
        "groups": groups,
        "cb": cb_rows,
        "favorites": favorite_rows,
        "sites": site_rows,
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))
        for name, path in files:
            zf.write(path, IMAGE_PREFIX + name)
    return buffer.getvalue()


# --------------------------------------------------------------------------- #
# 恢复
# --------------------------------------------------------------------------- #
def _to_int(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_records(raw, columns, int_fields=(), required: str = "") -> List[dict]:
    """把数据包里的记录规整成可安全写库的字典，非法记录直接丢弃。

    ``required`` 指定哪一列不能为空（分组/CB/收藏是 ``name``，网址是 ``url``）。
    """
    if not isinstance(raw, list):
        return []

    cleaned: List[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue

        record = {}
        for col in columns:
            value = item.get(col)
            if col in int_fields:
                record[col] = _to_int(value)
            elif col in JSON_LIST_COLUMNS:
                record[col] = json.dumps(parse_urls(value), ensure_ascii=False)
            elif value is None:
                record[col] = now_str() if col.endswith("_at") else ""
            else:
                record[col] = str(value)

        # 老数据包里没有 event_date，用创建日期补上
        if "event_date" in record and not record["event_date"]:
            record["event_date"] = (record.get("created_at") or "")[:10]

        if _to_int(record["id"]) is None:
            continue  # 没有合法主键的记录无法参与关联，丢弃
        if required and not str(record.get(required) or "").strip():
            continue  # 关键列为空没有意义
        if record.get("group_id") is not None and record["group_id"] <= 0:
            record["group_id"] = None
        if "cb_id" in record and record["cb_id"] is not None and record["cb_id"] <= 0:
            record["cb_id"] = None
        cleaned.append(record)
    return cleaned


def _normalize_sites(rows: List[dict]) -> List[dict]:
    """把数据包里越界的级别 / 状态 / 是否下载收敛到合法取值。

    手工改过的数据包不该让整次恢复失败，这里静默修正而不是报错。
    """
    for row in rows:
        level = _to_int(row.get("level"))
        if level is None or not SITE_LEVEL_MIN <= level <= SITE_LEVEL_MAX:
            level = SITE_LEVEL_MIN
        row["level"] = level
        row["downloadable"] = 1 if _to_int(row.get("downloadable")) else 0
        if row.get("status") not in SITE_STATUSES:
            row["status"] = SITE_DEFAULT_STATUS
    return rows


def _read_manifest(zf: zipfile.ZipFile, names: List[str]) -> dict:
    if MANIFEST_NAME not in names:
        raise ValueError("数据包缺少 backup.json，可能不是本系统的备份文件")

    try:
        manifest = json.loads(zf.read(MANIFEST_NAME).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("数据包内容已损坏，无法解析")

    if not isinstance(manifest, dict):
        raise ValueError("数据包内容格式不正确")
    if _to_int(manifest.get("version")) != BACKUP_VERSION:
        raise ValueError(f"数据包版本不匹配，需要 v{BACKUP_VERSION} 的备份文件")
    return manifest


def _restore_images(zf: zipfile.ZipFile, image_dir: str) -> int:
    """把数据包里的图片释放到当前图片目录。

    只取 `images/` 下的文件名，`..`、绝对路径等一律丢弃，防止路径穿越。
    """
    os.makedirs(image_dir, exist_ok=True)
    restored = 0
    for info in zf.infolist():
        if info.is_dir() or not info.filename.startswith(IMAGE_PREFIX):
            continue
        name = os.path.basename(info.filename)
        if not name or name.startswith("."):
            continue
        with open(os.path.join(image_dir, name), "wb") as f:
            f.write(zf.read(info))
        restored += 1
    return restored


def _replace_data(conn, groups, cb_rows, favorite_rows, site_rows) -> None:
    """清空并写回业务数据，调用方负责 commit / rollback。"""
    group_ids = {row["id"] for row in groups}
    cb_ids = {row["id"] for row in cb_rows}

    # 分组被删掉时对应外键要能被接受
    for row in cb_rows:
        if row["group_id"] not in group_ids:
            row["group_id"] = None

    seen_cb_ids = set()
    for row in favorite_rows:
        if row["group_id"] not in group_ids:
            row["group_id"] = None
        if row["cb_id"] not in cb_ids:
            row["cb_id"] = None
        elif row["cb_id"] in seen_cb_ids:
            # cb_id 有唯一约束，重复的降级成「手工收藏」
            row["cb_id"] = None
        else:
            seen_cb_ids.add(row["cb_id"])

    conn.execute("DELETE FROM favorites")
    conn.execute("DELETE FROM cb")
    conn.execute("DELETE FROM groups")
    conn.execute("DELETE FROM sites")
    try:
        # 让自增 id 从备份里的最大值重新开始
        conn.execute(
            "DELETE FROM sqlite_sequence WHERE name IN ('groups', 'cb', 'favorites', 'sites')"
        )
    except Exception:
        pass

    conn.executemany(
        "INSERT INTO groups (id, name, sort, created_at) VALUES (?, ?, ?, ?)",
        [(r["id"], r["name"], r["sort"] or 0, r["created_at"]) for r in groups],
    )
    conn.executemany(
        """
        INSERT INTO cb (id, name, group_id, remark, event_date, aliases, images,
                        created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                r["id"],
                r["name"],
                r["group_id"],
                r["remark"],
                r["event_date"],
                r["aliases"],
                r["images"],
                r["created_at"],
                r["updated_at"],
            )
            for r in cb_rows
        ],
    )
    conn.executemany(
        """
        INSERT INTO favorites (id, cb_id, name, group_id, remark, event_date, aliases,
                               images, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                r["id"],
                r["cb_id"],
                r["name"],
                r["group_id"],
                r["remark"],
                r["event_date"],
                r["aliases"],
                r["images"],
                r["created_at"],
                r["updated_at"],
            )
            for r in favorite_rows
        ],
    )
    conn.executemany(
        """
        INSERT INTO sites (id, url, event_date, test_url, level, downloadable, status,
                           remark, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                r["id"],
                r["url"],
                r["event_date"],
                r["test_url"],
                r["level"],
                r["downloadable"],
                r["status"],
                r["remark"],
                r["created_at"],
                r["updated_at"],
            )
            for r in site_rows
        ],
    )


def restore_backup(raw: bytes) -> dict:
    """用数据包整体覆盖当前数据，返回统计信息。数据不合法时抛 ValueError。"""
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise ValueError("文件不是有效的 zip 数据包")
    except Exception:
        raise ValueError("数据包无法读取，请确认文件完整")

    with zf:
        manifest = _read_manifest(zf, zf.namelist())
        groups = _clean_records(
            manifest.get("groups"), GROUP_COLUMNS, {"id", "sort"}, required="name"
        )
        cb_rows = _clean_records(
            manifest.get("cb"), CB_COLUMNS, {"id", "group_id"}, required="name"
        )
        favorite_rows = _clean_records(
            manifest.get("favorites"),
            FAVORITE_COLUMNS,
            {"id", "cb_id", "group_id"},
            required="name",
        )
        # 旧版数据包里没有 sites，取不到就是空列表（整体覆盖，因此网址会被清空）
        site_rows = _normalize_sites(
            _clean_records(
                manifest.get("sites"),
                SITE_COLUMNS,
                {"id", "level", "downloadable"},
                required="url",
            )
        )
        restored_images = _restore_images(zf, get_image_dir())

    conn = get_conn()
    try:
        # 恢复前的图片在覆盖后多半已无人引用，稍后一并清理
        old_images = list(collect_referenced(conn))
        _replace_data(conn, groups, cb_rows, favorite_rows, site_rows)

        name = str(manifest.get("site_name") or "").strip()
        if name:
            # 这里必须复用 conn：set_setting() 会另开一条连接，
            # 而当前连接还握着未提交的写事务，会直接 database is locked。
            conn.execute(
                """
                INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                               updated_at = excluded.updated_at
                """,
                ("site_name", name[:MAX_SITE_NAME_LEN], now_str()),
            )

        conn.commit()
        removed = cleanup_unreferenced(conn, old_images)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "success": True,
        "site_name": get_site_name(),
        "groups": len(groups),
        "cb": len(cb_rows),
        "favorites": len(favorite_rows),
        "sites": len(site_rows),
        "images": restored_images,
        "removed": len(removed),
    }


__all__ = ["BACKUP_VERSION", "build_backup", "restore_backup"]
