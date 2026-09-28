"""app/config.py —— 全局配置：统一从 .env 读取，任何业务代码不得硬编码密钥"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # 项目根目录 .env

# 数据目录锚定到 backend/ 绝对路径（脚本与 API 进程 cwd 不同，相对路径会导致数据分裂）
_BASE_DIR = Path(__file__).resolve().parents[1]


class Settings:
    # ── LLM（OpenAI 兼容协议，可切换 DeepSeek/GLM/Qwen） ──
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # ── 数据库 ──
    # 本地走 POSTGRES_DSN；Render 等 PaaS 平台提供 DATABASE_URL 时自动兼容
    pg_dsn: str = os.getenv("POSTGRES_DSN") or os.getenv("DATABASE_URL") or \
        "postgresql://postgres:postgres@localhost:5433/studymind"
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "password")
    chroma_path: str = os.getenv("CHROMA_PATH") or str(_BASE_DIR / "kb")
    upload_dir: str = os.getenv("UPLOAD_DIR") or str(_BASE_DIR / "data" / "uploads")

    # ── 部署 ──
    # 允许跨域的前端域名，逗号分隔；默认 * （本地开发/演示）
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")

    # ── 掌握度模型参数（Elo） ──
    elo_k: float = 32.0          # 更新学习率
    elo_initial: float = 1500.0  # 初始掌握度
    elo_mastered: float = 1700.0  # 达到即视为"已掌握"
    mastered_streak: int = 3      # 连续答对 3 次也视为"已掌握"


settings = Settings()
