import httpx
import respx
from sqlalchemy import func, select

from opportunity_intel.collectors import CivicEngageAgendaCollector, collect_source
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
