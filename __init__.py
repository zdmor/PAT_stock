"""价格行为学交易系统 (PAT) — Price Action Trading

基于 Al Brooks 三部曲的 A 股价格行为交易系统。
纯价格形态驱动, 不依赖技术指标。
"""

import sys
from pathlib import Path

# 统一 sys.path 管理: 确保 D:\ClaudeWorkspace 可 import (zhunwo 等)
_CLAUDE_ROOT = Path(__file__).resolve().parent.parent
if str(_CLAUDE_ROOT) not in sys.path:
    sys.path.insert(0, str(_CLAUDE_ROOT))

del Path
