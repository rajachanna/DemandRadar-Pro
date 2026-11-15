"""FastAPI operator console. No automated third-party messages or outreach."""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
import csv
import io
import json
import secrets
import httpx
from fastapi import FastAPI, Header, HTTPException, Depends, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from .config import Settings
from .drafts import draft_ai, draft_local, DraftModelError
from .scoring import clean_public_url, public_text
from .sources import Candidate, fetch_github, fetch_hackernews, SourceError, GITHUB_SEARCHES, HN_SEARCHES
from .storage import Store

ROOT = Path(__file__).resolve().parent / "static"
STATUS = {"new", "shortlisted", "contacted", "replied", "won", "lost", "archived"}


class ImportRequest(BaseModel):
    title: str = Field(min_length=5, max_length=250)
    description: str = Field(min_length=10, max_length=7000)
    url: str = Field(min_length=12, max_length=1800)
    published_at: str = ""
    source_name: str = Field(default="manual", min_length=2, max_length=70)


class ScanRequest(BaseModel):
    provider: str = Field(pattern="^(github|hackernews)$")
    search: str = Field(min_length=1, max_length=40)


class StatusRequest(BaseModel):
    status: str
    note: str = Field(default="", max_length=1500)


class DraftRequest(BaseModel):
    mode: str = Field(default="template", pattern="^(template|ai)$")


class TelegramRequest(BaseModel):
    record_id: int = Field(gt=0)


def create_app(config: Settings | None = None) -> FastAPI:
    settings = config or Settings.from_env()
    settings.ensure_dirs()
    store = Store(settings.db_path)

    @asynccontextmanager
    async def lifecycle(app: FastAPI) -> AsyncIterator[None]:
        yield

    app = FastAPI(title="DemandRadar Pro", version="0.1.0", lifespan=lifecycle,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store = store
    app.state.settings = settings

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return response

    def auth(x_operator_key: str | None = Header(default=None)) -> None:
        if not settings.operator_enabled:
            raise HTTPException(503, "Set DR_OPERATOR_KEY to a random 24+ character value")
        if not x_operator_key or not secrets.compare_digest(x_operator_key, settings.operator_key):
            raise HTTPException(401, "Operator key required")

    operator = Depends(auth)

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(ROOT / "index.html", media_type="text/html")

    @app.get("/assets/{name}", include_in_schema=False)
    async def assets(name: str):
        if name not in {"app.js", "styles.css"}:
            raise HTTPException(404)
        mime = "text/javascript" if name.endswith(".js") else "text/css"
        return FileResponse(ROOT / name, media_type=mime)

    @app.get("/health")
    async def health():
        return {"status": "ok", "product": "DemandRadar Pro", "demo": settings.demo_mode,
                "outreach_automated": False}

    @app.get("/api/session", dependencies=[operator])
    async def session():
        return {"authenticated": True, "demo_mode": settings.demo_mode,
                "ai_available": bool(settings.openai_api_key),
                "telegram_available": bool(settings.telegram_token and settings.telegram_chat_id),
                "providers": {"github": list(GITHUB_SEARCHES), "hackernews": list(HN_SEARCHES)}}

    @app.get("/api/summary", dependencies=[operator])
    async def summary():
        return store.summary()

    @app.get("/api/opportunities", dependencies=[operator])
    async def opportunities(status: str = "all", min_score: int = 0, limit: int = 100, q: str = ""):
        if status not in STATUS | {"all"}:
            raise HTTPException(422, "Unknown review state")
        return {"items": store.list(status, min(100,max(0,min_score)), limit, q)}

    @app.get("/api/opportunities/{record_id}", dependencies=[operator])
    async def get_record(record_id: int):
        record = store.get(record_id)
        if not record:
            raise HTTPException(404, "Opportunity not found")
        return record

    @app.post("/api/opportunities/import", dependencies=[operator])
    async def import_record(payload: ImportRequest):
        try:
            url = clean_public_url(payload.url)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        source = public_text(payload.source_name,70)
        if not source:
            raise HTTPException(422, "Invalid source label")
        candidate = Candidate("manual", url, url, public_text(payload.title,250),
                              public_text(payload.description,7000), payload.published_at,
                              "Operator-submitted link; not automatically vetted")
        return store.ingest([candidate])

    @app.post("/api/scan", dependencies=[operator])
    async def scan(payload: ScanRequest):
        searches = GITHUB_SEARCHES if payload.provider == "github" else HN_SEARCHES
        if payload.search not in searches:
            raise HTTPException(422, "Select a curated public-source query")
        async with httpx.AsyncClient(timeout=14.0, follow_redirects=False) as client:
            try:
                if payload.provider == "github":
                    candidates = await fetch_github(client, settings.github_token, payload.search,
                                                    settings.max_scan_items)
                else:
                    candidates = await fetch_hackernews(client, payload.search,
                                                       settings.max_scan_items)
            except SourceError as exc:
                store.log_scan(payload.provider, payload.search, 0, 0, "failed", str(exc))
                raise HTTPException(502, str(exc)) from exc
        result = store.ingest(candidates)
        store.log_scan(payload.provider, payload.search, result["fetched"], result["new"], "success")
        return {**result, "provider": payload.provider, "query": payload.search,
                "source_policy": "Public posts; relevance, hiring and compensation unverified"}

    @app.get("/api/scans", dependencies=[operator])
    async def scans():
        return {"items": store.scans()}

    @app.patch("/api/opportunities/{record_id}/status", dependencies=[operator])
    async def update_record(record_id: int, payload: StatusRequest):
        if payload.status not in STATUS:
            raise HTTPException(422, "Invalid status")
        record = store.update_status(record_id, payload.status, public_text(payload.note,1500))
        if not record:
            raise HTTPException(404, "Opportunity not found")
        return record

    @app.post("/api/opportunities/{record_id}/draft", dependencies=[operator])
    async def draft(record_id: int, payload: DraftRequest):
        record = store.get(record_id)
        if not record:
            raise HTTPException(404, "Opportunity not found")
        if payload.mode == "template":
            return draft_local(record)
        if not settings.openai_api_key:
            raise HTTPException(409, "Optional AI key not configured; template draft is available")
        async with httpx.AsyncClient(timeout=24.0) as client:
            try:
                return await draft_ai(client, record, settings.openai_api_key, settings.openai_model)
            except DraftModelError as exc:
                raise HTTPException(502, str(exc)) from exc

    @app.get("/api/exports/opportunities.csv", dependencies=[operator])
    async def csv_export():
        output = io.StringIO()
        writer = csv.writer(output)
        cols = ("id", "title", "source", "url", "score", "category", "status", "budget_evidence", "published_at", "note")
        writer.writerow(cols)
        for record in store.list(limit=250):
            # Spreadsheet formula injection prevention when opened in Excel/Sheets.
            def safe(cell):
                value = str(cell if cell is not None else "")
                return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value
            writer.writerow([safe(record.get(key)) for key in cols])
        return Response(output.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=demandradar-opportunities.csv"})

    @app.post("/api/alerts/telegram", dependencies=[operator])
    async def telegram(payload: TelegramRequest):
        if not settings.telegram_token or not settings.telegram_chat_id:
            raise HTTPException(409, "Owner Telegram alert channel is not configured")
        item = store.get(payload.record_id)
        if not item:
            raise HTTPException(404, "Opportunity not found")
        text = (f"DemandRadar review alert (unverified public lead)\n"
                f"{item['title'][:180]}\n"
                f"Score: {item['score']}/100 · {item['category']}\n"
                f"{item['url']}\n"
                "Please verify compensation, posting rules and legitimacy before contacting anyone.")
        async with httpx.AsyncClient(timeout=12) as client:
            try:
                response = await client.post(
                    f"https://api.telegram.org/bot{settings.telegram_token}/sendMessage",
                    data={"chat_id": settings.telegram_chat_id, "text": text,
                          "disable_web_page_preview": "true"},
                )
                response.raise_for_status()
                if not response.json().get("ok"):
                    raise ValueError("Telegram rejected message")
            except (httpx.HTTPError, ValueError) as exc:
                raise HTTPException(502, "Owner alert failed; check Telegram credentials") from exc
        return {"sent": True, "destination": "configured owner alert channel", "client_contacted": False}

    return app


app = create_app()
