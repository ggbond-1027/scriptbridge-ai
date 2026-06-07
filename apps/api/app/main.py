"""NovelScripter FastAPI 应用入口"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

import importlib

from app.config import settings
from app.routers.projects import (
    load_persisted_projects_into_memory,
    router as projects_router,
)
_import_module = importlib.import_module("app.routers.import")
import_router_router = _import_module.router
from app.routers.pipeline import router as pipeline_router
from app.routers.editing import router as editing_router
from app.routers.export import router as export_router
from app.routers.models import router as models_router
from app.core.pipeline import PipelineManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化资源，关闭时清理资源"""
    # 启动时初始化
    pipeline_manager = PipelineManager()
    app.state.pipeline_manager = pipeline_manager

    # 初始化模型路由器
    from app.core.model_router import ModelRouter
    app.state.model_router = ModelRouter(settings)
    app.state.persisted_project_count = load_persisted_projects_into_memory()

    # 初始化数据库连接（如果配置了且可用）
    if settings.DATABASE_URL and not settings.DATABASE_URL.startswith("sqlite"):
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            engine = create_engine(settings.DATABASE_URL)
            app.state.db_engine = engine
            app.state.db_session = sessionmaker(bind=engine)
        except Exception:
            pass  # 数据库不可用时跳过

    # 初始化Redis连接（如果配置了且可用）
    if settings.REDIS_URL:
        try:
            import redis as redis_lib
            app.state.redis = redis_lib.from_url(settings.REDIS_URL)
        except Exception:
            pass  # Redis不可用时跳过

    # 初始化MinIO客户端（如果配置了且可用）
    if settings.MINIO_ENDPOINT:
        try:
            from minio import Minio
            app.state.minio_client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
            )
        except Exception:
            pass  # MinIO不可用时跳过

    yield

    # 关闭时清理
    if hasattr(app.state, 'db_engine'):
        app.state.db_engine.dispose()

    if hasattr(app.state, 'redis'):
        app.state.redis.close()


app = FastAPI(
    title="NovelScripter API",
    description="AI小说转剧本工具 - 将小说文本智能转换为专业剧本格式",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 中间件配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(projects_router, prefix="/api/v1/projects", tags=["项目管理"])
app.include_router(import_router_router, prefix="/api/v1/import", tags=["小说导入"])
app.include_router(pipeline_router, prefix="/api/v1/pipeline", tags=["AI Pipeline"])
app.include_router(editing_router, prefix="/api/v1/editing", tags=["编辑"])
app.include_router(export_router, prefix="/api/v1/export", tags=["导出"])
app.include_router(models_router, prefix="/api/v1/models", tags=["模型管理"])


@app.get("/api/v1/health", tags=["系统"])
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "llm_provider": settings.LLM_PROVIDER,
        "model_name": settings.MODEL_NAME,
    }


@app.get("/api/v1/info", tags=["系统"])
async def system_info():
    """系统信息接口"""
    return {
        "name": "NovelScripter",
        "description": "AI小说转剧本工具",
        "version": "1.0.0",
        "supported_formats": ["yaml", "json", "markdown", "fountain", "zip", "docs"],
        "supported_languages": ["zh-CN", "en-US"],
        "pipeline_stages": [
            "chapter_splitting",
            "paragraph_indexing",
            "chapter_understanding",
            "story_bible_merge",
            "scene_splitting",
            "element_generation",
            "schema_validation",
        ],
    }
