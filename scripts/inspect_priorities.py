import sys
import io
from pathlib import Path
from collections import Counter

if sys.platform == "win32":
    reconfig = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfig):
        reconfig(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database.session import SessionLocal
from app.models.complaint import Complaint
from app.ai.priority_service import HIGH_WORDS, CRITICAL_WORDS, LOW_WORDS

db = SessionLocal()
comps = db.query(Complaint).all()
print("Total complaints:", len(comps))

for prio in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
    subset = [c for c in comps if c.priority.value == prio]
    print(f"\n--- {prio} ({len(subset)}) ---")
    for c in subset[:4]:
        print(f"  [{c.category}] {c.title[:35]} | {c.description[:45].strip()}")
