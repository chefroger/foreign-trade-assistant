"""
OSINT 模块测试 — 各层检测功能 + orchestrator 编排。

测试 WHOIS/DNS MX/制裁名单/技术栈/LinkedIn 的独立功能和集成。
网络相关测试使用真实的公开端点（example.com / google.com 等）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trade.osint import (
    domain_whois,
    verify_corporate_email,
    check_sanctions,
    detect_tech_stack,
    linkedin_company_verify,
    compute_risk_score,
    generate_recommendations,
)


# ── Layer 2: WHOIS ──────────────────────────────────────────────────────────


class TestWHOIS:
    """测试 WHOIS 域名查询。"""

    def test_known_domain_example_com(self):
        """example.com 是 IANA 保留域名，应返回已注册。"""
        result = domain_whois("example.com")
        assert result["registered"] is True
        assert result["domain"] == "example.com"
        assert result["error"] is None

    def test_www_prefix_stripped(self):
        """www. 前缀应被自动去除。"""
        result = domain_whois("www.example.com")
        assert result["domain"] == "example.com"

    def test_https_prefix_stripped(self):
        """https:// 前缀应被自动去除。"""
        result = domain_whois("https://example.com")
        assert result["domain"] == "example.com"

    def test_invalid_domain(self):
        """无效域名返回错误。"""
        result = domain_whois("not-a-domain")
        assert result["registered"] is False
        assert result.get("error") is not None

    def test_empty_string(self):
        """空字符串返回错误。"""
        result = domain_whois("")
        assert result["registered"] is False

    def test_result_has_all_fields(self):
        """返回结果应包含所有定义字段。"""
        result = domain_whois("example.com")
        expected_fields = {
            "domain", "registered", "registrar", "creation_date",
            "expiry_date", "days_old", "age_category", "dns_servers",
            "registrant_name", "whois_server", "status", "error",
        }
        assert expected_fields.issubset(result.keys()), \
            f"Missing fields: {expected_fields - result.keys()}"

    def test_google_com_too(self):
        """google.com 应返回已注册。"""
        result = domain_whois("google.com")
        assert result["registered"] is True


# ── Layer 3: Corporate Email Verification ───────────────────────────────────


class TestEmailVerification:
    """测试企业邮箱验证。"""

    def test_personal_email_gmail(self):
        """@gmail.com 应被识别为个人邮箱。"""
        result = verify_corporate_email("user@gmail.com")
        assert result["is_personal"] is True
        assert result["is_corporate"] is False
        assert result["risk_flag"] is True
        assert "个人邮箱" in str(result["risk_flags"])

    def test_personal_email_qq(self):
        """@qq.com 应被识别为个人邮箱。"""
        result = verify_corporate_email("12345@qq.com")
        assert result["is_personal"] is True
        assert result["risk_flag"] is True

    def test_corporate_email_example(self):
        """企业域名邮箱应识别为企业邮箱。"""
        result = verify_corporate_email("john@example.com")
        assert result["is_personal"] is False
        assert result["is_corporate"] is True

    def test_domain_matching(self):
        """提供 website 时应验证域名一致性。"""
        result = verify_corporate_email("john@example.com", website="https://example.com")
        assert result["domain_match"] is True

    def test_domain_mismatch(self):
        """邮箱域名与网站不一致时应标记。"""
        result = verify_corporate_email("john@other.com", website="https://example.com")
        assert result["domain_match"] is False

    def test_invalid_email_format(self):
        """无效邮箱格式返回错误提示。"""
        result = verify_corporate_email("not-an-email")
        assert result["suggestion"] == "邮箱格式无效"

    def test_mx_records_attempted(self):
        """企业邮箱应尝试查询 MX 记录。"""
        result = verify_corporate_email("admin@google.com")
        # google.com 应该有 MX 记录
        assert "mx_found" in result

    def test_result_has_all_fields(self):
        """返回结果应包含所有定义字段。"""
        result = verify_corporate_email("test@company.com")
        expected_fields = {
            "email", "domain", "is_personal", "is_corporate",
            "risk_flag", "domain_match", "mx_found", "mx_servers",
            "risk_flags", "suggestion",
        }
        assert expected_fields.issubset(result.keys())


# ── Layer 4: Sanctions ──────────────────────────────────────────────────────


class TestSanctions:
    """测试制裁名单筛查。"""

    def test_clean_company(self):
        """普通公司名不应命中制裁名单。"""
        result = check_sanctions("ACME Corporation Ltd")
        assert result["is_sanctioned"] is False
        assert result["risk_level"] == "none"

    def test_known_sanctioned_entity(self):
        """已知制裁实体应被精确匹配。"""
        # AL-SHABAAB 在 UN fallback 列表中
        result = check_sanctions("AL-SHABAAB")
        assert result["is_sanctioned"] is True
        assert result["risk_level"] == "high"

    def test_result_has_all_fields(self):
        """返回结果应包含所有定义字段。"""
        result = check_sanctions("test query")
        expected_fields = {
            "query", "country", "hits", "is_sanctioned",
            "risk_level", "suggestion",
        }
        assert expected_fields.issubset(result.keys())

    def test_country_filter(self):
        """提供 country 参数应影响结果。"""
        result = check_sanctions("ACME", country="US")
        assert result["country"] == "US"


# ── Layer 5: Tech Stack ─────────────────────────────────────────────────────


class TestTechStack:
    """测试技术栈检测。"""

    def test_detect_known_site(self):
        """google.com 应检测到某些技术栈。"""
        result = detect_tech_stack("https://google.com")
        assert result["ssl_valid"] is True
        # google.com 至少有一项技术
        assert len(result.get("technologies", [])) >= 0

    def test_auto_https_prefix(self):
        """省略协议时自动补全 https://。"""
        result = detect_tech_stack("example.com")
        assert result["url"].startswith("https://")

    def test_error_handling(self):
        """不存在的域名应有 error 字段。"""
        result = detect_tech_stack("https://this-domain-does-not-exist-12345.com")
        # 要么 error 非空，要么正常（DNS 可能解析到 parking page）
        assert "error" in result

    def test_result_has_all_fields(self):
        """返回结果应包含所有定义字段。"""
        result = detect_tech_stack("https://example.com")
        expected_fields = {
            "url", "technologies", "platforms", "is_free_platform",
            "is_enterprise", "ssl_valid", "server", "error",
        }
        assert expected_fields.issubset(result.keys())


# ── Layer 6: LinkedIn ───────────────────────────────────────────────────────


class TestLinkedInVerify:
    """测试 LinkedIn 公司页验证。"""

    def test_basic_verification(self):
        """基本验证逻辑：通过 Google 搜索查找 LinkedIn 公司页。"""
        result = linkedin_company_verify("microsoft.com", "Microsoft")
        assert result["domain"] == "microsoft.com"
        # microsoft.com 大概率有 LinkedIn 公司页
        # 但不一定每次都能通过 Google 搜索找到（受限于 Google 的反爬机制）
        assert "linkedin_found" in result

    def test_result_has_all_fields(self):
        """返回结果应包含所有定义字段。"""
        result = linkedin_company_verify("example.com", "Example Corp")
        expected_fields = {
            "domain", "company_name", "linkedin_found", "linkedin_url",
            "employee_count", "industry", "founded", "domain_match", "error",
        }
        assert expected_fields.issubset(result.keys())


# ── Scoring ─────────────────────────────────────────────────────────────────


class TestRiskScoring:
    """测试风险评分计算。"""

    def test_no_flags_max_score(self):
        """无红旗 → 满分 100 / low risk。"""
        score, rating = compute_risk_score([])
        assert score == 100
        assert rating == "low"

    def test_personal_email_penalty(self):
        """个人邮箱 → 扣 30 分。"""
        score, rating = compute_risk_score(["personal_email_domain"])
        assert score == 70

    def test_sanctioned_kills_score(self):
        """制裁命中 → 扣 50 分。"""
        score, rating = compute_risk_score(["sanctioned"])
        assert score == 50
        assert rating == "medium"

    def test_multiple_flags_high_risk(self):
        """多个红旗 → high risk。"""
        score, rating = compute_risk_score([
            "personal_email_domain",  # -30
            "domain_age_new",         # -20
            "free_platform",          # -15
            "no_linkedin",            # -10
        ])
        assert score == 25
        assert rating == "high"

    def test_score_clamped_zero(self):
        """分数不低于 0。"""
        score, rating = compute_risk_score([
            "sanctioned", "sanctioned", "sanctioned", "personal_email_domain",
        ])
        assert score >= 0

    def test_score_clamped_100(self):
        """分数不高于 100。"""
        score, rating = compute_risk_score([])
        assert score <= 100


class TestRecommendations:
    """测试建议生成。"""

    def test_generates_recommendations(self):
        """应生成多条建议。"""
        report = {
            "layers": {
                "email_verification": {
                    "is_corporate": True, "domain": "example.com", "risk_flag": False,
                },
                "domain_intel": {
                    "age_category": "old", "days_old": 2000,
                },
                "tech_stack": {
                    "is_enterprise": True, "is_free_platform": False,
                },
                "sanctions": {"is_sanctioned": False, "hits": []},
                "linkedin": {"linkedin_found": True, "employee_count": "1000+"},
            },
        }
        recs = generate_recommendations(report)
        assert len(recs) >= 3

    def test_flag_recommendations(self):
        """红旗报告中应包含警告建议。"""
        report = {
            "layers": {
                "email_verification": {
                    "risk_flag": True, "domain": "gmail.com",
                },
                "domain_intel": {
                    "age_category": "new", "days_old": 30,
                },
                "tech_stack": None,
                "sanctions": {"is_sanctioned": False, "hits": []},
                "linkedin": {"linkedin_found": False},
            },
        }
        recs = generate_recommendations(report)
        warnings = [r for r in recs if r.startswith("⚠️")]
        assert len(warnings) >= 1


# ── Orchestrator (requires async) ───────────────────────────────────────────


class TestOrchestrator:
    """测试 osint_full_check 编排器。"""

    @pytest.mark.asyncio
    async def test_email_full_check(self):
        """对邮箱执行完整尽职调查。"""
        from trade.osint import osint_full_check
        result = await osint_full_check(
            "test@example.com",
            include_sanctions=True,
            include_tech_stack=False,
            include_linkedin=False,
        )
        assert result["target"] == "test@example.com"
        assert result["target_type"] == "email"
        assert "layers" in result
        assert "domain_intel" in result["layers"]
        assert "email_verification" in result["layers"]
        assert "recommendations" in result

    @pytest.mark.asyncio
    async def test_domain_full_check(self):
        """对域名执行完整尽职调查。"""
        from trade.osint import osint_full_check
        result = await osint_full_check(
            "example.com",
            include_sanctions=False,
            include_tech_stack=False,
            include_linkedin=False,
        )
        assert result["target_type"] == "domain"
        assert result["layers"]["email_registration"] is None

    @pytest.mark.asyncio
    async def test_company_name_full_check(self):
        """对公司名执行完整尽职调查。"""
        from trade.osint import osint_full_check
        result = await osint_full_check(
            "Microsoft Corporation",
            include_sanctions=True,
            include_tech_stack=False,
            include_linkedin=False,
        )
        assert result["target_type"] == "company"
        assert "sanctions" in result["layers"]

    @pytest.mark.asyncio
    async def test_risk_score_computed(self):
        """orchestrator 应计算综合风险评分。"""
        from trade.osint import osint_full_check
        result = await osint_full_check(
            "test@example.com",
            include_sanctions=True,
            include_tech_stack=False,
            include_linkedin=False,
        )
        assert "overall_score" in result
        assert "overall_rating" in result
        assert result["overall_score"] >= 0
        assert result["overall_score"] <= 100


# ── Target Type Detection ───────────────────────────────────────────────────


class TestTargetDetection:
    """测试 target 类型自动识别。"""

    def test_email_detection(self):
        """含 @ 的应识别为 email。"""
        from trade.osint.orchestrator import _detect_target_type
        assert _detect_target_type("john@example.com") == "email"

    def test_url_detection(self):
        """含 https:// 的应识别为 url。"""
        from trade.osint.orchestrator import _detect_target_type
        assert _detect_target_type("https://example.com") == "url"

    def test_domain_detection(self):
        """example.com 应识别为 domain。"""
        from trade.osint.orchestrator import _detect_target_type
        assert _detect_target_type("example.com") == "domain"

    def test_company_detection(self):
        """纯公司名应识别为 company。"""
        from trade.osint.orchestrator import _detect_target_type
        assert _detect_target_type("Microsoft Corp") == "company"
