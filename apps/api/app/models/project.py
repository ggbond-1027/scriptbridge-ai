"""项目模型 - 项目管理数据结构"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, Boolean
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class ProjectStatus(str, Enum):
    """项目状态"""
    CREATED = "created"
    IMPORTING = "importing"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    EDITING = "editing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProjectDB(Base):
    """项目数据库模型"""
    __tablename__ = "projects"

    id = Column(String(64), primary_key=True)
    title = Column(String(256), nullable=False)
    description = Column(Text, default="")
    source_language = Column(String(16), default="zh-CN")
    target_format = Column(String(32), default="screenplay")
    status = Column(String(32), default=ProjectStatus.CREATED.value)
    source_text = Column(Text, default="")
    source_file_path = Column(String(512), default="")
    screenplay_data = Column(JSON, default=None)
    adaptation_style = Column(JSON, default=None)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    is_deleted = Column(Boolean, default=False)


class ProjectCreate(BaseModel):
    """创建项目请求 — 匹配前端 ImportPage 发送的字段"""
    name: str = Field(..., min_length=1, max_length=256, description="项目名称")
    source_text: Optional[str] = Field(default=None, description="小说原文文本")
    adaptation_style: str = Field(default="short_series", description="改编风格: short_series/tv_series/radio_drama/stage_play")
    dialogue_style: str = Field(default="natural", description="对白风格: natural/restrained/internet/dramatic")


class ProjectUpdate(BaseModel):
    """更新项目请求"""
    title: Optional[str] = Field(default=None, min_length=1, max_length=256)
    description: Optional[str] = Field(default=None)
    source_language: Optional[str] = Field(default=None)
    target_format: Optional[str] = Field(default=None)
    adaptation_style: Optional[Dict[str, Any]] = Field(default=None)
    status: Optional[ProjectStatus] = Field(default=None)


class CreateProjectResponse(BaseModel):
    """创建项目响应 — 匹配前端 CreateProjectResponse"""
    project_id: str
    message: str


class ProjectResponse(BaseModel):
    """项目响应"""
    id: str
    title: str
    description: Optional[str] = None
    source_language: str
    target_format: str
    status: str
    source_text_length: Optional[int] = None
    chapter_count: Optional[int] = None
    scene_count: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    """项目列表响应"""
    projects: List[ProjectResponse]
    total: int
    page: int
    page_size: int