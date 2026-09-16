"""收藏记录接口：与 CB 管理功能一致（分页查询、增删改），另提供收藏 / 取消收藏切换。

收藏态以 `cb_id` 建立关联：一个 CB 最多对应一条收藏记录，
再次点击「取消收藏」即删除该记录，CB 列表中的收藏状态随之消失。
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from database import get_conn, now_str, today_str
from image_store import cleanup_unreferenced, parse_urls
from oplog import (
    ACTION_FAVORITE,
    ACTION_FAVORITE_CREATE,
    ACTION_FAVORITE_DELETE,
    ACTION_FAVORITE_UPDATE,
    ACTION_UNFAVORITE,
    write_log,
)
from routers.cb import _clean_images, clean_aliases, clean_date, dump_json, list_years
from security import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])


class FavoritePayload(BaseModel):
    """新增 / 修改收藏记录。cb_id 仅新增时可传，用于标记来源 CB。"""

    cb_id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=200)
    group_id: Optional[int] = None
    remark: str = ""
    event_date: str = ""
    aliases: List[str] = Field(default_factory=list)
    images: List[str] = Field(default_factory=list)


class TogglePayload(BaseModel):
    cb_id: int


def _decode(row) -> dict:
    item = dict(row)
    item["images"] = parse_urls(row["images"])
    item["aliases"] = parse_urls(row["aliases"])
    item["event_date"] = row["event_date"] or ""
    return item


def _check_group(conn, group_id: Optional[int]) -> None:
    if not group_id:
        return
    exists = conn.execute("SELECT id FROM groups WHERE id = ?", (group_id,)).fetchone()
    if exists is None:
        raise HTTPException(status_code=400, detail="所选分组不存在")


@router.get("")
def list_favorites(
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
        # 别名一并参与搜索
        like = f"%{keyword.strip()}%"
        where.append("(f.name LIKE ? OR f.aliases LIKE ?)")
        params += [like, like]
    if group_id:
        where.append("f.group_id = ?")
        params.append(group_id)
    if year:
        # 「时间」存的是 YYYY-MM-DD，取前四位比年份
        where.append("substr(f.event_date, 1, 4) = ?")
        params.append(str(year))
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    conn = get_conn()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM favorites f {where_sql}", params
        ).fetchone()["c"]

        rows = conn.execute(
            f"""
            SELECT f.id, f.cb_id, f.name, f.group_id, g.name AS group_name,
                   f.remark, f.event_date, f.aliases, f.images,
                   f.created_at, f.updated_at
            FROM favorites f
            LEFT JOIN groups g ON f.group_id = g.id
            {where_sql}
            ORDER BY f.id DESC
            LIMIT ? OFFSET ?
            """,
            params + [page_size, (page - 1) * page_size],
        ).fetchall()

        return {
            "items": [_decode(r) for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "years": list_years(conn, "favorites"),
        }
    finally:
        conn.close()


@router.post("/toggle")
def toggle_favorite(payload: TogglePayload):
    """收藏 / 取消收藏。已收藏则删除记录，未收藏则复制一份 CB 数据到收藏记录。"""
    conn = get_conn()
    try:
        cb = conn.execute("SELECT * FROM cb WHERE id = ?", (payload.cb_id,)).fetchone()
        if cb is None:
            raise HTTPException(status_code=404, detail="CB 不存在")

        existing = conn.execute(
            "SELECT id, images FROM favorites WHERE cb_id = ?", (payload.cb_id,)
        ).fetchone()
        if existing is not None:
            conn.execute("DELETE FROM favorites WHERE id = ?", (existing["id"],))
            write_log(conn, ACTION_UNFAVORITE, cb["name"])
            conn.commit()
            # CB 本身还引用着这些图片，因此这里通常不会真的删文件
            cleanup_unreferenced(conn, parse_urls(existing["images"]))
            return {"favorited": False}

        created = now_str()
        conn.execute(
            """
            INSERT INTO favorites (cb_id, name, group_id, remark, event_date, aliases,
                                   images, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.cb_id,
                cb["name"],
                cb["group_id"],
                cb["remark"] or "",
                # 收藏记录跟随来源 CB 的「时间」和「别名」
                cb["event_date"] or created[:10],
                cb["aliases"] or "[]",
                cb["images"] or "[]",
                created,
                created,
            ),
        )
        write_log(conn, ACTION_FAVORITE, cb["name"])
        conn.commit()
        return {"favorited": True}
    finally:
        conn.close()


@router.post("")
def create_favorite(payload: FavoritePayload):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="CB 名称不能为空")
    images = _clean_images(payload.images)
    aliases = clean_aliases(payload.aliases)
    event_date = clean_date(payload.event_date) or today_str()

    conn = get_conn()
    try:
        _check_group(conn, payload.group_id)
        created = now_str()
        cur = conn.execute(
            """
            INSERT INTO favorites (cb_id, name, group_id, remark, event_date, aliases,
                                   images, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.cb_id,
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
        write_log(conn, ACTION_FAVORITE_CREATE, name)
        conn.commit()
        return {"id": cur.lastrowid, "success": True}
    finally:
        conn.close()


@router.put("/{favorite_id}")
def update_favorite(favorite_id: int, payload: FavoritePayload):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="CB 名称不能为空")
    images = _clean_images(payload.images)
    aliases = clean_aliases(payload.aliases)

    conn = get_conn()
    try:
        exists = conn.execute(
            "SELECT id, images, event_date FROM favorites WHERE id = ?", (favorite_id,)
        ).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="收藏记录不存在")
        _check_group(conn, payload.group_id)
        event_date = clean_date(payload.event_date) or exists["event_date"] or today_str()
        conn.execute(
            """
            UPDATE favorites SET name = ?, group_id = ?, remark = ?, event_date = ?,
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
                favorite_id,
            ),
        )
        write_log(conn, ACTION_FAVORITE_UPDATE, name)
        conn.commit()
        stale = [url for url in parse_urls(exists["images"]) if url not in images]
        cleanup_unreferenced(conn, stale)
        return {"success": True}
    finally:
        conn.close()


@router.delete("/{favorite_id}")
def delete_favorite(favorite_id: int):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT name, images FROM favorites WHERE id = ?", (favorite_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="收藏记录不存在")
        conn.execute("DELETE FROM favorites WHERE id = ?", (favorite_id,))
        write_log(conn, ACTION_FAVORITE_DELETE, row["name"])
        conn.commit()
        # 只有「CB管理」里也删掉了这条 CB，图片才会真正从磁盘移除
        cleanup_unreferenced(conn, parse_urls(row["images"]))
        return {"success": True}
    finally:
        conn.close()
