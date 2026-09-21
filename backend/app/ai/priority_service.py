import re
from typing import Tuple
from app.models.complaint import ComplaintPriority

CRITICAL_WORDS = [
    # English
    "emergency", "urgent", "danger", "dangerous", "fire", "accident", "life threatening",
    "life danger", "critical", "live wire", "spark", "electric shock", "short circuit",
    "dangling wire", "collapsed", "explosion", "hospital road blocked",
    # Tanglish
    "avasaram", "aabathu", "aapathu", "uyirukku aabathu", "urgent ah", "danger ah",
    "romba danger", "thee", "accident aachu", "wire arunthu", "shock adikithu",
    # Tamil
    "அவசரம்", "ஆபத்து", "தீ", "விபத்து", "உயிருக்கு ஆபத்து", "மின் கசிவு",
    "கம்பி அறுந்து", "மின் அதிர்ச்சி", "அதி அவசரம்"
]

HIGH_WORDS = [
    # English
    "immediately", "serious", "severe", "major leak", "complete blackout",
    "flood", "flooding", "massive pothole", "stench", "drainage inside house",
    # Tanglish
    "udane", "udane seiyanum", "seekiram", "periya prachana", "heavy ah",
    "thengi nikkuthu", "veetukulla thanni", "romba mosam",
    # Tamil
    "உடனே", "உடனடியாக", "தீவிர", "பெரிய பிரச்சினை", "வெள்ளம்", "துர்நாற்றம்"
]

LOW_WORDS = [
    "suggestion", "information", "aesthetic", "inquiry", "minor", "small paint", "request"
]


def assess_priority(text: str, category: str) -> Tuple[ComplaintPriority, float]:
    """
    Determines complaint urgency: CRITICAL, HIGH, MEDIUM, LOW.
    Returns: (ComplaintPriority, confidence)
    """
    if not text:
        return ComplaintPriority.MEDIUM, 0.5

    lowered = text.lower()

    # Rule 1: Public Safety emergencies & live electrical hazards are Critical
    if category == "Public Safety":
        return ComplaintPriority.CRITICAL, 0.95

    # Rule 2: Critical keywords
    for word in CRITICAL_WORDS:
        if word in lowered:
            return ComplaintPriority.CRITICAL, 0.9

    # Rule 3: High keywords
    for word in HIGH_WORDS:
        if word in lowered:
            return ComplaintPriority.HIGH, 0.85

    # Rule 4: Low keywords
    for word in LOW_WORDS:
        if word in lowered:
            return ComplaintPriority.LOW, 0.8

    # Default to Medium for civic grievances
    return ComplaintPriority.MEDIUM, 0.75
