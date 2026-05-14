"""
Trade AI Assistant — API 请求/响应模型（Pydantic）。

将所有创建/更新类接口的 query params 替换为请求体模型，
自动校验类型、长度，生成正确的 OpenAPI schema。
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ── Company ────────────────────────────────────────────────────────────────────

class CompanyCreate(BaseModel):
    name: str = Field(..., description="公司名称")
    slug: Optional[str] = Field(None, description="URL 标识（省略时自动生成）")
    logo_url: str = Field("", description="Logo URL")
    website: str = Field("", description="公司网站")
    contact_name: str = Field("", description="联系人姓名")
    contact_email: str = Field("", description="联系人邮箱")
    address: str = Field("", description="地址")
    work_dir_name: str = Field("", description="桌面工作目录名称（目录存在时可用此改名）")


class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(None, description="公司名称")
    logo_url: Optional[str] = Field(None, description="Logo URL")
    website: Optional[str] = Field(None, description="公司网站")
    contact_name: Optional[str] = Field(None, description="联系人姓名")
    contact_email: Optional[str] = Field(None, description="联系人邮箱")
    address: Optional[str] = Field(None, description="地址")
    is_active: Optional[bool] = Field(None, description="是否激活")


class AgentIdentityUpdate(BaseModel):
    agent_identity_md: str = Field("", description="Agent 身份配置 (Markdown)")


class OnboardingFirstCompany(BaseModel):
    company_name: str = Field(..., description="公司名称")
    contact_name: str = Field("", description="联系人姓名")
    contact_email: str = Field("", description="联系人邮箱")
    identity_data: Optional[dict] = Field(None, description="Agent 身份配置")
    work_dir_name: str = Field("", description="桌面工作目录名称")


# ── Library ────────────────────────────────────────────────────────────────────

class LibraryCreate(BaseModel):
    name: str = Field(..., description="文档库名称")
    root_path: str = Field(..., description="本地目录绝对路径")
    description: str = Field("", description="文档库描述")


class LibraryUpdate(BaseModel):
    name: Optional[str] = Field(None, description="文档库名称")
    root_path: Optional[str] = Field(None, description="本地目录绝对路径")
    description: Optional[str] = Field(None, description="文档库描述")


# ── Customer ───────────────────────────────────────────────────────────────────

class CustomerCreate(BaseModel):
    name: str = Field(..., description="客户名称")
    contact: str = Field("", description="联系方式")
    note: str = Field("", description="备注")
    country: str = Field("", description="国家")
    tier: str = Field("", description="客户等级 (A/B/C)")
    linkedin_url: str = Field("", description="LinkedIn URL")


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, description="客户名称")
    contact: Optional[str] = Field(None, description="联系方式")
    note: Optional[str] = Field(None, description="备注")
    country: Optional[str] = Field(None, description="国家")
    tier: Optional[str] = Field(None, description="客户等级 (A/B/C)")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn URL")


# ── Conversation ───────────────────────────────────────────────────────────────

class ConversationSave(BaseModel):
    library_id: Optional[int] = Field(None, description="关联的文档库 ID")
    query: str = Field(..., description="用户问题")
    response: str = Field("", description="Agent 回复")
    files_read: list[dict] = Field(default_factory=list, description="读取的文件列表")
    library_name: str = Field("", description="文档库名称（用于上下文标注）")


class ConversationUpdate(BaseModel):
    response: str = Field(..., description="更新后的回复内容")


# ── Chat ───────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str = Field(..., description="用户问题")
    library_id: Optional[int] = Field(None, description="关联的文档库 ID")
    customer_id: Optional[int] = Field(None, description="关联的客户 ID")
