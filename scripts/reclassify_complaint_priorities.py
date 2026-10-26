"""
Reclassifies all existing complaints in voxentra.db according to the enhanced AI priority assessment engine.
"""

import sys
import io
from pathlib import Path

# Set up paths and UTF-8 console output
if sys.platform == "win32":
    reconfig = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfig):
        reconfig(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database.session import SessionLocal
from app.models.complaint import Complaint, ComplaintPriority
from app.ai.priority_service import assess_priority
from app.services.complaint_service import complaint_service
from collections import Counter

def reclassify_all_complaints():
    db = SessionLocal()
    try:
        complaints = db.query(Complaint).all()
        print(f"Total complaints found in database: {len(complaints)}")
        initial_counts = Counter(c.priority.value for c in complaints)
        print("Initial priority distribution:", initial_counts)

        updated_count = 0
        for c in complaints:
            title = c.title or ""
            desc = c.description or ""
            full_text = f"{title} {desc}".strip()
            category = c.category or "Other"

            # Check if ai_metadata has duration or scope
            duration = None
            scope = None
            hazard = None
            if c.ai_metadata and isinstance(c.ai_metadata, dict):
                duration = c.ai_metadata.get("duration")
                scope = c.ai_metadata.get("scope") or c.ai_metadata.get("affected_scope")
                hazard = c.ai_metadata.get("safety_hazard")

            new_prio, conf = assess_priority(
                text=full_text,
                category=category,
                duration=duration,
                scope=scope,
                hazard=hazard
            )

            if c.priority != new_prio:
                c.priority = new_prio
                c.due_at = complaint_service._calculate_due_date(new_prio)
                updated_count += 1

        db.commit()
        final_counts = Counter(c.priority.value for c in complaints)
        print(f"\nSuccessfully reclassified {updated_count} complaints based on severity and content.")
        print("New priority distribution:", final_counts)
        return final_counts
    finally:
        db.close()

if __name__ == "__main__":
    reclassify_all_complaints()
