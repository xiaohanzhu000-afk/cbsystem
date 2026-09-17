"""网址管理接口：存放与 CB 相关的网址，支持增删改查。

字段说明：

- ``url``：主网址，列表里渲染成超链接，新窗口打开
- ``event_date``：「创建日期」，默认当天，允许修改
- ``test_url``：收藏内链，可存多条（最多 ``MAX_TEST_URLS`` 条）。
  库里放的是 JSON 数组字符串，对外统一暴露成 ``test_urls`` 列表
- ``level``：作用级别，1 - 5
- ``downloadable``：是否支持下载
- ``status``：正常 / 作废，作废后可以通过「恢复」改回正常
- ``remark``：备注
- ``sort``：排序权重，越大越靠前；新建和「移到最前」都会把它顶到最大值之上
"""
import json
import re
from typing import List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from database import (
    SITE_DEFAULT_STATUS,
    SITE_LEVEL_MAX,
    SITE_LEVEL_MIN,
    SITE_STATUS_OK,
    SITE_STATUS_VOID,
    SITE_STATUSES,
    get_conn,
    now_str,
    today_str,
)
from oplog import (
    ACTION_SITE_CREATE,
    ACTION_SITE_DELETE,
    ACTION_SITE_DISABLE,
    ACTION_SITE_ENABLE,
    ACTION_SITE_MOVE_TOP,
    ACTION_SITE_UPDATE,
    write_log,
)
from routers.cb import clean_date
from security import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])

MAX_URL_LEN = 500
MAX_REMARK_LEN = 500
# 收藏内链最多几条。列表里只展示第一条，其余收进「+N」，避免一行被长网址撑开
MAX_TEST_URLS = 10

# 带协议头的样子；裸域名（example.com）会在 clean_url 里补上 https://
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")
# 形如 `javascript:xxx` / `mailto:xxx` 的伪协议；`localhost:8024` 这种不算
PSEUDO_SCHEME_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.\-]*):(.*)$", re.S)
# host 或 host:port，不接受带账号密码的写法
NETLOC_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9.\-]*[a-zA-Z0-9])?(:\d{1,5})?$")


class SitePayload(BaseModel):
    url: str = Field(..., min_length=1, max_length=MAX_URL_LEN)
    event_date: str = ""
    test_urls: List[str] = Field(default_factory=list)
    level: int = SITE_LEVEL_MIN
    downloadable: bool = False
    status: str = SITE_DEFAULT_STATUS
    remark: str = ""


def clean_url(value: Optional[str], field: str = "网址", required: bool = True) -> str:
    """规整网址：没写协议头就补 https://，只放行 http / https。

    这里必须挡住 `javascript:` 之类的伪协议，否则前端会把它渲染成可点击链接。
    所以「没有协议头就补 https://」这条路，只对不像伪协议的输入开放。
    """
    text = (value or "").strip()
    if not text:
        if required:
            raise HTTPException(status_code=400, detail=f"{field}不能为空")
        return ""
    if len(text) > MAX_URL_LEN:
        raise HTTPException(status_code=400, detail=f"{field}最长 {MAX_URL_LEN} 个字符")

    if SCHEME_RE.match(text):
        if SCHEME_RE.match(text).group(0)[:-3].lower() not in ("http", "https"):
            raise HTTPException(status_code=400, detail=f"{field}只支持 http / https 协议")
        candidate = text
    else:
        pseudo = PSEUDO_SCHEME_RE.match(text)
        if pseudo:
            # 冒号后到路径之前必须是端口号（纯数字），否则当成伪协议拒掉，
            # 例如 javascript:alert(1) 拒掉，而 localhost:8024/cb 放行
            head = re.split(r"[/?#]", pseudo.group(2), maxsplit=1)[0]
            if not head.isdigit():
                raise HTTPException(status_code=400, detail=f"{field}只支持 http / https 协议")
        candidate = "https://" + text

    parsed = urlparse(candidate)
    if not NETLOC_RE.match(parsed.netloc or ""):
        raise HTTPException(
            status_code=400, detail=f"{field}格式不正确，例如 https://example.com"
        )
    return candidate


def _clean_level(value) -> int:
    try:
        level = int(value)
    except (TypeError, ValueError):
        level = None
    if level is None or not SITE_LEVEL_MIN <= level <= SITE_LEVEL_MAX:
        raise HTTPException(
            status_code=400,
            detail=f"作用级别应为 {SITE_LEVEL_MIN} - {SITE_LEVEL_MAX} 之间的整数",
        )
    return level


def _clean_status(value: Optional[str]) -> str:
    text = (value or "").strip()
    if not text:
        return SITE_DEFAULT_STATUS
    if text not in SITE_STATUSES:
        raise HTTPException(
            status_code=400, detail=f"状态只能是「{SITE_STATUS_OK}」或「{SITE_STATUS_VOID}」"
        )
    return text


def _clean_remark(value: Optional[str]) -> str:
    """备注：允许留空，只限制长度。"""
    text = value or ""
    if len(text) > MAX_REMARK_LEN:
        raise HTTPException(status_code=400, detail=f"备注最长 {MAX_REMARK_LEN} 个字符")
    return text


def _dump_test_urls(values: Optional[List[str]]) -> str:
    """校验并序列化「收藏内链」：逐条走 clean_url，空串和重复项直接丢掉。"""
    result: List[str] = []
    for item in values or []:
        url = clean_url(item, "收藏内链", required=False)
        if url and url not in result:
            result.append(url)
    if len(result) > MAX_TEST_URLS:
        raise HTTPException(status_code=400, detail=f"收藏内链最多 {MAX_TEST_URLS} 条")
    return json.dumps(result, ensure_ascii=False)


def parse_test_urls(raw) -> List[str]:
    """把库里的 test_url 还原成列表。

    新数据存的是 JSON 数组；历史数据和旧数据包里可能是单条裸网址，
    这时按「只有一条」处理，保证升级后老数据不会凭空消失。
    """
    if isinstance(raw, (list, tuple)):
        values = list(raw)
    else:
        text = str(raw or "").strip()
        if not text:
            return []
        if not text.startswith("["):
            return [text]
        try:
            values = json.loads(text)
        except json.JSONDecodeError:
            return [text]
        if not isinstance(values, list):
            return [text]

    result: List[str] = []
    for item in values:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _log_target(url: str) -> str:
    """日志里去掉协议头：`https://example.com/a` 记成 `example.com/a`，更好读。"""
    return SCHEME_RE.sub("", url)


def _decode(row) -> dict:
    item = dict(row)
    item["downloadable"] = bool(row["downloadable"])
    item["level"] = int(row["level"] or SITE_LEVEL_MIN)
    item["event_date"] = row["event_date"] or ""
    item["status"] = row["status"] or SITE_DEFAULT_STATUS
    # 库里存的是 JSON 数组，对外只暴露解析好的列表
    item["test_urls"] = parse_test_urls(item.pop("test_url", ""))
    return item


@router.get("")
def list_sites(page: int = 1, page_size: int = 20, keyword: str = "", status: str = ""):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)

    where: List[str] = []
    params: list = []

    word = (keyword or "").strip()
    if word:
        like = f"%{word}%"
        where.append("(url LIKE ? OR test_url LIKE ? OR remark LIKE ?)")
        params += [like, like, like]

    state = (status or "").strip()
    if state:
        where.append("status = ?")
        params.append(_clean_status(state))

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    conn = get_conn()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM sites {where_sql}", params
        ).fetchone()["c"]
        rows = conn.execute(
            f"""
            SELECT id, url, event_date, test_url, level, downloadable, status,
                   remark, created_at, updated_at
            FROM sites
            {where_sql}
            ORDER BY sort DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            params + [page_size, (page - 1) * page_size],
        ).fetchall()
        return {
            "items": [_decode(r) for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    finally:
        conn.close()


@router.post("")
def create_site(payload: SitePayload):
    url = clean_url(payload.url)
    test_url = _dump_test_urls(payload.test_urls)
    level = _clean_level(payload.level)
    status = _clean_status(payload.status)
    remark = _clean_remark(payload.remark)
    event_date = clean_date(payload.event_date) or today_str()

    conn = get_conn()
    try:
        duplicate = conn.execute("SELECT id FROM sites WHERE url = ?", (url,)).fetchone()
        if duplicate is not None:
            raise HTTPException(status_code=400, detail="该网址已存在")

        created = now_str()
        # 新记录排在列表最前：sort 取当前最大值 + 1
        top = conn.execute("SELECT COALESCE(MAX(sort), 0) AS m FROM sites").fetchone()["m"]
        cur = conn.execute(
            """
            INSERT INTO sites (url, event_date, test_url, level, downloadable, status,
                               remark, sort, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                url,
                event_date,
                test_url,
                level,
                1 if payload.downloadable else 0,
                status,
                remark,
                int(top or 0) + 1,
                created,
                created,
            ),
        )
        write_log(conn, ACTION_SITE_CREATE, _log_target(url))
        conn.commit()
        return {"id": cur.lastrowid, "success": True}
    finally:
        conn.close()


@router.put("/{site_id}")
def update_site(site_id: int, payload: SitePayload):
    url = clean_url(payload.url)
    test_url = _dump_test_urls(payload.test_urls)
    level = _clean_level(payload.level)
    status = _clean_status(payload.status)
    remark = _clean_remark(payload.remark)

    conn = get_conn()
    try:
        exists = conn.execute(
            "SELECT id, url, event_date FROM sites WHERE id = ?", (site_id,)
        ).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="网址不存在")

        duplicate = conn.execute(
            "SELECT id FROM sites WHERE url = ? AND id <> ?", (url, site_id)
        ).fetchone()
        if duplicate is not None:
            raise HTTPException(status_code=400, detail="该网址已存在")

        # 「创建日期」留空表示不改动原值，而不是清掉
        event_date = clean_date(payload.event_date) or exists["event_date"] or today_str()

        conn.execute(
            """
            UPDATE sites SET url = ?, event_date = ?, test_url = ?, level = ?,
                             downloadable = ?, status = ?, remark = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                url,
                event_date,
                test_url,
                level,
                1 if payload.downloadable else 0,
                status,
                remark,
                now_str(),
                site_id,
            ),
        )
        write_log(conn, ACTION_SITE_UPDATE, _log_target(url))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()


@router.post("/{site_id}/toggle-status")
def toggle_site_status(site_id: int):
    """在「正常」与「作废」之间切换。"""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id, url, status FROM sites WHERE id = ?", (site_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="网址不存在")

        # 只有「正常」才算生效，其余一律视为作废，避免脏数据卡住状态
        target = SITE_STATUS_VOID if row["status"] == SITE_STATUS_OK else SITE_STATUS_OK
        conn.execute(
            "UPDATE sites SET status = ?, updated_at = ? WHERE id = ?",
            (target, now_str(), site_id),
        )
        write_log(
            conn,
            ACTION_SITE_ENABLE if target == SITE_STATUS_OK else ACTION_SITE_DISABLE,
            _log_target(row["url"]),
        )
        conn.commit()
        return {"success": True, "status": target}
    finally:
        conn.close()


@router.post("/{site_id}/move-top")
def move_site_to_top(site_id: int):
    """把一条网址提到列表最前：sort 取当前最大值 + 1，其余记录顺序不受影响。"""
    conn = get_conn()
    try:
        row = conn.execute("SELECT id, url FROM sites WHERE id = ?", (site_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="网址不存在")

        top = conn.execute("SELECT COALESCE(MAX(sort), 0) AS m FROM sites").fetchone()["m"]
        conn.execute(
            "UPDATE sites SET sort = ?, updated_at = ? WHERE id = ?",
            (int(top or 0) + 1, now_str(), site_id),
        )
        write_log(conn, ACTION_SITE_MOVE_TOP, _log_target(row["url"]))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()


@router.delete("/{site_id}")
def delete_site(site_id: int):
    conn = get_conn()
    try:
        row = conn.execute("SELECT url FROM sites WHERE id = ?", (site_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="网址不存在")
        conn.execute("DELETE FROM sites WHERE id = ?", (site_id,))
        write_log(conn, ACTION_SITE_DELETE, _log_target(row["url"]))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()
