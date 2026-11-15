import asyncio
import httpx
import pytest
from demandradar.drafts import draft_local, draft_ai, DraftModelError

ITEM={"title":"FastAPI developer for our automation dashboard","description":"Connect 2 APIs and add retry handling", "category":"Web Apps & APIs"}


def test_template_never_claims_sent():
    o=draft_local(ITEM)
    assert o["mode"]=="template"
    assert not o["sent"] and o["review_required"]
    assert "ClientMagnet" in o["text"]
    assert "Would you be open" in o["text"]


def test_template_public_example_for_trading():
    o=draft_local({**ITEM,"category":"MT5 / Trading Automation"})
    assert "TradeBridge-Pro" in o["text"]


def test_template_public_example_for_ai():
    o=draft_local({**ITEM,"category":"AI Agents & Automation"})
    assert "SupportPilot-Pro" in o["text"]


def test_ai_no_key_refused():
    async def run():
        async with httpx.AsyncClient() as c:return await draft_ai(c,ITEM,"","gpt-4.1-mini")
    with pytest.raises(DraftModelError):asyncio.run(run())


def test_ai_request_mocked_and_unsent():
    def handler(r):
        assert r.url.host=="api.openai.com"
        assert r.headers["authorization"]=="Bearer demo-test-key"
        data=__import__("json").loads(r.content)
        assert data["store"] is False
        assert "UNTRUSTED" in data["instructions"]
        return httpx.Response(200,json={"output":[{"type":"message","content":[{"type":"output_text","text":"Hello, please review this scoped technical proposal."}]}]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await draft_ai(c,ITEM,"demo-test-key","gpt-4.1-mini")
    o=asyncio.run(run())
    assert o["mode"]=="ai" and o["review_required"] and not o["sent"]


def test_ai_response_failure_safe():
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(429))) as c:
            return await draft_ai(c,ITEM,"fake","gpt-4.1-mini")
    with pytest.raises(DraftModelError):asyncio.run(run())


def test_ai_empty_output_rejected():
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={"output":[]}))) as c:
            return await draft_ai(c,ITEM,"fake","gpt-4.1-mini")
    with pytest.raises(DraftModelError):asyncio.run(run())
