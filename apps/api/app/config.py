"""NovelScripter 配置管理模块"""

from pydantic_settings import BaseSettings
from typing import List, Optional
from enum import Enum


class LLMProviderMode(str, Enum):
    """LLM提供商模式"""
    API = "api"
    LOCAL = "local"


class Settings(BaseSettings):
    """应用配置，从环境变量或.env文件读取"""

    # 数据库配置
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/novelscripter"

    # Redis配置
    REDIS_URL: str = "redis://localhost:6379/0"

    # MinIO对象存储配置
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_BUCKET_NAME: str = "novelscripter"

    # OpenAI / API模式配置
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    MODEL_NAME: str = "gpt-4o"

    # DeepSeek配置
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # GLM配置
    GLM_API_KEY: str = ""
    GLM_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"

    # Claude配置
    CLAUDE_API_KEY: str = ""
    CLAUDE_BASE_URL: str = "https://api.anthropic.com/v1"
    CLAUDE_MODEL: str = "claude-3-5-sonnet-20241022"

    # 本地模式配置（Ollama/vLLM）
    LLM_PROVIDER: LLMProviderMode = LLMProviderMode.API
    LOCAL_LLM_BASE_URL: str = "http://localhost:11434/v1"  # Ollama默认
    LOCAL_LLM_MODEL: str = "qwen2.5:14b"
    VLLM_BASE_URL: str = "http://localhost:8000/v1"
    VLLM_MODEL: str = "Qwen2.5-14B-Instruct"

    # Celery配置
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # CORS配置
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173", "*"]

    # 应用配置
    APP_NAME: str = "NovelScripter"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Pipeline配置
    PIPELINE_MAX_RETRIES: int = 3
    PIPELINE_TIMEOUT_SECONDS: int = 300

    # 模型路由配置
    DEFAULT_MODEL_TIER: str = "standard"
    COST_LIMIT_PER_REQUEST: float = 0.5  # USD

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


settings = Settings()