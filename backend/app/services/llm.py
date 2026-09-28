"""app/services/llm.py —— LLM 工厂：全项目统一从这里拿模型客户端
所有模型走 OpenAI 兼容协议，换 DeepSeek/GLM/Qwen 只改 .env
"""
import functools
import os

from langchain_openai import ChatOpenAI

from app.config import settings


def get_chat_llm(temperature: float = 0.3, model: str | None = None) -> ChatOpenAI:
    """获取对话模型客户端。默认用 .env 配置的模型"""
    return ChatOpenAI(
        model=model or settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=temperature,
        max_retries=2,
    )


@functools.lru_cache(maxsize=1)
def get_embedder():
    """嵌入模型加载（进程级单例，避免每个请求重载模型）：
    优先读 .env 的 BGE_M3_PATH 本地目录，否则从 hub 拉取
    """
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(os.environ.get("BGE_M3_PATH", "BAAI/bge-m3"))


def get_structured_llm(schema, temperature: float = 0.3, model: str | None = None):
    """结构化输出客户端：走 function calling（DeepSeek 不支持 json_schema 响应格式）"""
    return get_chat_llm(temperature, model).with_structured_output(
        schema, method="function_calling")
