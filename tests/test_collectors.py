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
    extract_salem_hawker_licenses,
    extract_salem_permits,
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


def test_salem_permit_normalization_filters_residential():
    text = """B-25-101 9/15/2025 401 MAIN ST CHANGE OF OCCUPANT--COMMERCIAL
    RESTAURANT TENANT FIT UP $ 100,000
    B-25-102 9/16/2025 5 HOME RD ALTERATION--RESIDENTIAL KITCHEN REMODEL
    B-25-103 9/17/2025 10 PARK AVE CERTIFICATE OF OCCUPANCY 1 BEDROOM ADU"""
    records = extract_salem_permits(text)
    assert len(records) == 1
    assert records[0]["permit_number"] == "B-25-101"
    assert records[0]["address"] == "401 MAIN ST"


def test_license_normalization_discards_personal_contact_data():
    records = extract_salem_hawker_licenses(
        "HP-26-34 7/6/2026 Sunrun Solar Garrett Loftstrom 978.360.0998 Ford Truck "
        "HP-26-28 6/3/2026 Power Home Remodeling Jacob Giacalone 603.918.9344"
    )
    assert records[0]["business_name"] == "Sunrun Solar"
    assert "978" not in records[0]["text"]


@respx.mock
def test_partial_source_failure_is_visible_as_degraded(db, tmp_path, monkeypatch):
    import asyncio

    source = Source(
        name="Degraded agenda",
        source_type="planning_board",
        jurisdiction="Test, NH",
        base_url="https://city.gov/AgendaCenter",
        collector_name="civic_engage_agenda",
    )
    db.add(source)
    db.commit()
    respx.get(source.base_url).mock(
        return_value=httpx.Response(
            200,
            text=(
                '<a href="/AgendaCenter/ViewFile/Item/1">Agenda PDF</a>'
                '<a href="/AgendaCenter/ViewFile/Item/2">Agenda PDF</a>'
            ),
        )
    )
    respx.get("https://city.gov/AgendaCenter/ViewFile/Item/1").mock(
        return_value=httpx.Response(200, content=b"one", headers={"content-type": "text/html"})
    )
    respx.get("https://city.gov/AgendaCenter/ViewFile/Item/2").mock(
        return_value=httpx.Response(500)
    )
    from opportunity_intel.config import get_settings

    async def no_sleep(_delay):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    monkeypatch.setattr(get_settings(), "artifact_root", tmp_path)
    run = asyncio.run(collect_source(db, source))
    assert run.status == "degraded"
    assert run.documents_new == 1
    assert source.failure_count == 1
