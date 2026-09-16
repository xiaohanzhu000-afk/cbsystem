"""图片文件的保存、访问与「无引用自动清理」。

图片一律以 `/uploads/<文件名>` 的形式存进数据库；真实目录由「网站设置」里的
image_dir 决定，因此这里所有路径解析都必须走 `get_image_dir()`，不能缓存。

清理规则：某个图片文件只要还被子表 `cb` 或 `favorites` 中的任意一条记录引用，
就保留；两个表都不再引用时才删掉磁盘文件。
"""
import json
import os
import shutil
import uuid
from typing import Iterable, List, Optional, Set, Tuple

from database import get_image_dir

URL_PREFIX = "/uploads/"
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp", "bmp"}

# 参与「引用计数」的表，两处都删除后图片才会被清理
REFERENCE_TABLES = ("cb", "favorites")


def _ext_of(filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lstrip(".").lower()
    return ext if ext in ALLOWED_EXT else "png"


def save_bytes(content: bytes, filename: str) -> str:
    """把二进制内容写入当前图片目录，返回可访问的相对 URL。"""
    name = f"{uuid.uuid4().hex}.{_ext_of(filename)}"
    target_dir = get_image_dir()
    with open(os.path.join(target_dir, name), "wb") as f:
        f.write(content)
    return URL_PREFIX + name


def resolve_media_path(filename: str) -> Optional[str]:
    """由文件名得到本地绝对路径；带路径分隔符或隐藏文件一律拒绝。"""
    if not filename or os.path.basename(filename) != filename:
        return None
    if filename.startswith("."):
        return None
    return os.path.join(get_image_dir(), filename)


def delete_by_url(url: str) -> bool:
    """删除某个 /uploads/xxx 对应的物理文件；外部 URL、data: 等直接忽略。"""
    if not url or not isinstance(url, str) or not url.startswith(URL_PREFIX):
        return False
    path = resolve_media_path(url[len(URL_PREFIX):])
    if not path or not os.path.isfile(path):
        return False
    try:
        os.remove(path)
        return True
    except OSError:
        return False


def parse_urls(raw) -> List[str]:
    """把数据库里的 images 字段（JSON 字符串或已解析的列表）转成 URL 列表。"""
    if isinstance(raw, (list, tuple)):
        return [str(x) for x in raw if x]
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(value, list):
        return []
    return [str(x) for x in value if x]


def collect_referenced(conn) -> Set[str]:
    """当前仍被 CB 或 收藏记录 引用到的全部图片 URL。"""
    used: Set[str] = set()
    for table in REFERENCE_TABLES:
        try:
            rows = conn.execute(f"SELECT images FROM {table}").fetchall()
        except Exception:
            continue
        for row in rows:
            used.update(parse_urls(row["images"]))
    return used


def cleanup_unreferenced(conn, candidates: Iterable[str]) -> List[str]:
    """把候选中已无人引用的图片从磁盘删掉。

    必须在数据库改动**提交之后**调用，这样 `conn` 看到的是最新引用关系。
    """
    removed: List[str] = []
    targets = {url for url in candidates if url}
    if not targets:
        return removed

    used = collect_referenced(conn)
    for url in targets:
        if url in used:
            continue
        if delete_by_url(url):
            removed.append(url)
    return removed


def move_images(old_dir: str, new_dir: str) -> Tuple[int, List[str]]:
    """图片目录切换时，把已有图片挪到新目录，避免历史缩略图失效。

    返回 (成功数量, 失败文件名列表)。同名文件已存在时视为已就位，不覆盖。
    """
    if not old_dir or os.path.abspath(old_dir) == os.path.abspath(new_dir):
        return 0, []
    if not os.path.isdir(old_dir):
        return 0, []

    os.makedirs(new_dir, exist_ok=True)
    moved, failed = 0, []
    for name in sorted(os.listdir(old_dir)):
        if name.startswith("."):
            continue
        src = os.path.join(old_dir, name)
        if not os.path.isfile(src):
            continue
        dst = os.path.join(new_dir, name)
        if os.path.exists(dst):
            continue
        try:
            shutil.move(src, dst)
            moved += 1
        except OSError:
            failed.append(name)
    return moved, failed


def count_images(directory: Optional[str] = None) -> int:
    directory = directory or get_image_dir()
    if not os.path.isdir(directory):
        return 0
    return sum(
        1
        for name in os.listdir(directory)
        if not name.startswith(".") and os.path.isfile(os.path.join(directory, name))
    )


def orphan_urls(conn) -> List[str]:
    """磁盘上存在、但已无人引用的图片（供手动排查用）。"""
    used = collect_referenced(conn)
    directory = get_image_dir()
    if not os.path.isdir(directory):
        return []
    result = []
    for name in os.listdir(directory):
        if name.startswith("."):
            continue
        url = URL_PREFIX + name
        if url not in used and os.path.isfile(os.path.join(directory, name)):
            result.append(url)
    return result


__all__ = [
    "ALLOWED_EXT",
    "REFERENCE_TABLES",
    "URL_PREFIX",
    "cleanup_unreferenced",
    "collect_referenced",
    "count_images",
    "delete_by_url",
    "move_images",
    "orphan_urls",
    "parse_urls",
    "resolve_media_path",
    "save_bytes",
]
