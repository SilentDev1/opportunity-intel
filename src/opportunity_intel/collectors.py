import abc
import asyncio
import hashlib
import io
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import CollectionRun, RawRecord, RawSourceDocument, Source
from .storage import LocalArtifactStorage

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiscoveredDocument:
    url: str
    title: str


class SourceCollector(abc.ABC):
    parser_version = "1"

    def __init__(self, source: Source):
        self.source = source

    @abc.abstractmethod
    async def discover(self, client: httpx.AsyncClient) -> list[DiscoveredDocument]: ...
    async def fetch(self, client: httpx.AsyncClient, item: DiscoveredDocument) -> httpx.Response:
        for attempt in range(3):
            try:
                return await client.get(item.url)
            except (httpx.TimeoutException, httpx.TransportError):
                if attempt == 2:
                    raise
                await asyncio.sleep(2**attempt)
        raise RuntimeError("unreachable")

    def parse(self, content: bytes, content_type: str, url: str) -> list[dict[str, str]]:
        text = ""
        if "pdf" in content_type:
            try:
                text = "\n".join(
                    page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages
                )
            except Exception:
                log.warning("pdf_text_extraction_failed", extra={"url": url})
        elif "html" in content_type:
            text = BeautifulSoup(content, "html.parser").get_text("\n", strip=True)
        return [
            {
                "external_id": hashlib.sha256(url.encode()).hexdigest(),
                "record_type": "document",
                "text": text,
            }
        ]


class CivicEngageAgendaCollector(SourceCollector):
    async def discover(self, client: httpx.AsyncClient) -> list[DiscoveredDocument]:
        response = await client.get(self.source.base_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        links: list[Tag] = list(soup.select("a[href]"))
        if self.source.jurisdiction == "Salem, NH":
            heading = soup.find(
                lambda tag: (
                    tag.name in {"h2", "h3"} and tag.get_text(" ", strip=True) == "Planning Board"
                )
            )
            scoped = []
            if heading:
                for element in heading.find_all_next():
                    if element.name == "h2":
                        break
                    if element.name == "a" and element.get("href"):
                        scoped.append(element)
            links = scoped
        found = {}
        for link in links:
            href = str(link.get("href"))
            text = " ".join(link.get_text(" ", strip=True).split())
            if "ViewFile" in href and (
                "agenda" in text.casefold()
                or "packet" in text.casefold()
                or href.casefold().endswith(".pdf")
            ):
                url = urljoin(self.source.base_url, href)
                found[url] = DiscoveredDocument(url, text or Path(url).name)
        return list(found.values())


class ManchesterPlanningCollector(SourceCollector):
    async def discover(self, client: httpx.AsyncClient) -> list[DiscoveredDocument]:
        response = await client.get(self.source.base_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        result = []
        for link in soup.select("a[href]"):
            href = str(link.get("href"))
            title = " ".join(link.get_text(" ", strip=True).split())
            if ".pdf" in href.casefold() and (
                "agenda" in title.casefold() or "pb_" in href.casefold()
            ):
                result.append(DiscoveredDocument(urljoin(self.source.base_url, href), title))
        return result


COLLECTORS = {
    "civic_engage_agenda": CivicEngageAgendaCollector,
    "manchester_planning": ManchesterPlanningCollector,
}


async def collect_source(db: Session, source: Source, limit: int = 20) -> CollectionRun:
    settings = get_settings()
    run = CollectionRun(source_id=source.id)
    db.add(run)
    source.last_attempt_at = datetime.utcnow()
    db.commit()
    collector = COLLECTORS[source.collector_name](source)
    storage = LocalArtifactStorage(settings.artifact_root)
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": settings.http_user_agent}, timeout=30, follow_redirects=True
        ) as client:
            items = (await collector.discover(client))[:limit]
            run.documents_discovered = len(items)
            for item in items:
                await asyncio.sleep(0.25)
                response = await collector.fetch(client, item)
                response.raise_for_status()
                content = response.content
                digest = hashlib.sha256(content).hexdigest()
                if db.scalar(
                    select(RawSourceDocument).where(
                        RawSourceDocument.source_id == source.id,
                        RawSourceDocument.content_hash == digest,
                    )
                ):
                    continue
                content_type = response.headers.get(
                    "content-type", "application/octet-stream"
                ).split(";")[0]
                suffix = (
                    ".pdf"
                    if "pdf" in content_type
                    else ".html"
                    if "html" in content_type
                    else ".bin"
                )
                path, _ = storage.put(content, suffix)
                doc = RawSourceDocument(
                    source_id=source.id,
                    source_url=item.url,
                    content_type=content_type,
                    http_status=response.status_code,
                    content_hash=digest,
                    storage_path=path,
                    title=item.title,
                    parser_version=collector.parser_version,
                )
                db.add(doc)
                db.flush()
                records = collector.parse(content, content_type, item.url)
                for record in records:
                    db.add(
                        RawRecord(
                            raw_source_document_id=doc.id,
                            record_type=record["record_type"],
                            external_id=record["external_id"],
                            raw_payload={"source_url": item.url, "title": item.title},
                            extracted_text=record.get("text"),
                            parser_version=collector.parser_version,
                        )
                    )
                doc.processing_status = "parsed"
                run.documents_new += 1
                run.records_parsed += len(records)
        run.status = "success"
        source.last_success_at = datetime.utcnow()
        source.last_error = None
        source.failure_count = 0
    except Exception as exc:
        log.exception("collector_failed", extra={"run_id": run.id, "source": source.name})
        run.status = "failed"
        run.error = str(exc)[:2000]
        source.last_error = run.error
        source.failure_count += 1
    run.finished_at = datetime.utcnow()
    db.commit()
    return run
