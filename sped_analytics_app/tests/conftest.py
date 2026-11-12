import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SPED_DATA_DIR", tempfile.mkdtemp(prefix="sped_test_"))
os.environ.setdefault("SPED_PARSER_WORKERS", "2")
