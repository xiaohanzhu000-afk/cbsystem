"""CB 管理接口：分页查询、增删改、图片上传。"""
import base64
import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from database import get_conn, now_str, today_str
from image_store import ALLOWED_EXT, cleanup_unreferenced, parse_urls, save_bytes
from oplog import ACTION_CB_CREATE, ACTION_CB_DELETE, ACTION_CB_UPDATE, write_log
from security import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])

MAX_IMAGES = 3
MAX_ALIASES = 20
MAX_ALIAS_LEN = 100

DATE_FORMAT = "%Y-%m-%d"


class CbPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    group_id: Optional[int] = None
    remark: str = ""
    event_date: str = ""
    aliases: List[str] = Field(default_factory=list)
    images: List[str] = Field(default_factory=list)


def _clean_images(images: List[str]) -> List[str]:
    """去重、去空、限制最多 3 张。"""
    result: List[str] = []
    for item in images or []:
        if item and item not in result:
            result.append(item)
    if len(result) > MAX_IMAGES:
        raise HTTPException(status_code=400, detail=f"图片最多只能上传 {MAX_IMAGES} 张")
    return result


def clean_aliases(aliases) -> List[str]:
    """别名：去空、去重、截断，最多 20 个。"""
    result: List[str] = []
    for item in aliases or []:
        text = str(item).strip()
        if text and text not in result:
            result.append(text[:MAX_ALIAS_LEN])
    if len(result) > MAX_ALIASES:
        raise HTTPException(status_code=400, detail=f"别名最多只能填 {MAX_ALIASES} 个")
    return result


def clean_date(value: Optional[str]) -> str:
    """把「时间」规整成 YYYY-MM-DD；留空表示用默认值。"""
    text = (value or "").strip()
    if not text:
        return ""
    for fmt in (DATE_FORMAT, "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).strftime(DATE_FORMAT)
        except ValueError:
            continue
    raise HTTPException(status_code=400, detail="时间格式不正确，应为 2026-09-16 这样的日期")


def dump_json(values: List[str]) -> str:
    return json.dumps(values, ensure_ascii=False)


def list_years(conn, table: str) -> List[int]:
    """表里「时间」字段出现过的年份，倒序；给筛选下拉框用。

    故意不带查询条件：按 2024 年筛完还要能切回 2025 年。
    """
    rows = conn.execute(
        f"""
        SELECT DISTINCT substr(event_date, 1, 4) AS year
        FROM {table}
        WHERE event_date IS NOT NULL AND event_date <> ''
        """
    ).fetchall()
    years = {int(r["year"]) for r in rows if (r["year"] or "").isdigit()}
    return sorted(years, reverse=True)


@router.post("/upload")
def upload_image(file: UploadFile = File(...)):
    """上传单张图片，返回可访问的 URL。前端粘贴图片时也走这里。"""
    content = file.file.read()
    if not content:
        raise HTTPException(status_code=400, detail="图片内容为空")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片大小不能超过 10MB")
    url = save_bytes(content, file.filename or "image.png")
    return {"url": url}


@router.post("/upload-base64")
def upload_base64(payload: dict):
    """把粘贴的 base64 图片保存为文件。"""
    data_url = payload.get("data", "")
    if not data_url:
        raise HTTPException(status_code=400, detail="图片内容为空")
    header, _, raw = data_url.partition(",")
    if not raw:
        raw = data_url
    try:
        content = base64.b64decode(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="图片解析失败")
    ext = "png"
    if "jpeg" in header or "jpg" in header:
        ext = "jpg"
    elif "gif" in header:
        ext = "gif"
    elif "webp" in header:
        ext = "webp"
    url = save_bytes(content, f"image.{ext}")
    return {"url": url}


@router.get("")
def list_cb(
    page: int = 1,
    page_size: int = 10,
    keyword: str = "",
    group_id: Optional[int] = None,
    year: Optional[int] = None,
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    where = []
    params: list = []
    if keyword.strip():
        # 别名一并参与搜索：搜名称时能搜到别名匹配的 CB
        like = f"%{keyword.strip()}%"
        where.append("(c.name LIKE ? OR c.aliases LIKE ?)")
        params += [like, like]
    if group_id:
        where.append("c.group_id = ?")
        params.append(group_id)
    if year:
        # 「时间」存的是 YYYY-MM-DD，取前四位比年份
        where.append("substr(c.event_date, 1, 4) = ?")
        params.append(str(year))
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    conn = get_conn()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM cb c {where_sql}", params
        ).fetchone()["c"]

        rows = conn.execute(
            f"""
            SELECT c.id, c.name, c.group_id, g.name AS group_name,
                   c.remark, c.event_date, c.aliases, c.images,
                   c.created_at, c.updated_at,
                   EXISTS (SELECT 1 FROM favorites f WHERE f.cb_id = c.id) AS is_favorite
            FROM cb c
            LEFT JOIN groups g ON c.group_id = g.id
            {where_sql}
            ORDER BY c.id DESC
            LIMIT ? OFFSET ?
            """,
            params + [page_size, (page - 1) * page_size],
        ).fetchall()

        items = []
        for r in rows:
            item = dict(r)
            item["images"] = parse_urls(r["images"])
            item["aliases"] = parse_urls(r["aliases"])
            item["event_date"] = r["event_date"] or ""
            item["is_favorite"] = bool(r["is_favorite"])
            items.append(item)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "years": list_years(conn, "cb"),
        }
    finally:
        conn.close()


@router.post("")
def create_cb(payload: CbPayload):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="CB 名称不能为空")
    images = _clean_images(payload.images)
    aliases = clean_aliases(payload.aliases)
    # 「时间」留空时默认取创建当天
    event_date = clean_date(payload.event_date) or today_str()

    conn = get_conn()
    try:
        if payload.group_id:
            exists = conn.execute(
                "SELECT id FROM groups WHERE id = ?", (payload.group_id,)
            ).fetchone()
            if exists is None:
                raise HTTPException(status_code=400, detail="所选分组不存在")
        created = now_str()
        cur = conn.execute(
            """
            INSERT INTO cb (name, group_id, remark, event_date, aliases, images,
                            created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                payload.group_id,
                payload.remark or "",
                event_date,
                dump_json(aliases),
                dump_json(images),
                created,
                created,
            ),
        )
        write_log(conn, ACTION_CB_CREATE, name)
        conn.commit()
        return {"id": cur.lastrowid, "success": True}
    finally:
        conn.close()


@router.put("/{cb_id}")
def update_cb(cb_id: int, payload: CbPayload):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="CB 名称不能为空")
    images = _clean_images(payload.images)
    aliases = clean_aliases(payload.aliases)

    conn = get_conn()
    try:
        exists = conn.execute(
            "SELECT id, images, event_date FROM cb WHERE id = ?", (cb_id,)
        ).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="CB 不存在")
        if payload.group_id:
            group = conn.execute(
                "SELECT id FROM groups WHERE id = ?", (payload.group_id,)
            ).fetchone()
            if group is None:
                raise HTTPException(status_code=400, detail="所选分组不存在")
        # 留空表示不改动原有时间，而不是把它清掉
        event_date = clean_date(payload.event_date) or exists["event_date"] or today_str()
        conn.execute(
            """
            UPDATE cb SET name = ?, group_id = ?, remark = ?, event_date = ?,
                          aliases = ?, images = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                name,
                payload.group_id,
                payload.remark or "",
                event_date,
                dump_json(aliases),
                dump_json(images),
                now_str(),
                cb_id,
            ),
        )
        write_log(conn, ACTION_CB_UPDATE, name)
        conn.commit()
        # 本次被移除、且已不被任何 CB / 收藏记录引用的图片，直接删除
        stale = [url for url in parse_urls(exists["images"]) if url not in images]
        cleanup_unreferenced(conn, stale)
        return {"success": True}
    finally:
        conn.close()


@router.delete("/{cb_id}")
def delete_cb(cb_id: int):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT name, images FROM cb WHERE id = ?", (cb_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="CB 不存在")
        conn.execute("DELETE FROM cb WHERE id = ?", (cb_id,))
        write_log(conn, ACTION_CB_DELETE, row["name"])
        conn.commit()
        # 收藏记录里还引用着的话会保留，两边都删掉后图片才会被清理
        cleanup_unreferenced(conn, parse_urls(row["images"]))
        return {"success": True}
    finally:
        conn.close()
