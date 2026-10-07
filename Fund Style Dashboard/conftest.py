"""conftest.py — ให้ pytest หา config/data/analysis เจอ (รันจากที่ไหนก็ได้)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
