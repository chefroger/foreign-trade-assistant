"""
API 层测试 — FastAPI 端点 + skill_router 匹配。

直接测试路由函数（不经过 HTTP），mock 外部 Hermes 依赖。
HTTP 层测试通过 run_server_smoke 验证即可。
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def setup_mocks():
    """模块级 mock Hermes 依赖。"""
    with patch.dict(sys.modules, {
        "hermes_cli": MagicMock(),
        "hermes_cli.config": MagicMock(),
        "hermes_cli.auth": MagicMock(),
        "hermes_cli.env_loader": MagicMock(),
        "hermes_cli.models": MagicMock(),
        "hermes_constants": MagicMock(),
        "run_agent": MagicMock(),
    }):
        import hermes_cli
        hermes_cli.__version__ = "0.13.0"

        from hermes_cli import env_loader
        env_loader.load_hermes_dotenv = MagicMock()

        import hermes_constants
        hermes_constants.get_hermes_home = MagicMock(return_value=Path("/tmp/.hermes"))

        from hermes_cli import config
        config.load_config = MagicMock(return_value={
            "model": {"provider": "openai", "default": "gpt-4o"}
        })

        from hermes_cli import auth
        class MockProviderConfig:
            auth_type = "api_key"
            api_key_env_vars = ["OPENAI_API_KEY"]
            display_name = "OpenAI"
            base_url_env_var = ""

        auth.PROVIDER_REGISTRY = {"openai": MockProviderConfig()}
        yield


@pytest.fixture
def test_db(monkeypatch, tmp_path, setup_mocks):
    """创建临时测试数据库。"""
    db_path = tmp_path / "trade.db"

    import trade.database as _db
    original = _db._get_db_path
    _db._get_db_path = lambda: db_path

    from trade.database import get_connection, SCHEMA_SQL, _add_spare_columns
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_SQL)
    _add_spare_columns(conn)
    conn.commit()
    conn.close()

    yield db_path

    _db._get_db_path = original


@pytest.fixture
def company_id(test_db):
    """创建测试公司并返回 ID。"""
    from trade import company
    c = company.create(name="API Test Company", slug="api-test-company")
    return c["id"]


# ── Deps 测试 ──────────────────────────────────────────────────────────────


class TestDeps:
    """测试 API 依赖函数。"""

    def test_require_company_valid(self, company_id, setup_mocks):
        """有效的 X-Company-ID 返回 company_id。"""
        from trade.api.deps import require_company
        # 直接调用函数（绕过 FastAPI Header 依赖注入）
        result = require_company(str(company_id))
        assert result == company_id

    def test_require_company_missing(self, setup_mocks):
        """缺失 header → 401。"""
        from trade.api.deps import require_company
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            require_company("")
        assert exc_info.value.status_code == 401

    def test_require_company_invalid(self, setup_mocks):
        """无效 header → 401。"""
        from trade.api.deps import require_company
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            require_company("not-an-int")
        assert exc_info.value.status_code == 401

    def test_opt_company_missing(self, setup_mocks):
        """缺失 header → None。"""
        from trade.api.deps import opt_company
        assert opt_company("") is None
        assert opt_company(None) is None


# ── Router Assembly 测试 ────────────────────────────────────────────────────


class TestRouterAssembly:
    """测试路由组装和注册。"""

    def test_router_imports_and_registers(self, setup_mocks):
        """router 对象可正常导入且注册了所有端点类型。"""
        from trade.api import router
        assert router is not None

        # 收集路由路径前缀
        paths = set()
        for route in router.routes:
            if hasattr(route, 'path'):
                paths.add(route.path.split('/')[1] if route.path.startswith('/') else '')

        # 应包含所有主要域
        key_routes = set()
        for route in router.routes:
            if hasattr(route, 'path'):
                p = route.path
                for keyword in ['companies', 'libraries', 'customers', 'conversations',
                                'chat', 'memory', 'onboarding', 'models']:
                    if keyword in p:
                        key_routes.add(keyword)

        assert 'companies' in key_routes
        assert 'libraries' in key_routes
        assert 'customers' in key_routes
        assert 'chat' in key_routes

    def test_all_endpoints_registered(self, setup_mocks):
        """所有 endpoint 数量符合预期（至少 25 个）。"""
        from trade.api import router
        # 收集所有 HTTP 路由路径
        endpoints = []
        for route in router.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                for method in route.methods:
                    if method in ('GET', 'POST', 'PUT', 'DELETE'):
                        endpoints.append(f"{method} {route.path}")

        # 至少应有 25 个端点
        assert len(endpoints) >= 25, f"Expected >= 25 endpoints, got {len(endpoints)}"


# ── Skill Router Tests ──────────────────────────────────────────────────────


class TestSkillRouter:
    """测试 skill_router 匹配逻辑。"""

    def test_match_b2b_osint(self):
        from trade.skill_router import match_skill
        result = match_skill("帮我背调一下这家公司")
        assert result is not None
        assert result["name"] == "b2b-osint"

    def test_match_lead_generation(self):
        from trade.skill_router import match_skill
        result = match_skill("帮我写一封开发信给欧洲客户")
        assert result is not None
        assert result["name"] == "b2b-lead-generation"

    def test_match_document_analysis(self):
        from trade.skill_router import match_skill
        result = match_skill("分析这份产品报价单文档")
        assert result is not None
        assert result["name"] in ("b2b-document", "b2b-lead-generation")

    def test_match_platform_diagnosis(self):
        from trade.skill_router import match_skill
        result = match_skill("帮我优化阿里国际站的产品标题")
        assert result is not None
        assert result["name"] == "b2b-platform"

    def test_match_linkedin_marketing(self):
        from trade.skill_router import match_skill
        result = match_skill("帮我做一个LinkedIn营销方案")
        assert result is not None
        assert result["name"] == "b2b-linkedin-marketing"

    def test_match_social_media(self):
        from trade.skill_router import match_skill
        result = match_skill("帮我规划一周的Facebook发帖内容")
        assert result is not None
        assert result["name"] == "b2b-social-media"

    def test_match_customs_data(self):
        from trade.skill_router import match_skill
        result = match_skill("分析这批海关数据的采购商")
        assert result is not None
        assert result["name"] == "b2b-customs-data"

    def test_match_onboarding(self):
        from trade.skill_router import match_skill
        result = match_skill("我是新公司，怎么开始使用")
        assert result is not None
        assert result["name"] == "b2b-onboarding"

    def test_match_document_generation(self):
        from trade.skill_router import match_skill
        result = match_skill("帮我做一份提案演示PPT")
        assert result is not None
        assert result["name"] == "b2b-doc-generation"

    def test_match_customer_management(self):
        from trade.skill_router import match_skill
        result = match_skill("查看我的客户列表")
        assert result is not None
        assert result["name"] == "b2b-customer-mgmt"

    def test_match_daily_automation(self):
        from trade.skill_router import match_skill
        result = match_skill("帮我设置早安简报自动发送")
        assert result is not None
        assert result["name"] == "b2b-daily-automation"

    def test_match_email_intel(self):
        from trade.skill_router import match_skill
        result = match_skill("查一下这个邮箱 john@test.com")
        assert result is not None
        assert result["name"] in ("b2b-email-intel", "b2b-osint")

    def test_explicit_skill_call(self):
        from trade.skill_router import match_skill
        result = match_skill("用 b2b-email-intel 查 john@test.com")
        assert result is not None
        assert result["name"] == "b2b-email-intel"

    def test_no_match_irrelevant(self):
        from trade.skill_router import match_skill
        assert match_skill("今天天气怎么样") is None

    def test_empty_query(self):
        from trade.skill_router import match_skill
        assert match_skill("") is None
        assert match_skill("   ") is None

    def test_augment_query_with_skill(self):
        from trade.skill_router import augment_query
        result = augment_query("帮我背调", skill_name="b2b-osint")
        assert "[SKILL AUGMENTATION]" in result
        assert "b2b-osint" in result
        assert "帮我背调" in result

    def test_augment_query_no_match(self):
        from trade.skill_router import augment_query
        original = "这是什么天气"
        assert augment_query(original) == original

    def test_skill_registry_count(self):
        """注册表应有 14 个 skill（13个业务 + 1个 chat-memory）。"""
        from trade.skill_registry import _SKILLS
        assert len(_SKILLS) == 14


# ── Company Endpoint Functions ──────────────────────────────────────────────


class TestCompanyEndpoints:
    """测试公司端点函数。"""

    def test_create_company(self, test_db, setup_mocks):
        from trade import company
        c = company.create(name="Endpoint Co", slug="endpoint-co")
        assert c["name"] == "Endpoint Co"
        assert c["slug"] == "endpoint-co"
        assert c["is_active"] is True

    def test_list_companies(self, test_db, company_id, setup_mocks):
        from trade import company
        companies = company.list_all()
        assert any(c["id"] == company_id for c in companies)

    def test_agent_identity(self, test_db, company_id, setup_mocks):
        from trade import company
        identity = company.get_agent_identity(company_id)
        assert isinstance(identity, str)  # may be empty, but should be a string

    def test_update_agent_identity(self, test_db, company_id, setup_mocks):
        from trade import company
        result = company.update_trade_company(company_id, agent_identity_md="Test identity")
        assert result["agent_identity_md"] == "Test identity"


# ── Library Endpoint Functions ──────────────────────────────────────────────


class TestLibraryEndpoints:
    """测试文档库端点函数。"""

    def test_create_and_list(self, test_db, company_id, setup_mocks):
        from trade import library
        lib = library.create("Endpoint Lib", "/tmp/eplib", company_id=company_id)
        assert lib["name"] == "Endpoint Lib"

        libs = library.list_by_company(company_id)
        assert any(l["id"] == lib["id"] for l in libs)

    def test_company_scoped_access(self, test_db, company_id, setup_mocks):
        from trade import library, company
        other = company.create(name="Other Co", slug="other-co-lib")
        lib = library.create("My Lib", "/tmp/mylib", company_id=company_id)

        # Other company shouldn't see this library
        assert library.get(lib["id"], company_id=other["id"]) is None


# ── Customer Endpoint Functions ─────────────────────────────────────────────


class TestCustomerEndpoints:
    """测试客户端点函数。"""

    def test_create_and_list(self, test_db, company_id, setup_mocks):
        from trade import customer
        cust = customer.create("Endpoint Customer", company_id=company_id)
        assert cust["name"] == "Endpoint Customer"

        custs = customer.list_by_company(company_id)
        assert any(c["id"] == cust["id"] for c in custs)


# ── Conversation Endpoint Functions ─────────────────────────────────────────


class TestConversationEndpoints:
    """测试对话端点函数。"""

    def test_save_conversation(self, test_db, company_id, setup_mocks):
        from trade import chat_memory
        conv = chat_memory.save(company_id, "Query", "Response",
                                 files_read=[{"file": "test.pdf", "pages": [1]}])
        assert conv["query"] == "Query"
        assert len(conv["files_read"]) == 1

    def test_list_conversations(self, test_db, company_id, setup_mocks):
        from trade import chat_memory
        chat_memory.save(company_id, "Q1", "A1")
        convs = chat_memory.list_by_company(company_id)
        assert len(convs) >= 1


# ── Onboarding Flow ─────────────────────────────────────────────────────────


class TestOnboardingFlow:
    """测试首次引导流程。"""

    def test_onboarding_status_new_db(self, test_db, setup_mocks):
        from trade import onboarding
        onboarding.reset_onboarding_flag()
        assert onboarding.is_onboarding_done() is False

    def test_create_first_company(self, test_db, setup_mocks):
        from trade import onboarding
        onboarding.reset_onboarding_flag()

        result = onboarding.create_first_company(
            company_name="Flow Test Co",
            contact_name="Alice",
            identity_data={
                "products": "Electronics",
                "differentiation": "OEM factory",
                "target_region": "Europe",
            },
        )
        assert result["company"]["name"] == "Flow Test Co"
        assert "Electronics" in result["trade_company"]["agent_identity_md"]
        assert onboarding.is_onboarding_done() is True

    def test_create_first_company_duplicate(self, test_db, company_id, setup_mocks):
        from trade import onboarding
        assert onboarding.is_onboarding_done() is True
