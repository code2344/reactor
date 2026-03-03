import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_PATH = ROOT / "src"
if SRC_PATH.exists() and str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from helios_core.channel_deviation_view import run_app


if __name__ == "__main__":
    run_app()
