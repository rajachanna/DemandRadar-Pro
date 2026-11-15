"""Offline illustration: only synthetic records, no real lead claims or APIs."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from demandradar.sources import Candidate
from demandradar.storage import Store


def records():
    now = datetime.now(timezone.utc)
    return [
        Candidate("synthetic_demo", "D-101", "https://example.com/public-demo/mt5", "Need a custom MT5 Expert Advisor with configurable risk controls", "Paid project, budget $1400-$2200. Need a developer to build MQL5 EA with trailing stops, logs and broker-aware volume checks.", (now-timedelta(days=1)).isoformat(), "ILLUSTRATIVE DATA ONLY"),
        Candidate("synthetic_demo", "D-102", "https://example.com/public-demo/ai", "Looking for developer to build AI customer support agent", "We want RAG, escalation, API integration and human review. Budget $3000. This is an illustrative client request.", (now-timedelta(days=2)).isoformat(), "ILLUSTRATIVE DATA ONLY"),
        Candidate("synthetic_demo", "D-103", "https://example.com/public-demo/shopify", "Shopify webhook dashboard and inventory alerts", "Need Python FastAPI dashboard, signed webhook handling and low stock notifications for an illustrative store.", (now-timedelta(days=4)).isoformat(), "ILLUSTRATIVE DATA ONLY"),
        Candidate("synthetic_demo", "D-104", "https://example.com/public-demo/help", "Open source automation help wanted", "Volunteer only unpaid work. Looking for developer to improve a workflow automation script.", (now-timedelta(days=6)).isoformat(), "ILLUSTRATIVE DATA ONLY"),
        Candidate("synthetic_demo", "D-105", "https://example.com/public-demo/voice", "Voice agent appointment booking contractor", "Need AI voice agent with signed Twilio webhooks, appointment booking and manual transfer. Paid project, budget $2500.", (now-timedelta(days=3)).isoformat(), "ILLUSTRATIVE DATA ONLY"),
    ]


def main():
    with tempfile.TemporaryDirectory() as root:
        store = Store(str(Path(root) / "demo.sqlite"))
        first = store.ingest(records())
        assert first["new"] == 5
        again = store.ingest(records())
        assert again["new"] == 0
        print("OFFLINE DEMO: synthetic data only; not real clients or earnings")
        print(json.dumps({"ingest":first,"summary":store.summary(),"duplicates":again["duplicates"]},indent=2))


if __name__ == "__main__":
    main()
