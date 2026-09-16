"""网站设置：站点名称、图片存放目录（可在磁盘上选文件夹）、无引用图片清理、数据备份与恢复。"""
import os
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel

from backup import build_backup, restore_backup
from database import (
    DEFAULT_IMAGE_DIR,
    get_conn,
    get_image_dir,
    get_site_name,
    set_setting,
)
from image_store import cleanup_unreferenced, count_images, move_images, orphan_urls
from oplog import (
    ACTION_BACKUP,
    ACTION_CLEANUP_IMAGES,
    ACTION_RESTORE,
    ACTION_SETTINGS_UPDATE,
    log_action,
)
from security import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])

# 登录页也要显示站点名称，这部分不鉴权
public_router = APIRouter()

MAX_SITE_NAME_LEN = 50
MAX_BACKUP_SIZE = 200 * 1024 * 1024  # 数据包上限 200MB


class SettingsPayload(BaseModel):
    site_name: str = ""
    image_dir: str = ""


def _snapshot() -> dict:
    image_dir = get_image_dir()
    return {
        "site_name": get_site_name(),
        "image_dir": image_dir,
        "default_image_dir": DEFAULT_IMAGE_DIR,
        "is_default_dir": os.path.abspath(image_dir) == os.path.abspath(DEFAULT_IMAGE_DIR),
        "image_count": count_images(image_dir),
    }


@public_router.get("/public")
def read_public_settings():
    """站点名称，供登录页 / 全局标题使用。"""
    return {"site_name": get_site_name()}


@router.get("")
def read_settings():
    return _snapshot()


@router.put("")
def update_settings(payload: SettingsPayload):
    new_name = (payload.site_name or "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="站点名称不能为空")
    if len(new_name) > MAX_SITE_NAME_LEN:
        raise HTTPException(
            status_code=400, detail=f"站点名称不能超过 {MAX_SITE_NAME_LEN} 个字符"
        )

    raw_dir = (payload.image_dir or "").strip()
    old_dir = get_image_dir()
    new_dir = os.path.abspath(os.path.expanduser(raw_dir)) if raw_dir else DEFAULT_IMAGE_DIR

    if os.path.exists(new_dir) and not os.path.isdir(new_dir):
        raise HTTPException(status_code=400, detail="所选路径不是文件夹")
    try:
        os.makedirs(new_dir, exist_ok=True)
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"无法创建或访问该文件夹：{exc}")
    if not os.access(new_dir, os.W_OK):
        raise HTTPException(status_code=400, detail="该文件夹没有写入权限，请换一个目录")

    # 换目录时把已有图片搬过去，历史缩略图不会失效
    moved, failed = 0, []
    if os.path.abspath(old_dir) != new_dir:
        moved, failed = move_images(old_dir, new_dir)

    set_setting("site_name", new_name)
    set_setting("image_dir", new_dir)

    detail = new_name if os.path.abspath(old_dir) == new_dir else f"{new_name}（图片目录改为 {new_dir}）"
    log_action(ACTION_SETTINGS_UPDATE, detail)

    result = _snapshot()
    result.update({"success": True, "moved": moved, "failed": failed})
    return result


@router.post("/pick-folder")
def pick_folder():
    """弹出一个系统文件夹选择框，返回选中的绝对路径。

    对话框开在运行后端的这台机器上；若环境不支持，前端可改为手动输入路径。
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        raise HTTPException(
            status_code=400, detail="当前运行环境不支持弹出文件夹选择框，请手动输入路径"
        )

    selected = ""
    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass
        selected = filedialog.askdirectory(title="请选择图片存放文件夹") or ""
    except Exception:
        raise HTTPException(
            status_code=400, detail="无法打开文件夹选择框，请手动输入路径"
        )
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass

    if not selected:
        return {"cancelled": True, "path": ""}
    return {"cancelled": False, "path": os.path.normpath(selected)}


@router.post("/cleanup-images")
def cleanup_images():
    """清理磁盘上已不被任何 CB / 收藏记录引用的图片。"""
    conn = get_conn()
    try:
        removed = cleanup_unreferenced(conn, orphan_urls(conn))
    finally:
        conn.close()
    log_action(ACTION_CLEANUP_IMAGES, f"清理 {len(removed)} 张")
    return {"success": True, "removed": len(removed), "remaining": count_images()}


@router.get("/backup")
def download_backup():
    """导出数据包：zip（backup.json 业务数据 + images/ 图片）。"""
    filename = f"cbsystem-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
    content = build_backup()
    log_action(ACTION_BACKUP, filename)
    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            # 让前端能直接读到文件名
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.post("/restore")
async def upload_restore(file: UploadFile = File(...)):
    """上传数据包，整体覆盖当前的分组、CB、收藏记录与图片。"""
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="请选择要恢复的数据包")
    if len(raw) > MAX_BACKUP_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"数据包不能超过 {MAX_BACKUP_SIZE // 1024 // 1024} MB",
        )

    try:
        result = restore_backup(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"写入数据失败：{exc}")

    log_action(
        ACTION_RESTORE,
        f"{file.filename or '数据包'}"
        f"（CB {result['cb']} 条、收藏 {result['favorites']} 条、网址 {result['sites']} 条）",
    )
    return result
