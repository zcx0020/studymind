"""app/api/deps.py —— FastAPI 依赖：数据库连接与进程级单例资源"""
import chromadb
import psycopg2
from neo4j import GraphDatabase

from app.config import settings
from app.services.llm import get_embedder

_neo4j_driver = None
_chroma_client = None


def new_pg():
    """新建 PG 连接（后台任务用，用完自行 close）"""
    return psycopg2.connect(settings.pg_dsn)


def get_pg():
    """FastAPI 请求级依赖：请求结束自动关闭"""
    conn = psycopg2.connect(settings.pg_dsn)
    try:
        yield conn
    finally:
        conn.close()


def get_neo4j():
    global _neo4j_driver
    if _neo4j_driver is None:
        _neo4j_driver = GraphDatabase.driver(
            settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
    return _neo4j_driver


def get_chroma():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=settings.chroma_path)
    return _chroma_client


def get_quiz_service(doc_id: int):
    """按教材构建出题服务（嵌入模型是进程级单例，不会重复加载）"""
    from app.services.rag.adaptive_quiz import AdaptiveQuizService, ChromaRetriever
    return AdaptiveQuizService(ChromaRetriever(get_chroma(), f"doc_{doc_id}", get_embedder()))
