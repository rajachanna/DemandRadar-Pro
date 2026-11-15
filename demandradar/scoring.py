"""Explainable scoring, not probabilistic claims or guarantees of paid work."""
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
import html
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str):
        self.parts.append(data)


def public_text(text: str, limit: int = 7000) -> str:
    """Remove HTML and public-post contact details we do not need to retain."""
    parser = _PlainText()
    parser.feed(html.unescape(text or ""))
    clean = " ".join(parser.parts)
    clean = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[contact redacted]", clean)
    clean = re.sub(r"(?<!\w)(?:\+?\d[\d .()\-]{8,}\d)(?!\w)", "[phone redacted]", clean)
    return re.sub(r"\s+", " ", clean).strip()[:limit]


def clean_public_url(value: str) -> str:
    """Store links only; never fetch user-supplied URLs (no SSRF surface)."""
    raw = str(value or "").strip()
    if len(raw) > 1800:
        raise ValueError("Link is too long")
    url = urlsplit(raw)
    if url.scheme != "https" or not url.netloc or url.username or url.password:
        raise ValueError("Provide a public HTTPS URL")
    host = (url.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} or host.endswith(".local"):
        raise ValueError("Local addresses are not accepted")
    # Strip tracking parameters; preserve actual issue or post IDs.
    allowed = [(k, v) for k, v in parse_qsl(url.query, keep_blank_values=True)
               if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    return urlunsplit(("https", url.netloc.lower(), url.path.rstrip("/") or "/", urlencode(allowed), ""))


SKILLS = {
    "MT5 / Trading Automation": {
        "mt5": 13, "mql5": 15, "metatrader": 14, "expert advisor": 15,
        "tradingview": 10, "pine script": 11, "ibkr": 11,
        "forex bot": 11, "copy trading": 8, "kalshi": 8, "polymarket": 8,
    },
    "AI Agents & Automation": {
        "ai agent": 14, "llm": 9, "rag": 9, "chatbot": 9,
        "n8n": 9, "voice agent": 14, "workflow automation": 15,
        "customer support automation": 14, "document extraction": 11,
    },
    "Web Apps & APIs": {
        "fastapi": 12, "python": 9, "web app": 10, "dashboard": 8,
        "api integration": 14, "rest api": 10, "shopify": 12,
        "webhook": 12, "saas": 8, "typescript": 7,
    },
}

BUYING = ("looking for developer", "looking to hire", "need a developer", "paid contract", "freelance", "contractor", "bounty", "budget", "hiring")
UNPAID = ("unpaid", "volunteer only", "no budget", "without pay", "free work")
URGENT = ("urgent", "asap", "this week", "immediately")
MONEY = re.compile(r"(?:\$|usd\s*)([\d,]+(?:\.\d{1,2})?)\s*(?:-|to|–)?\s*(?:\$|usd\s*)?([\d,]+(?:\.\d{1,2})?)?", re.I)


@dataclass(frozen=True)
class Score:
    value: int
    category: str
    reasons: tuple[str, ...]
    budget_evidence: str | None
    payment_verified: bool = False  # Never claim payment verified from a public post.


def parse_iso(value: str) -> datetime | None:
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
    except (ValueError, AttributeError):
        return None


def score_opportunity(title: str, description: str, published_at: str | None = None,
                      now: datetime | None = None) -> Score:
    text = f"{title} {description}".lower()
    now = now or datetime.now(timezone.utc)
    scores: dict[str, int] = {}
    matched: dict[str, list[str]] = {}
    for category, terms in SKILLS.items():
        found = [term for term in terms if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text)]
        matched[category] = found
        scores[category] = min(64, sum(terms[word] for word in found))
    category = max(scores, key=lambda c: scores[c])
    value = scores[category]
    reasons = [f"Skill match: {', '.join(matched[category][:4])}"] if matched[category] else ["No specific skill evidence"]
    if any(t in text for t in BUYING):
        value += 13
        reasons.append("Explicit project/hiring intent in text")
    if any(t in text for t in URGENT):
        value += 6
        reasons.append("Urgency mentioned; unverified")
    is_unpaid = any(t in text for t in UNPAID)
    budget = None
    match = MONEY.search(text)
    if match and not is_unpaid:
        budget = "$" + match.group(1) + (("–$" + match.group(2)) if match.group(2) else "")
        value += 9
        reasons.append("Dollar amount mentioned; payment not verified")
    if is_unpaid:
        value -= 25
        reasons.append("Unpaid/volunteer indication")
    published = parse_iso(published_at or "")
    if published:
        age = (now - published).total_seconds() / 86400
        if 0 <= age < 7:
            value += 8
            reasons.append("Posted in last 7 days")
        elif age > 45:
            value -= 10
            reasons.append("Older than 45 days")
    return Score(value=max(0, min(100, value)), category=category,
                 reasons=tuple(reasons), budget_evidence=budget)
