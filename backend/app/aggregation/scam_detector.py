"""Scam, fraud and suspicious opportunity detection engine.

Analyzes job listings for common predatory internship/job scam patterns
including fee demands, unverified contact channels, suspicious link shorteners,
and unrealistic compensation promises.
"""
import re
from typing import Dict, List, Any

# Critical red flag keywords that indicate monetary demands
PAYMENT_KEYWORDS = [
    r"\bregistration\s+fee\b",
    r"\bsecurity\s+deposit\b",
    r"\btraining\s+fee\b",
    r"\bprocessing\s+fee\b",
    r"\blaptop\s+charges?\b",
    r"\brefundable\s+amount\b",
    r"\bcaution\s+deposit\b",
    r"\bpay\s+(?:for|before)\s+(?:the\s+)?interview\b",
    r"\bpay\s+to\s+apply\b",
    r"\bdocument\s+verification\s+charges?\b",
    r"\buniform\s+charges?\b",
    r"\bbackground\s+check\s+fee\b",
]

SUSPICIOUS_LINK_PATTERNS = [
    r"\bbit\.ly\b",
    r"\btinyurl\.com\b",
    r"\bt\.me\b",
    r"\btelegram\.(?:me|org)\b",
    r"\bchat\.whatsapp\.com\b",
    r"\bwa\.me\b",
    r"\bgoo\.gl\b",
    r"\bis\.gd\b",
    r"\bbuff\.ly\b",
    r"\bow\.ly\b",
]

SUSPICIOUS_CONTACT_PATTERNS = [
    r"\b[a-zA-Z0-9_.+-]+@(gmail|yahoo|hotmail|outlook|rediffmail)\.com\b",
]


def assess_opportunity_risk(job: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluates a job record and returns a risk report with flags, score, and risk level.
    
    Risk Levels:
    - 'Low Risk': Normal corporate posting with valid channels.
    - 'Medium Risk': Contains unverified contact info, missing description, or slight anomalies.
    - 'High Risk': Direct mention of payments, security deposits, or predatory fees.
    - 'Requires Manual Review': Multiple warnings or unverified domains needing human audit.
    """
    flags: List[str] = []
    score = 0  # 0 to 100

    title = (job.get("title") or "").strip()
    company = (job.get("company") or "").strip()
    description = (job.get("description") or "").strip()
    url = (job.get("source_url") or job.get("link") or "").strip()
    stipend_raw = str(job.get("stipend") or "")
    ctc = float(job.get("ctc_lpa") or 0)

    combined_text = f"{title} {company} {description}".lower()

    # 1. Critical check: Fee / Payment demands (Instantly High Risk)
    for pattern in PAYMENT_KEYWORDS:
        if re.search(pattern, combined_text, re.IGNORECASE):
            match = re.search(pattern, combined_text, re.IGNORECASE).group(0)
            flags.append(f"Monetary demand detected: mention of '{match}'")
            score += 65

    # 2. Check for suspicious redirect or messaging app links
    for pattern in SUSPICIOUS_LINK_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE) or re.search(pattern, combined_text, re.IGNORECASE):
            flags.append("Contains suspicious redirect, Telegram, or WhatsApp group link instead of career portal")
            score += 35
            break

    # 3. Check for free webmail instead of official corporate domain in contacts
    for pattern in SUSPICIOUS_CONTACT_PATTERNS:
        if re.search(pattern, combined_text, re.IGNORECASE):
            flags.append("Personal/free email address (e.g. Gmail/Yahoo) used instead of official corporate domain")
            score += 20
            break

    # 4. Check for missing or extremely vague description
    if len(description) < 30 and not job.get("from_verified_ats"):
        flags.append("Extremely brief or missing job description")
        score += 15

    # 5. Check for missing or suspicious company name
    if not company or company.lower() in ("n/a", "unknown", "hiring company", "confidential"):
        flags.append("Unspecified or confidential company identity")
        score += 25

    # 6. Unrealistic compensation promises for student internships
    if ctc > 45:
        flags.append(f"Unusually high compensation promise ({ctc} LPA) for campus level opportunity")
        score += 20

    if any(term in stipend_raw.lower() for term in ["100000", "150000", "200000"]) and "year" not in stipend_raw.lower():
        flags.append("Disproportionately high monthly internship stipend claim")
        score += 15

    # Normalize score
    score = min(score, 100)

    # Determine risk level
    if score >= 60:
        level = "High Risk"
    elif score >= 35:
        level = "Requires Manual Review"
    elif score >= 20:
        level = "Medium Risk"
    else:
        level = "Low Risk"

    return {
        "risk_level": level,
        "risk_score": score,
        "risk_flags": flags,
    }
