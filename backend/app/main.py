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

logger = logging.getLogger("studymind.main")

# 前端构建产物目录（相对 backend/ 上溯到项目根）
_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def _ensure_schema():
    """幂等轻迁移：老库补 quiz_records 的 Elo 快照列（会话总结依赖）。
    数据库未就绪时静默跳过，不阻塞 API 启动"""
    try:
        import psycopg2
        from app.config import settings
        conn = psycopg2.connect(settings.pg_dsn)
        try:
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE quiz_records ADD COLUMN IF NOT EXISTS elo_delta REAL")
                cur.execute("ALTER TABLE quiz_records ADD COLUMN IF NOT EXISTS theta_before REAL")
            conn.commit()
        finally:
            conn.close()
    except Exception:   # noqa: BLE001 —— DB 未启动时不能阻止 API 起来
        logger.warning("schema 轻迁移跳过（数据库未就绪？）")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _ensure_schema()
    yield


app = FastAPI(title="StudyMind API", version="0.2.0", lifespan=lifespan)

# 课程项目：前端 dev server 任意源
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
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
