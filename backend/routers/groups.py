"""分组管理接口：增删改查。"""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from database import get_conn, now_str
from oplog import ACTION_GROUP_CREATE, ACTION_GROUP_DELETE, ACTION_GROUP_UPDATE, write_log
from security import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])


class GroupPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    sort: int = 0


@router.get("")
def list_groups():
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, name, sort, created_at FROM groups ORDER BY sort ASC, id ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.post("")
def create_group(payload: GroupPayload):
    conn = get_conn()
    try:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="分组名称不能为空")
        try:
            cur = conn.execute(
                "INSERT INTO groups (name, sort, created_at) VALUES (?, ?, ?)",
                (name, payload.sort, now_str()),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="分组名称已存在")
        write_log(conn, ACTION_GROUP_CREATE, name)
        conn.commit()
        return {"id": cur.lastrowid, "name": name, "sort": payload.sort}
    finally:
        conn.close()


@router.put("/{group_id}")
def update_group(group_id: int, payload: GroupPayload):
    conn = get_conn()
    try:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="分组名称不能为空")
        exists = conn.execute("SELECT id FROM groups WHERE id = ?", (group_id,)).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="分组不存在")
        try:
            conn.execute(
                "UPDATE groups SET name = ?, sort = ? WHERE id = ?",
                (name, payload.sort, group_id),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="分组名称已存在")
        write_log(conn, ACTION_GROUP_UPDATE, name)
        conn.commit()
        return {"id": group_id, "name": name, "sort": payload.sort}
    finally:
        conn.close()


@router.delete("/{group_id}")
def delete_group(group_id: int):
    conn = get_conn()
    try:
        exists = conn.execute(
            "SELECT id, name FROM groups WHERE id = ?", (group_id,)
        ).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="分组不存在")
        conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))
        write_log(conn, ACTION_GROUP_DELETE, exists["name"])
        conn.commit()
        return {"success": True}
    finally:
        conn.close()
