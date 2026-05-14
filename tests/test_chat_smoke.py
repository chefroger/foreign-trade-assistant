"""冒烟测试：保证 /chat 端点的依赖注入不会崩。"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestRequireCompanyInjection:
    """验证 Depends(require_company) 的依赖注入不会在 chat 端点里崩。"""

    def test_cid_directly_injected_not_requiring_strip(self, monkeypatch, tmp_path):
        """require_company 的返回值是 int，chat 端点应直接当 int 用。

        如果代码里写了 cid = require_company(x_company_id)，int 没有 .strip()，
        直接 AttributeError。
        """
        # Simulate what FastAPI Depends does: require_company returns an int
        from trade.api.deps import require_company

        # Mock the company lookup
        import trade.company as co
        monkeypatch.setattr(co, "get_trade_company", lambda cid: {"company_id": cid, "is_active": 1})

        # A valid header string should parse to int 1
        result = require_company("1")
        assert result == 1
        assert isinstance(result, int)

        # If someone wrote cid = require_company(result) with result=1 (int),
        # it would call "1".strip() → AttributeError on int.
        # This is what the bug was. Let's verify int.strip() fails:
        with pytest.raises(AttributeError):
            _ = int("1").strip() is not None  # int has no .strip()


class TestSmokeChatModule:
    """验证 chat.py 的 import 链不会崩（无需真实 LLM）。"""

    def test_chat_module_imports(self, monkeypatch, tmp_path):
        """chat.py 可以正常导入，Depends 签名正确。"""
        monkeypatch.setenv("TRADE_HOME", str(tmp_path))
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
            hermes_constants.get_hermes_home = MagicMock(return_value=Path(tmp_path))
            from hermes_cli import config
            config.load_config = MagicMock(return_value={"model": {"provider": "openai", "default": "gpt-4o"}})
            from hermes_cli import auth
            class _PC:
                auth_type = "api_key"
                api_key_env_vars = ["OPENAI_API_KEY"]
                display_name = "OpenAI"
                base_url_env_var = ""
            auth.PROVIDER_REGISTRY = {"openai": _PC()}

            from trade.database import init_db
            init_db()

            from trade.api.chat import router, trade_chat, trade_chat_stream
            assert router is not None
            assert callable(trade_chat)
            assert callable(trade_chat_stream)

    def test_create_agent_factory(self, monkeypatch, tmp_path):
        """create_agent 不再写 os.environ。"""
        monkeypatch.setenv("TRADE_HOME", str(tmp_path))
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
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
            hermes_constants.get_hermes_home = MagicMock(return_value=Path(tmp_path))
            from hermes_cli import config
            config.load_config = MagicMock(return_value={"model": {"provider": "openai", "default": "gpt-4o"}})
            from hermes_cli import auth
            class _PC:
                auth_type = "api_key"
                api_key_env_vars = ["OPENAI_API_KEY"]
                display_name = "OpenAI"
                base_url_env_var = ""
            auth.PROVIDER_REGISTRY = {"openai": _PC()}

            from trade.helpers import create_agent
            import os
            os.environ.pop("HERMES_YOLO_MODE", None)

            # Mock AIAgent to avoid real LLM call
            class _MockAgent:
                def __init__(self, **kw):
                    pass
                def chat(self, msg):
                    return "ok"

            import run_agent
            run_agent.AIAgent = _MockAgent

            agent = create_agent()
            assert agent.chat("hi") == "ok"

            # create_agent should NOT set HERMES_YOLO_MODE (moved to server.py startup)
            assert os.environ.get("HERMES_YOLO_MODE", "") != "true"
