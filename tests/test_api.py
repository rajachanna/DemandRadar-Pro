import pytest
from demandradar.config import Settings
from demandradar.api import create_app
from fastapi.testclient import TestClient
from demandradar.sources import Candidate, SourceError


def seed(client,hdr,title="Need Python FastAPI developer for dashboard",url="https://github.com/acme/test/issues/5",description="We need help building an API, paid project $1500"):
    response=client.post("/api/opportunities/import",headers=hdr,json={"url":url,"title":title,"description":description})
    assert response.status_code==200,response.text
    return response.json()


def test_health_public(client):
    r=client.get("/health")
    assert r.status_code==200 and r.json()["outreach_automated"] is False


@pytest.mark.parametrize("path",["/api/session","/api/summary","/api/opportunities","/api/scans","/api/exports/opportunities.csv"])
def test_private_get_requires_auth(client,path):
    assert client.get(path).status_code==401


def test_private_write_requires_auth(client):
    assert client.post("/api/scan",json={"provider":"github","search":"python_contracts"}).status_code==401


def test_wrong_key(client):
    assert client.get("/api/session",headers={"X-Operator-Key":"wrong"}).status_code==401


def test_missing_config_returns_503(tmp_path):
    with TestClient(create_app(Settings(db_path=str(tmp_path/"no-key.sqlite")))) as c:
        assert c.get("/api/summary").status_code==503


def test_session_capabilities(client,hdr):
    data=client.get("/api/session",headers=hdr).json()
    assert data["authenticated"] and data["demo_mode"]
    assert not data["ai_available"] and not data["telegram_available"]
    assert "python_contracts" in data["providers"]["github"]


def test_import_and_duplicate(client,hdr):
    assert seed(client,hdr)["new"]==1
    assert seed(client,hdr)["new"]==0
    assert client.get("/api/summary",headers=hdr).json()["total"]==1


def test_import_rejects_http(client,hdr):
    r=client.post("/api/opportunities/import",headers=hdr,json={"url":"http://bad.example/","title":"Need automation developer","description":"Build reliable app software"})
    assert r.status_code==422


def test_import_validates_required_fields(client,hdr):
    r=client.post("/api/opportunities/import",headers=hdr,json={"url":"https://example.com/","title":"a","description":"b"})
    assert r.status_code==422


def test_import_removes_email(client,hdr):
    seed(client,hdr,description="Email test@example.com; need Python API integration in a dashboard")
    body=client.get("/api/opportunities",headers=hdr).json()
    assert "test@example.com" not in body["items"][0]["description"]


def test_status_pipeline(client,hdr):
    seed(client,hdr)
    record=client.get("/api/opportunities",headers=hdr).json()["items"][0]
    r=client.patch(f"/api/opportunities/{record['id']}/status",headers=hdr,json={"status":"contacted","note":"Contacted manually on allowed platform"})
    assert r.status_code==200 and r.json()["status"]=="contacted"
    assert client.get("/api/summary",headers=hdr).json()["contacted"]==1


def test_status_rejects_unknown(client,hdr):
    seed(client,hdr)
    r=client.patch("/api/opportunities/1/status",headers=hdr,json={"status":"fake-win","note":""})
    assert r.status_code==422


def test_status_missing_record(client,hdr):
    r=client.patch("/api/opportunities/8973/status",headers=hdr,json={"status":"new"})
    assert r.status_code==404


def test_template_draft(client,hdr):
    seed(client,hdr)
    r=client.post("/api/opportunities/1/draft",headers=hdr,json={"mode":"template"})
    assert r.status_code==200 and r.json()["sent"] is False
    assert "github.com/rajachanna" in r.json()["text"]


def test_optional_ai_requires_key(client,hdr):
    seed(client,hdr)
    r=client.post("/api/opportunities/1/draft",headers=hdr,json={"mode":"ai"})
    assert r.status_code==409


def test_draft_missing_record(client,hdr):
    assert client.post("/api/opportunities/999/draft",headers=hdr,json={"mode":"template"}).status_code==404


def test_listing_filter(client,hdr):
    seed(client,hdr)
    assert len(client.get("/api/opportunities?q=FastAPI",headers=hdr).json()["items"])==1
    assert len(client.get("/api/opportunities?q=unlikely",headers=hdr).json()["items"])==0
    assert client.get("/api/opportunities?status=not-a-status",headers=hdr).status_code==422


def test_csv_formula_guard(client,hdr):
    seed(client,hdr,title="=EXEC command developer job")
    text=client.get("/api/exports/opportunities.csv",headers=hdr).text
    assert "'=EXEC" in text
    assert "Content-Disposition" in client.get("/api/exports/opportunities.csv",headers=hdr).headers


def test_get_record(client,hdr):
    seed(client,hdr)
    assert client.get("/api/opportunities/1",headers=hdr).json()["id"]==1
    assert client.get("/api/opportunities/999",headers=hdr).status_code==404


def test_assets_and_security(client):
    r=client.get("/")
    assert r.status_code==200 and "DemandRadar" in r.text
    assert "Content-Security-Policy" in r.headers
    assert client.get("/assets/styles.css").status_code==200
    assert client.get("/assets/app.js").status_code==200
    assert client.get("/assets/secret.env").status_code==404


def test_invalid_scan_query(client,hdr):
    r=client.post("/api/scan",headers=hdr,json={"provider":"github","search":"unapproved arbitrary site"})
    assert r.status_code==422


def test_invalid_scan_provider(client,hdr):
    assert client.post("/api/scan",headers=hdr,json={"provider":"linkedin","search":"people"}).status_code==422


def test_scan_mocked_records(client,hdr,monkeypatch):
    async def fake(*args,**kwargs):return [Candidate("github_issues","id1","https://github.com/acme/help/issues/2","Need FastAPI developer","Budget $2000, webhook integration","2026-11-14T00:00:00Z")]
    monkeypatch.setattr("demandradar.api.fetch_github",fake)
    r=client.post("/api/scan",headers=hdr,json={"provider":"github","search":"automation_help"})
    assert r.status_code==200 and r.json()["new"]==1
    r2=client.post("/api/scan",headers=hdr,json={"provider":"github","search":"automation_help"})
    assert r2.json()["duplicates"]==1
    assert len(client.get("/api/scans",headers=hdr).json()["items"])==2


def test_scan_failed_is_logged(client,hdr,monkeypatch):
    async def fail(*args,**kwargs):raise SourceError("GitHub read-only API unavailable")
    monkeypatch.setattr("demandradar.api.fetch_github",fail)
    r=client.post("/api/scan",headers=hdr,json={"provider":"github","search":"web_integrations"})
    assert r.status_code==502
    assert client.get("/api/scans",headers=hdr).json()["items"][0]["outcome"]=="failed"


def test_scan_hackernews_adapter(client,hdr,monkeypatch):
    async def fake(*args,**kwargs):return [Candidate("hacker_news","123","https://news.ycombinator.com/item?id=123","Hiring contractor for AI agent","Need RAG and workflow automation","2026-11-14T00:00:00Z")]
    monkeypatch.setattr("demandradar.api.fetch_hackernews",fake)
    r=client.post("/api/scan",headers=hdr,json={"provider":"hackernews","search":"contract"})
    assert r.status_code==200 and r.json()["new"]==1


def test_telegram_off_by_default(client,hdr):
    seed(client,hdr)
    r=client.post("/api/alerts/telegram",headers=hdr,json={"record_id":1})
    assert r.status_code==409


def test_demo_mode_label(client):
    assert client.get("/health").json()["demo"] is True


def test_headers_prevent_caching(client,hdr):
    assert client.get("/api/summary",headers=hdr).headers["cache-control"]=="no-store"
    assert client.get("/api/summary",headers=hdr).headers["x-frame-options"]=="DENY"
