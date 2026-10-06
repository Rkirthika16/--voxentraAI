"""Re-export of test_complaint_creation for root tests directory."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from backend.tests.test_complaint_creation import *
