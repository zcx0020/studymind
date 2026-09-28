"""StudyMind API 入口
启动: cd backend && uvicorn app.main:app --reload --port 8000
文档: http://localhost:8000/docs
说明: 若 frontend/dist 存在，后端直接托管前端构建产物，
      部署机上无需安装 Node.js，访问 http://localhost:8000 即为完整应用
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import documents, knowledge, mastery, plans, quiz, tasks
from app.config import settings

logger = logging.getLogger("studymind.main")

# 前端构建产物目录（相对 backend/ 上溯到项目根）
_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def _ensure_schema():
    """启动自检：① 老库补 quiz_records 的 Elo 快照列（会话总结依赖）；
    ② 新库（Render 等平台无 docker init 环节）自动执行 init_db.sql 建表。
    数据库未就绪时静默跳过，不阻塞 API 启动"""
    try:
        import psycopg2
        conn = psycopg2.connect(settings.pg_dsn)
        try:
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE quiz_records ADD COLUMN IF NOT EXISTS elo_delta REAL")
                cur.execute("ALTER TABLE quiz_records ADD COLUMN IF NOT EXISTS theta_before REAL")
                # 表不存在（全新库）→ 执行完整建表脚本（幂等，含演示用户）
                cur.execute("SELECT to_regclass('public.questions')")
                if cur.fetchone()[0] is None:
                    sql_path = Path(__file__).resolve().parents[2] / "scripts" / "init_db.sql"
                    if sql_path.exists():
                        cur.execute(sql_path.read_text(encoding="utf-8"))
                        logger.info("已初始化数据库表结构（init_db.sql）")
            conn.commit()
        finally:
            conn.close()
    except Exception:   # noqa: BLE001 —— DB 未启动时不能阻止 API 起来
        logger.warning("schema 轻迁移跳过（数据库未就绪？）")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _ensure_schema()
    yield


app = FastAPI(title="StudyMind API", version="0.3.0", lifespan=lifespan)

# 跨域：默认放开（本地开发/演示）；生产通过 CORS_ORIGINS 指定 Vercel 域名
_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (documents.router, knowledge.router, mastery.router,
          plans.router, quiz.router, quiz.submit_router,
          tasks.router, tasks.status_router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ── 前端静态托管 + SPA 路由回退（仅在 dist 存在时启用） ──
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")

    @app.exception_handler(StarletteHTTPException)
    async def _spa_fallback(request: Request, exc: StarletteHTTPException):
        """前端 vue-router 深链接（如 /quiz/3）刷新时回退到 index.html；
        /api 开头的 404 保持 JSON 响应"""
        if exc.status_code == 404 and not request.url.path.startswith("/api"):
            return FileResponse(_DIST / "index.html")
        return JSONResponse({"detail": str(exc.detail)}, status_code=exc.status_code)
