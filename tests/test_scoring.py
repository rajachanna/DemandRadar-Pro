import pytest
from datetime import datetime, timezone, timedelta
from demandradar.scoring import score_opportunity, clean_public_url, public_text, parse_iso

NOW = datetime(2026,11,15,tzinfo=timezone.utc)

@pytest.mark.parametrize("text,category", [
    ("MT5 MQL5 Expert Advisor", "MT5 / Trading Automation"),
    ("Pine Script TradingView automation", "MT5 / Trading Automation"),
    ("n8n workflow automation AI agent RAG", "AI Agents & Automation"),
    ("FastAPI REST API webhook dashboard", "Web Apps & APIs"),
    ("Shopify API integration", "Web Apps & APIs"),
    ("Twilio voice agent customer support automation", "AI Agents & Automation"),
    ("IBKR algo connector", "MT5 / Trading Automation"),
])
def test_category_match(text,category):
    assert score_opportunity(text,"", now=NOW).category==category


def test_explicit_budget_not_verified():
    s=score_opportunity("Need MT5 developer", "We have budget $1,800 for this contract",now=NOW)
    assert s.budget_evidence=="$1,800"
    assert not s.payment_verified
    assert any("not verified" in r for r in s.reasons)


def test_unpaid_not_claimed_paid():
    s=score_opportunity("Python API developer needed", "volunteer only unpaid. Budget $100",now=NOW)
    assert s.budget_evidence is None
    assert "Unpaid/volunteer indication" in s.reasons


def test_recency_gain():
    recent=(NOW-timedelta(days=2)).isoformat()
    old=(NOW-timedelta(days=90)).isoformat()
    a=score_opportunity("FastAPI developer", "",recent,now=NOW)
    b=score_opportunity("FastAPI developer", "",old,now=NOW)
    assert a.value>b.value


def test_urgency_is_not_guarantee():
    s=score_opportunity("AI workflow automation urgent", "Need developer ASAP",now=NOW)
    assert any("unverified" in r for r in s.reasons)


def test_bounded_score():
    s=score_opportunity(" ".join(["mt5 mql5 expert advisor ibkr TradingView pine script"]*50),"hiring asap",now=NOW)
    assert 0<=s.value<=100


def test_unknown_text_safe():
    s=score_opportunity("hello", "some unrelated description",now=NOW)
    assert s.value<20
    assert "No specific skill evidence" in s.reasons

@pytest.mark.parametrize("raw,expected",[
    ("https://github.com/a/b/issues/1?utm_source=foo&filter=all", "https://github.com/a/b/issues/1?filter=all"),
    ("https://example.com/", "https://example.com/"),
    ("https://Example.COM/path/#item", "https://example.com/path"),
])
def test_normalize_url(raw,expected):
    assert clean_public_url(raw)==expected

@pytest.mark.parametrize("bad",[
    "javascript:alert(1)", "http://example.org/", "https://user:pass@example.com/x",
    "https://localhost/admin", "https://127.0.0.1/admin", "https://dev.local/test", "nope",
    "https://example.com/"+"x"*1900,
])
def test_reject_untrusted_url(bad):
    with pytest.raises(ValueError):clean_public_url(bad)


def test_redacts_public_contacts():
    v=public_text("<p>Contact alpha@example.com or +1 (213) 555-1212 for a Python bot</p>")
    assert "alpha@example.com" not in v
    assert "[contact redacted]" in v
    assert "<p>" not in v


def test_parse_iso_time():
    assert parse_iso("2026-01-01T05:00:00Z").tzinfo is not None
    assert parse_iso("not-date") is None
    assert parse_iso("") is None


def test_text_limit():
    assert len(public_text("abc "*3000,40))<=40
