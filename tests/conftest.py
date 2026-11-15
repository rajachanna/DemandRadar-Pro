import pytest
from fastapi.testclient import TestClient
from demandradar.config import Settings
from demandradar.api import create_app
from demandradar.sources import Candidate

KEY = "test_operator_key_demandradar_min_32_characters"


@pytest.fixture
def cfg(tmp_path):
    return Settings(db_path=str(tmp_path / "db.sqlite"), operator_key=KEY, demo_mode=True)


@pytest.fixture
def client(cfg):
    with TestClient(create_app(cfg)) as c:
        yield c


@pytest.fixture
def hdr():
    return {"X-Operator-Key": KEY}


@pytest.fixture
def sample():
    return Candidate("manual", "p1", "https://example.com/projects/1", "Need a Python FastAPI webhook developer", "Hiring a developer to integrate a REST API and dashboard, budget $1200", "2026-11-14T12:00:00Z")
