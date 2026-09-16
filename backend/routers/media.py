"""图片访问接口。

存放目录可以在「网站设置」里随时改成磁盘上的任意文件夹，所以这里不能用
StaticFiles 挂载固定目录，必须每次请求都实时解析当前目录。
"""
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from image_store import resolve_media_path

router = APIRouter()


@router.get("/uploads/{filename}")
def read_image(filename: str):
    path = resolve_media_path(filename)
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(path)
