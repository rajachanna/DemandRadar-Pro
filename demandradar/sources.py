"""Two real, public read-only feeds; no unauthorized scraping or account login."""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import httpx
from .scoring import clean_public_url, public_text

GITHUB_SEARCHES = {
    "python_contracts": 'is:issue is:open "bounty" "python"',
    "automation_help": 'is:issue is:open "help wanted" "automation"',
    "ai_workflows": 'is:issue is:open "bounty" "ai agent"',
    "web_integrations": 'is:issue is:open "help wanted" "webhook"',
}
HN_SEARCHES = {
    "freelance": "freelance developer",
    "automation": "automation contractor",
    "contract": "contract developer",
}


@dataclass(frozen=True)
class Candidate:
    source: str
    source_id: str
    url: str
    title: str
    description: str
    published_at: str
    project_context: str = ""


class SourceError(RuntimeError):
    """Public-source API failure; not evidence of zero real-world opportunities."""


async def fetch_github(client: httpx.AsyncClient, token: str, search: str,
                       limit: int = 20) -> list[Candidate]:
    if search not in GITHUB_SEARCHES:
        raise ValueError("Unknown curated GitHub query")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "DemandRadar-Pro/0.1",
               "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        r = await client.get("https://api.github.com/search/issues", headers=headers, params={
            "q": GITHUB_SEARCHES[search], "sort": "created", "order": "desc",
            "per_page": max(1, min(30, limit)),
        })
        r.raise_for_status()
        payload = r.json()
        if not isinstance(payload.get("items"), list):
            raise SourceError("GitHub response missing issue items")
        records = []
        for item in payload["items"][:limit]:
            if "pull_request" in item:
                continue
            item_url = clean_public_url(item.get("html_url", ""))
            if item_url.startswith("https://github.com/"):
                records.append(Candidate(
                    source="github_issues", source_id=str(item["id"]), url=item_url,
                    title=public_text(item.get("title", ""), 250),
                    description=public_text(item.get("body", ""), 6000),
                    published_at=str(item.get("created_at", "")),
                    project_context=public_text(item.get("repository_url", ""), 300),
                ))
        return records
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        if isinstance(exc, SourceError):
            raise
        raise SourceError(f"GitHub public search failed: {type(exc).__name__}. Check API limits or network.") from exc


async def fetch_hackernews(client: httpx.AsyncClient, search: str,
                           limit: int = 20) -> list[Candidate]:
    if search not in HN_SEARCHES:
        raise ValueError("Unknown curated Hacker News query")
    try:
        r = await client.get("https://hn.algolia.com/api/v1/search_by_date", params={
            "query": HN_SEARCHES[search], "tags": "story", "hitsPerPage": max(1, min(30, limit)),
        }, headers={"User-Agent": "DemandRadar-Pro/0.1"})
        r.raise_for_status()
        data = r.json()
        if not isinstance(data.get("hits"), list):
            raise SourceError("Hacker News public index missing hits")
        records = []
        for item in data["hits"][:limit]:
            oid = str(item.get("objectID", ""))
            if not oid.isdigit():
                continue
            title = public_text(item.get("title") or "", 250)
            if not title:
                continue
            records.append(Candidate(
                source="hacker_news", source_id=oid,
                url=f"https://news.ycombinator.com/item?id={oid}",
                title=title, description=public_text(item.get("story_text") or "", 6000),
                published_at=str(item.get("created_at", "")),
                project_context="Public discussion; hiring/payment requires manual verification",
            ))
        return records
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        if isinstance(exc, SourceError):
            raise
        raise SourceError(f"Hacker News index request failed: {type(exc).__name__}. Retry later.") from exc
