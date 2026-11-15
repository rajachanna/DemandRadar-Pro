import asyncio
import pytest
import httpx
from demandradar.sources import fetch_github, fetch_hackernews, SourceError, GITHUB_SEARCHES, HN_SEARCHES


def async_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_github_parsing_and_ignores_pr():
    def handler(r):
        assert r.url.host=="api.github.com"
        assert r.url.params.get("q")==GITHUB_SEARCHES["python_contracts"]
        return httpx.Response(200,json={"items":[
            {"id":42,"html_url":"https://github.com/example/project/issues/2?utm_source=bot", "title":"Python bounty", "body":"budget $900 contact x@private.example", "created_at":"2026-11-14T00:00:00Z", "repository_url":"https://api.github.com/repos/example/project"},
            {"id":43,"pull_request":{},"html_url":"https://github.com/example/project/pull/3"}
        ]})
    async def run():
        async with async_client(handler) as c:return await fetch_github(c,"", "python_contracts")
    result=asyncio.run(run())
    assert len(result)==1
    assert result[0].url=="https://github.com/example/project/issues/2"
    assert "x@private.example" not in result[0].description


def test_github_token_not_leaked_in_return():
    def handler(r):
        assert r.headers.get("authorization")=="Bearer test-token"
        return httpx.Response(200,json={"items":[]})
    async def run():
        async with async_client(handler) as c:return await fetch_github(c,"test-token","automation_help")
    assert asyncio.run(run())==[]


def test_github_rate_limit_error():
    def handler(r):return httpx.Response(403,json={"message":"rate limit"})
    async def run():
        async with async_client(handler) as c:return await fetch_github(c,"","ai_workflows")
    with pytest.raises(SourceError):asyncio.run(run())


def test_github_malformed_response():
    def handler(r):return httpx.Response(200,json={"message":"not items"})
    async def run():
        async with async_client(handler) as c:return await fetch_github(c,"","web_integrations")
    with pytest.raises(SourceError):asyncio.run(run())


def test_github_unknown_query():
    async def run():
        async with async_client(lambda r:httpx.Response(200,json={"items":[]})) as c:
            return await fetch_github(c,"","malicious arbitrary query")
    with pytest.raises(ValueError):asyncio.run(run())


def test_hn_discussion_parsing():
    def handler(r):
        assert r.url.host=="hn.algolia.com"
        assert r.url.params.get("tags")=="story"
        return httpx.Response(200,json={"hits":[{"objectID":"123","title":"Need contractor for automation","story_text":"<p>budget $1200, write to email@x.com</p>","created_at":"2026-11-14T00:00:00Z"}]})
    async def run():
        async with async_client(handler) as c:return await fetch_hackernews(c,"contract")
    result=asyncio.run(run())
    assert len(result)==1
    assert result[0].url=="https://news.ycombinator.com/item?id=123"
    assert "email@x.com" not in result[0].description


def test_hn_filters_non_numeric_ids():
    def handler(r):return httpx.Response(200,json={"hits":[{"objectID":"wrong","title":"x"},{"objectID":"3","title":""}]})
    async def run():
        async with async_client(handler) as c:return await fetch_hackernews(c,"freelance")
    assert asyncio.run(run())==[]


def test_hn_malformed_response():
    async def run():
        async with async_client(lambda r:httpx.Response(200,json={})) as c:return await fetch_hackernews(c,"automation")
    with pytest.raises(SourceError):asyncio.run(run())


def test_hn_unknown_query():
    async def run():
        async with async_client(lambda r:httpx.Response(200,json={"hits":[]})) as c:return await fetch_hackernews(c,"non-approved")
    with pytest.raises(ValueError):asyncio.run(run())


def test_source_catalogs_are_curated():
    assert "python_contracts" in GITHUB_SEARCHES
    assert "contract" in HN_SEARCHES
    assert len(GITHUB_SEARCHES)<=6 and len(HN_SEARCHES)<=6
