"""操作日志：把每一次写操作记进 operation_logs 表，供「日志记录」菜单查看。

表里只存两段信息——「动作」和「对象」，页面拼成 `动作 — 对象` 显示：

    2026年9月16日 16:32:09    新增CB — XXXX
    2026年9月16日 16:35:09    备份数据

写入方式按场景选一个：

- ``write_log(conn, ...)``：调用方已经有一条可写连接时用，日志与业务数据同事务，
  必须在 ``conn.commit()`` **之前**调用。
- ``log_action(...)``：调用方没有现成事务（备份、网站设置、恢复数据）时用，自己开连接。

两者都会吞掉日志写入本身的异常：日志记不上不应该让业务操作跟着失败。
"""
from typing import List

from database import get_conn, now_str

# 动作文案集中在这里，避免各处硬编码字符串
ACTION_LOGIN = "登录系统"
ACTION_GROUP_CREATE = "新增分组"
ACTION_GROUP_UPDATE = "修改分组"
ACTION_GROUP_DELETE = "删除分组"
ACTION_CB_CREATE = "新增CB"
ACTION_CB_UPDATE = "修改CB"
ACTION_CB_DELETE = "删除CB"
ACTION_FAVORITE = "收藏CB"
ACTION_UNFAVORITE = "取消收藏"
ACTION_FAVORITE_CREATE = "新增收藏"
ACTION_FAVORITE_UPDATE = "修改收藏"
ACTION_FAVORITE_DELETE = "删除收藏"
ACTION_SETTINGS_UPDATE = "修改网站设置"
ACTION_CLEANUP_IMAGES = "清理未引用图片"
ACTION_BACKUP = "备份数据"
ACTION_RESTORE = "恢复备份"
ACTION_LOG_CLEAR = "清空日志"
ACTION_LOG_DELETE = "删除日志"
ACTION_SITE_CREATE = "新增网址"
ACTION_SITE_UPDATE = "修改网址"
ACTION_SITE_DELETE = "删除网址"
ACTION_SITE_DISABLE = "作废网址"
ACTION_SITE_ENABLE = "恢复网址"

# 对象名过长时截断，避免一条日志被整段备注撑爆
MAX_TARGET_LEN = 200


def _clean_target(target) -> str:
    return str(target or "").strip()[:MAX_TARGET_LEN]


def write_log(conn, action: str, target: str = "") -> None:
    """在调用方已有的连接上写日志，需在 commit 之前调用。"""
    try:
        conn.execute(
            "INSERT INTO operation_logs (created_at, action, target) VALUES (?, ?, ?)",
            (now_str(), action, _clean_target(target)),
        )
    except Exception:
        # 日志只是旁路记录，写不进去也不能影响主流程
        pass


def log_action(action: str, target: str = "") -> None:
    """独立连接写日志，用于没有现成事务的场景。"""
    try:
        conn = get_conn()
    except Exception:
        return
    try:
        write_log(conn, action, target)
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def list_logs(page: int = 1, page_size: int = 20, keyword: str = "") -> dict:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)

    where = []
    params: List = []
    word = (keyword or "").strip()
    if word:
        like = f"%{word}%"
        where.append("(action LIKE ? OR target LIKE ?)")
        params += [like, like]
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    conn = get_conn()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM operation_logs {where_sql}", params
        ).fetchone()["c"]
        rows = conn.execute(
            f"""
            SELECT id, created_at, action, target
            FROM operation_logs
            {where_sql}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            params + [page_size, (page - 1) * page_size],
        ).fetchall()
        return {
            "items": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    finally:
        conn.close()


def clear_logs() -> int:
    conn = get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) AS c FROM operation_logs").fetchone()["c"]
        conn.execute("DELETE FROM operation_logs")
        # 清空后让自增 id 从头开始
        try:
            conn.execute("DELETE FROM sqlite_sequence WHERE name = 'operation_logs'")
        except Exception:
            pass
        conn.commit()
        return total
    finally:
        conn.close()


def delete_logs(ids: List[int]) -> int:
    """按 id 批量删除日志，返回实际删掉的条数。"""
    clean: List[int] = []
    for value in ids or []:
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number not in clean:
            clean.append(number)
    if not clean:
        return 0

    conn = get_conn()
    try:
        placeholders = ", ".join("?" for _ in clean)
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM operation_logs WHERE id IN ({placeholders})", clean
        ).fetchone()["c"]
        conn.execute(f"DELETE FROM operation_logs WHERE id IN ({placeholders})", clean)
        conn.commit()
        return total
    finally:
        conn.close()


__all__ = [
    "ACTION_BACKUP",
    "ACTION_CB_CREATE",
    "ACTION_CB_DELETE",
    "ACTION_CB_UPDATE",
    "ACTION_CLEANUP_IMAGES",
    "ACTION_FAVORITE",
    "ACTION_FAVORITE_CREATE",
    "ACTION_FAVORITE_DELETE",
    "ACTION_FAVORITE_UPDATE",
    "ACTION_GROUP_CREATE",
    "ACTION_GROUP_DELETE",
    "ACTION_GROUP_UPDATE",
    "ACTION_LOGIN",
    "ACTION_LOG_CLEAR",
    "ACTION_LOG_DELETE",
    "ACTION_RESTORE",
    "ACTION_SETTINGS_UPDATE",
    "ACTION_SITE_CREATE",
    "ACTION_SITE_DELETE",
    "ACTION_SITE_DISABLE",
    "ACTION_SITE_ENABLE",
    "ACTION_SITE_UPDATE",
    "ACTION_UNFAVORITE",
    "clear_logs",
    "delete_logs",
    "list_logs",
    "log_action",
    "write_log",
]
