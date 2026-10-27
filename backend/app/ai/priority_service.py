import re
from typing import Tuple, Optional
from app.models.complaint import ComplaintPriority

CRITICAL_WORDS = [
    # Immediate Life & Safety Hazards (24h SLA)
    "emergency", "urgent", "danger", "dangerous", "fire", "accident", "life threatening",
    "life danger", "critical", "live wire", "open wire", "spark", "sparking", "electric shock",
    "short circuit", "dangling wire", "collapsed", "explosion", "hospital road blocked",
    "ambulance blocked", "gas leak", "toxic", "open manhole", "manhole open", "sinkhole",
    "deep trench", "transformer blast", "open fuse",
    # Tanglish
    "avasaram", "aabathu", "aapathu", "uyirukku aabathu", "urgent ah", "danger ah",
    "romba danger", "thee", "thee pidithathu", "accident aachu", "wire arunthu",
    "kambi arunthu", "shock adikithu", "current shock", "thirandha manhole",
    # Tamil
    "அவசரம்", "ஆபத்து", "தீ", "தீ விபத்து", "விபத்து", "உயிருக்கு ஆபத்து", "மின் கசிவு",
    "கம்பி அறுந்து", "மின் அதிர்ச்சி", "அதி அவசரம்", "அபாயம்", "திறந்த மேன்ஹோல்",
    "இடிந்து விழுந்தது", "உயிர் சேதம்"
]

HIGH_WORDS = [
    # Major Water Pipeline Bursts & Flooding Mains (48h SLA)
    "pipeline burst", "pipe burst", "major pipeline leak", "broken main",
    "water completely cut", "drinking water completely cut", "flooding the road",
    "குழாய் உடைந்து வெள்ளம்", "குழாய் உடைப்பு", "குடிநீர் தட்டுப்பாடு தீவிரமாக",
    # Sewage Overflow & Drainage Flooding into Houses/Streets
    "drainage overflow", "sewage overflow", "sewage entering house", "choked drain",
    "flooding", "water stagnation", "sakkadai thanni", "drainage adaippu",
    "thengi nikkuthu", "veetukulla thanni", "romba mosam",
    "சாக்கடை நீர்", "சாக்கடை வழிந்து", "வடிகால் அடைப்பு", "வெள்ளம்", "வீட்டுக்குள் கழிவுநீர்",
    # Severe Road Hazards & Accident Risks
    "massive pothole", "deep potholes", "damaged heavily with potholes", "accident prone",
    "road cave in", "periya pallam", "accident aaguthu", "road full-ah pallam",
    "ரோட்டில் பெரிய பள்ளம்", "விபத்து ஏற்படுகிறது", "சாலை பெரும் சேதம்",
    # Power Blackouts & Substation Outages
    "complete blackout", "blackout", "agricultural power cut", "entire village power cut",
    "முழுமையான மின் தடை", "கிராமத்தில் மின்சாரம் இல்லை",
    # Sanitation - Severe Multi-day Uncleared Waste & Stench
    "garbage dump not cleared for 4 days", "garbage not cleared for 4 days",
    "dustbin overflowing for days", "stench", "dead animal", "heavy stench",
    "romba naaththam", "துர்நாற்றம் வீசுகிறது", "துர்நாற்றம்", "குப்பை நிரம்பி வழிந்து",
    # Dark Bridges & Highways
    "entire road dark", "bridge lights not working", "dark road on highway",
    "மேம்பாலத்தில் விளக்குகள் எரியாமல்",
    # Multi-day and Wide Scope Indicators
    "3 days", "4 days", "three days", "four days", "rendu naala full street", "entire street", "all houses"
]

LOW_WORDS = [
    # Suggestions, Informational Requests, Routine Queries, Aesthetics (120h SLA)
    "suggestion", "information", "inquiry", "aesthetic", "signboard", "nameboard",
    "name plate", "painting", "bench repair", "park bench", "minor pruning",
    "tree branch trimming", "routine maintenance", "feedback", "certificate",
    "ration card query", "ration query", "request for park", "footpath tile loose",
    "minor paint", "small request",
    # Tanglish & Tamil
    "parinthuraigal", "thakaval", "vanna poosu", "peyar palagai", "siriya vishayam",
    "arisi varala", "ration rice query",
    "பரிந்துரை", "தகவல்", "பெயர் பலகை", "வண்ணம் பூசுதல்", "பூங்கா", "சிறு பழுது",
    "ரேஷன் கடையில் அரிசி", "விவரம்"
]


def assess_priority(
    text: str,
    category: str = "General",
    duration: Optional[str] = None,
    scope: Optional[str] = None,
    hazard: Optional[str] = None
) -> Tuple[ComplaintPriority, float]:
    """
    Determines complaint urgency: CRITICAL, HIGH, MEDIUM, LOW.
    Analyzes complaint text, category, duration, scope, and reported safety hazards.
    Returns: (ComplaintPriority, confidence)
    """
    if not text:
        return ComplaintPriority.MEDIUM, 0.5

    combined = f"{text} {duration or ''} {scope or ''} {hazard or ''}".lower()

    # Rule 1: Immediate Life & Safety Hazards (CRITICAL - 24h SLA)
    for word in CRITICAL_WORDS:
        if word in combined:
            return ComplaintPriority.CRITICAL, 0.95

    # Public Safety emergency override if hazard is indicated
    if category in ["Public Safety", "Electricity"] and any(w in combined for w in ["hazard", "wire", "shock", "fire", "danger", "pit", "hole", "accident", "விபத்து", "ஆபத்து"]):
        return ComplaintPriority.CRITICAL, 0.92

    # Rule 2: High Severity Civic Failures (HIGH - 48h SLA)
    for word in HIGH_WORDS:
        if word in combined:
            return ComplaintPriority.HIGH, 0.88

    # Direct Safety Hazard check (Immediate Emergency -> CRITICAL)
    if hazard and str(hazard).strip().lower() not in ["none", "no", "illa", "illai", "nothing", "இல்லை", "ஆபத்து இல்லை"]:
        if any(w in str(hazard).lower() for w in ["wire", "spark", "shock", "fire", "danger", "risk", "accident", "thee", "aabathu", "aapathu", "தீ", "ஆபத்து", "விபத்து", "கசிவு"]):
            return ComplaintPriority.CRITICAL, 0.95

    # Category-specific High overrides based on duration or scope
    dur_triggers = [
        "3 days", "4 days", "5 days", "three days", "four days", "one week", "two weeks", "2 days", "two days",
        "3 naala", "moonu naala", "2 naala", "rendu naala", "4 naala", "naalu naala", "5 naala",
        "oru varam", "romba naala", "pala naala", "many days", "several days",
        "ஒரு வாரம்", "வாரமாக", "மூன்று நாட்கள்", "நான்கு நாட்கள்", "இரண்டு நாட்கள்", "பல நாட்களாக"
    ]
    if any(d in combined for d in dur_triggers):
        if any(cat_match in category.lower() for cat_match in ["water", "drainage", "electric", "power", "sanitation", "garbage", "sewage", "road"]):
            return ComplaintPriority.HIGH, 0.88

    scope_triggers = [
        "entire locality", "all houses", "full street", "entire street", "whole street", "full-ah", "fulla",
        "moththa theru", "ellarukum", "முழு தெரு", "அனைத்து வீடுகளும்", "தெரு முழுவதும்", "ஊர் முழுக்க"
    ]
    if any(s in combined for s in scope_triggers):
        if any(cat_match in category.lower() for cat_match in ["water", "drainage", "electric", "power", "sewage", "road"]):
            return ComplaintPriority.HIGH, 0.88

    # Rule 3: Low Priority (Aesthetic, Suggestions, Non-Urgent Queries - 120h SLA)
    for word in LOW_WORDS:
        if word in combined:
            return ComplaintPriority.LOW, 0.80

    # Rule 4: Standard Civic Grievance (MEDIUM - 72h SLA)
    # Covers standard single-point grievances: domestic hand pump repair, single street light bulb,
    # regular potholes, routine garbage collection delay, low water pressure.
    return ComplaintPriority.MEDIUM, 0.75
