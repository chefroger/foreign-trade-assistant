"""
测试全局配置 — 必须在任何 trade 模块 import 之前执行。

设置 TRADE_HOME 环境变量，防止 _setup_work_directory 和 _get_trade_home 触碰真实桌面。
"""
import os
import tempfile

# 在第 0 步：在所有 import 之前设置 TRADE_HOME
# 这样 trade.company 模块级别的 TRADE_HOME 常量就会指向临时路径
if "TRADE_HOME" not in os.environ:
    os.environ["TRADE_HOME"] = tempfile.mkdtemp(prefix="trade-test-")
