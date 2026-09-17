"""SQLite 数据库连接与初始化（使用 Python 内置 sqlite3）。"""
import json
import os
import sqlite3
from datetime import datetime

from security import hash_password

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
# 图片默认存放目录，可在「网站设置」里改成磁盘上的任意文件夹
DEFAULT_IMAGE_DIR = os.path.join(BASE_DIR, "uploads")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(DEFAULT_IMAGE_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "app.db")

DEFAULT_SITE_NAME = "未完成 CB 后台管理系统"

# 「网址管理」里状态的两种取值：正常 / 作废（作废后可以再恢复）
SITE_STATUS_OK = "正常"
SITE_STATUS_VOID = "作废"
SITE_STATUSES = (SITE_STATUS_OK, SITE_STATUS_VOID)
SITE_DEFAULT_STATUS = SITE_STATUS_OK

# 作用级别的取值范围
SITE_LEVEL_MIN = 1
SITE_LEVEL_MAX = 5

# 默认写入数据库的分组（原需求中 Color 重复，已去重）
DEFAULT_GROUPS = [
    "WantA",
    "Want4",
    "Want",
    "UP",
    "Color",
    "Perfeat",
    "Hard",
    "CN",
    "Sweet",
    "Day",
    "Desk",
]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_setting(key: str, default: str = "") -> str:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row is not None else default
    except sqlite3.Error:
        # 表尚未创建（首次启动）等情况，回退到默认值
        return default
    finally:
        conn.close()


def set_setting(key: str, value: str) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, value, now_str()),
        )
        conn.commit()
    finally:
        conn.close()


def get_site_name() -> str:
    """站点名称；未配置时回退到默认名称。"""
    return (get_setting("site_name") or "").strip() or DEFAULT_SITE_NAME


def today_str() -> str:
    """YYYY-MM-DD，CB / 收藏记录里「时间」字段的默认值。"""
    return datetime.now().strftime("%Y-%m-%d")


def get_image_dir() -> str:
    """当前图片存放目录；未配置或目录不可用时回退到默认目录。"""
    path = (get_setting("image_dir") or "").strip() or DEFAULT_IMAGE_DIR
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        path = DEFAULT_IMAGE_DIR
        os.makedirs(path, exist_ok=True)
    return path


def _ensure_column(cur, table: str, column: str, ddl: str) -> None:
    """给已存在的表补一个缺失的字段（SQLite 没有 ADD COLUMN IF NOT EXISTS）。"""
    existing = {row["name"] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_db() -> None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                sort INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        # event_date：业务上的「时间」，默认取创建当天，允许手工改成别的日期
        # aliases：别名列表（JSON 数组），搜索 CB 名称时会一并匹配
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS cb (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                group_id INTEGER,
                remark TEXT NOT NULL DEFAULT '',
                event_date TEXT NOT NULL DEFAULT '',
                aliases TEXT NOT NULL DEFAULT '[]',
                images TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE SET NULL
            )
            """
        )

        # 收藏记录：与 cb 结构一致，cb_id 指向被收藏的 CB（可为空，表示手工新增的收藏）
        # 一个 CB 最多对应一条收藏记录；CB 被删除时收藏记录保留，cb_id 置空
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cb_id INTEGER UNIQUE,
                name TEXT NOT NULL,
                group_id INTEGER,
                remark TEXT NOT NULL DEFAULT '',
                event_date TEXT NOT NULL DEFAULT '',
                aliases TEXT NOT NULL DEFAULT '[]',
                images TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (cb_id) REFERENCES cb(id) ON DELETE SET NULL,
                FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE SET NULL
            )
            """
        )

        # 操作日志：每一次写操作都记一条，供「日志记录」菜单查看
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                action TEXT NOT NULL,
                target TEXT NOT NULL DEFAULT ''
            )
            """
        )

        # 网址管理：与 CB 相关的网址清单
        # url       主网址，列表里做成超链接新窗口打开
        # event_date「创建日期」，默认当天，可改
        # test_url  收藏内链，JSON 数组字符串，可存多条（列表里只展示第一条）
        # level     作用级别，1 - 5
        # downloadable 是否支持下载，0/1
        # status    正常 / 作废
        # remark    备注
        # sort      排序权重，越大越靠前；「移到最前」就是顶到最大值之上
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL DEFAULT '',
                event_date TEXT NOT NULL DEFAULT '',
                test_url TEXT NOT NULL DEFAULT '[]',
                level INTEGER NOT NULL DEFAULT 1,
                downloadable INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT '正常',
                remark TEXT NOT NULL DEFAULT '',
                sort INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        # 老库补列：CREATE TABLE IF NOT EXISTS 不会给已存在的表加字段
        for table in ("cb", "favorites"):
            _ensure_column(cur, table, "event_date", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(cur, table, "aliases", "TEXT NOT NULL DEFAULT '[]'")
            # 历史上已有的记录，用创建日期补上「时间」
            cur.execute(
                f"UPDATE {table} SET event_date = substr(created_at, 1, 10) "
                "WHERE event_date IS NULL OR event_date = ''"
            )

        # 网址管理是后加的菜单，remark / sort 更是后补的字段，一并补齐
        _ensure_column(cur, "sites", "remark", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(cur, "sites", "sort", "INTEGER NOT NULL DEFAULT 0")

        # 收藏内链原来只能存一条裸网址，现在改成 JSON 数组以支持多条。
        # 这里把老值包成单元素数组，避免读出来时被当成一堆字符。
        legacy_rows = cur.execute(
            "SELECT id, test_url FROM sites "
            "WHERE trim(test_url) <> '' AND substr(trim(test_url), 1, 1) <> '['"
        ).fetchall()
        for row in legacy_rows:
            cur.execute(
                "UPDATE sites SET test_url = ? WHERE id = ?",
                (json.dumps([row["test_url"].strip()], ensure_ascii=False), row["id"]),
            )

        # 站点设置：site_name（站点名称）、image_dir（图片存放目录）
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        created = now_str()

        # 初始化默认站点名称
        cur.execute(
            "INSERT OR IGNORE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("site_name", DEFAULT_SITE_NAME, created),
        )

        # 初始化默认管理员
        count = cur.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        if count == 0:
            cur.execute(
                "INSERT INTO users (username, password, created_at) VALUES (?, ?, ?)",
                ("admin", hash_password("admin123"), created),
            )

        # 初始化默认分组
        count = cur.execute("SELECT COUNT(*) AS c FROM groups").fetchone()["c"]
        if count == 0:
            for index, name in enumerate(DEFAULT_GROUPS):
                cur.execute(
                    "INSERT INTO groups (name, sort, created_at) VALUES (?, ?, ?)",
                    (name, index + 1, created),
                )

        conn.commit()
    finally:
        conn.close()
