import httpx
import respx
from sqlalchemy import func, select

from opportunity_intel.collectors import (
    CivicEngageAgendaCollector,
    DiscoveredDocument,
    DoverBusinessNewsCollector,
    ManchesterPlanningCollector,
    PortsmouthPlanningCollector,
    collect_source,
)
from opportunity_intel.models import RawSourceDocument, Source


@respx.mock
def test_discovery_and_idempotent_ingestion(db, tmp_path, monkeypatch):
    import asyncio

    source = Source(
        name="Test agenda",
        source_type="planning_board",
        jurisdiction="Test, NH",
        base_url="https://city.gov/AgendaCenter",
        collector_name="civic_engage_agenda",
    )
    db.add(source)
    db.commit()
    respx.get("https://city.gov/AgendaCenter").mock(
        return_value=httpx.Response(
            200, text='<a href="/AgendaCenter/ViewFile/Item/1">Agenda PDF</a>'
        )
    )
    respx.get("https://city.gov/AgendaCenter/ViewFile/Item/1").mock(
        return_value=httpx.Response(
            200, content=b"pdf fixture", headers={"content-type": "application/pdf"}
        )
    )
    from opportunity_intel.config import get_settings

    monkeypatch.setattr(get_settings(), "artifact_root", tmp_path)
    first = asyncio.run(collect_source(db, source))
    second = asyncio.run(collect_source(db, source))
    assert first.documents_new == 1 and second.documents_new == 0
    assert db.scalar(select(func.count()).select_from(RawSourceDocument)) == 1


@respx.mock
def test_salem_discovery_is_scoped_to_planning_board():
    import asyncio

    source = Source(
        name="Salem",
        source_type="planning_board",
        jurisdiction="Salem, NH",
        base_url="https://salem.gov/AgendaCenter",
        collector_name="civic_engage_agenda",
    )
    html = (
        '<h2>Other Board</h2><a href="/ViewFile/1">Agenda</a>'
        '<h2>Planning Board</h2><a href="/ViewFile/2">Agenda</a>'
        '<h2>Town Council</h2><a href="/ViewFile/3">Agenda</a>'
    )
    respx.get(source.base_url).mock(return_value=httpx.Response(200, text=html))

    async def discover():
        async with httpx.AsyncClient() as client:
            return await CivicEngageAgendaCollector(source).discover(client)

    items = asyncio.run(discover())
    assert [item.url for item in items] == ["https://salem.gov/ViewFile/2"]


@respx.mock
def test_dover_newsletter_discovery_ignores_signup_link():
    import asyncio

    source = Source(
        name="Dover",
        source_type="municipal_news",
        jurisdiction="Dover, NH",
        base_url="https://dover.gov/news/",
        collector_name="dover_business_news",
    )
    html = (
        '<a href="/signup">Down to Business</a>'
        '<a href="https://conta.cc/abc">Down to Business, August 18, 2026</a>'
    )
    respx.get(source.base_url).mock(return_value=httpx.Response(200, text=html))

    async def discover():
        async with httpx.AsyncClient() as client:
            return await DoverBusinessNewsCollector(source).discover(client)

    items = asyncio.run(discover())
    assert [(item.url, item.title) for item in items] == [
        ("https://conta.cc/abc", "Down to Business, August 18, 2026")
    ]


@respx.mock
def test_portsmouth_discovery_only_keeps_primary_meeting_documents():
    import asyncio

    source = Source(
        name="Portsmouth",
        source_type="planning_board",
        jurisdiction="Portsmouth, NH",
        base_url="https://portsmouth.gov/archive",
        collector_name="portsmouth_planning",
    )
    html = (
        '<a href="/agenda.pdf">Agenda</a>'
        '<a href="/packet.pdf">Meeting Packet</a>'
        '<a href="/site.pdf">123 Main St</a>'
        '<a href="/memo.pdf">Staff Memo</a>'
    )
    respx.get(source.base_url).mock(return_value=httpx.Response(200, text=html))

    async def discover():
        async with httpx.AsyncClient() as client:
            return await PortsmouthPlanningCollector(source).discover(client)

    items = asyncio.run(discover())
    assert {item.title for item in items} == {"Agenda", "Staff Memo"}


@respx.mock
def test_fetch_retries_rate_limit_response(monkeypatch):
    import asyncio

    source = Source(
        name="Manchester",
        source_type="planning_board",
        jurisdiction="Manchester, NH",
        base_url="https://city.gov/agendas",
        collector_name="manchester_planning",
    )
    route = respx.get("https://city.gov/agenda.pdf").mock(
        side_effect=[httpx.Response(429), httpx.Response(200, content=b"ok")]
    )

    async def no_sleep(_delay):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    async def fetch():
        async with httpx.AsyncClient() as client:
            return await ManchesterPlanningCollector(source).fetch(
                client, DiscoveredDocument("https://city.gov/agenda.pdf", "Agenda")
            )

    assert asyncio.run(fetch()).status_code == 200
    assert route.call_count == 2
