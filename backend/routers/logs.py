"""日志记录接口：分页查询、批量删除、清空日志。"""
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from oplog import (
    ACTION_LOG_CLEAR,
    ACTION_LOG_DELETE,
    clear_logs,
    delete_logs,
    list_logs,
    log_action,
)
from security import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])


class BatchDeletePayload(BaseModel):
    ids: List[int] = Field(default_factory=list)


@router.get("")
def read_logs(page: int = 1, page_size: int = 20, keyword: str = ""):
    return list_logs(page=page, page_size=page_size, keyword=keyword)


@router.post("/batch-delete")
def remove_selected_logs(payload: BatchDeletePayload):
    """按 id 批量删除勾选的日志。"""
    removed = delete_logs(payload.ids)
    if removed:
        log_action(ACTION_LOG_DELETE, f"共 {removed} 条")
    return {"success": True, "removed": removed}


@router.delete("")
def remove_logs():
    """清空全部操作日志。"""
    removed = clear_logs()
    # 清空动作本身也要留痕，于是清完立刻补一条
    log_action(ACTION_LOG_CLEAR, f"共 {removed} 条")
    return {"success": True, "removed": removed}
