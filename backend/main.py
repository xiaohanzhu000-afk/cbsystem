"""CB后台管理系统 - FastAPI 入口。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routers import auth, cb, favorites, groups, logs, media, settings, sites


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="CB后台管理系统", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 上传的图片通过 /uploads/xxx.png 访问，实际目录由「网站设置」决定
app.include_router(media.router, tags=["图片"])

app.include_router(auth.router, prefix="/api/auth", tags=["登录"])
app.include_router(groups.router, prefix="/api/groups", tags=["分组管理"])
app.include_router(cb.router, prefix="/api/cb", tags=["CB管理"])
app.include_router(favorites.router, prefix="/api/favorites", tags=["收藏记录"])
app.include_router(sites.router, prefix="/api/sites", tags=["网址管理"])
app.include_router(logs.router, prefix="/api/logs", tags=["日志记录"])
app.include_router(settings.public_router, prefix="/api/settings", tags=["网站设置"])
app.include_router(settings.router, prefix="/api/settings", tags=["网站设置"])


@app.get("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8024, reload=True)
