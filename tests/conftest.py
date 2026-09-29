# Lets tests import modules from src/ (run pytest from the project root).
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
