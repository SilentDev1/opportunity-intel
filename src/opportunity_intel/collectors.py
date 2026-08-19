import abc
import asyncio
import hashlib
import io
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
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
                response = await client.get(item.url)
                if response.status_code != 429 and response.status_code < 500:
                    return response
                if attempt == 2:
                    return response
                retry_after = response.headers.get("retry-after")
                delay = min(float(retry_after), 10.0) if retry_after else 2**attempt
                await asyncio.sleep(delay)
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
        if self.source.jurisdiction in {"Salem, NH", "Bedford, NH"}:
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


class DoverBusinessNewsCollector(SourceCollector):
    async def discover(self, client: httpx.AsyncClient) -> list[DiscoveredDocument]:
        response = await client.get(self.source.base_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        found: dict[str, DiscoveredDocument] = {}
        for link in soup.select("a[href]"):
            title = " ".join(link.get_text(" ", strip=True).split())
            if title.casefold().startswith("down to business,"):
                url = urljoin(self.source.base_url, str(link.get("href")))
                found[url] = DiscoveredDocument(url, title)
        return list(found.values())


class PortsmouthPlanningCollector(SourceCollector):
    async def discover(self, client: httpx.AsyncClient) -> list[DiscoveredDocument]:
        response = await client.get(self.source.base_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        wanted = {"agenda", "revised agenda", "staff memo", "action sheet", "legal notice"}
        found: dict[str, DiscoveredDocument] = {}
        for link in soup.select("a[href]"):
            title = " ".join(link.get_text(" ", strip=True).split())
            href = str(link.get("href"))
            if title.casefold() in wanted and ".pdf" in href.casefold():
                url = urljoin(self.source.base_url, href)
                found[url] = DiscoveredDocument(url, title)
        return list(found.values())


def extract_salem_permits(text: str) -> list[dict[str, str]]:
    """Extract commercial permit records without retaining private contact details."""
    records: list[dict[str, str]] = []
    chunks = re.split(r"(?=\bB-\d{2}-\d+\b)", " ".join(text.split()))
    for chunk in chunks:
        permit = re.match(r"(B-\d{2}-\d+)\s+(\d{1,2}/\d{1,2}/\d{4})\s+(.+)", chunk)
        if not permit:
            continue
        body = permit.group(3).strip()
        commercial = re.search(
            r"COMMERCIAL|CHANGE OF OCCUPANT|TENANT FIT|RESTAURANT|RETAIL|OFFICE|"
            r"INDUSTRIAL|WAREHOUSE|SIGN|CERTIFICATE OF OCCUPANCY",
            body,
            re.I,
        )
        residential = re.search(
            r"ALTERATION--RESIDENTIAL|NEW CONSTRUCTION--1 FAMILY|SINGLE.FAMILY|"
            r"DECK|POOL|KITCHEN REMODEL|\bADU\b|REPLACEMENT (?:MANUFACTURED |MOBILE )?HOME|"
            r"\b\d+\s*BEDROOMS?\b",
            body,
            re.I,
        )
        if not commercial or (residential and not re.search(r"COMMERCIAL", body, re.I)):
            continue
        address = re.match(
            r"(\d+[A-Z-]*\s+[A-Z0-9 .'#&-]+?\b(?:ST|RD|DR|AVE|BLVD|LN|WAY|HWY))\b",
            body,
        )
        records.append(
            {
                "external_id": permit.group(1),
                "record_type": "building_permit",
                "text": chunk.strip(),
                "permit_number": permit.group(1),
                "issued_date": permit.group(2),
                "address": address.group(1).strip() if address else "",
            }
        )
    return records


class SalemIssuedPermitCollector(CivicEngageAgendaCollector):
    async def discover(self, client: httpx.AsyncClient) -> list[DiscoveredDocument]:
        response = await client.get(self.source.base_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        found = []
        for link in soup.select("a[href*='DocumentCenter/View']"):
            title = " ".join(link.get_text(" ", strip=True).split())
            if re.search(r"2025 Through|2025 Though", title):
                found.append(
                    DiscoveredDocument(urljoin(self.source.base_url, str(link.get("href"))), title)
                )
        return found

    def parse(self, content: bytes, content_type: str, url: str) -> list[dict[str, str]]:
        if "pdf" not in content_type:
            return []
        text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)
        return extract_salem_permits(text)


def extract_salem_hawker_licenses(text: str) -> list[dict[str, str]]:
    records = []
    pattern = re.compile(
        r"(HP-\d{2}-\d+)\s+(\d{1,2}/\d{1,2}/\d{4})(.+?)"
        r"(?=\s+[A-Z][a-z]+\s+[A-Z][a-z]+\s+\d{3}[.-]\d{3}|\s+HP-|$)"
    )
    for match in pattern.finditer(" ".join(text.split())):
        records.append(
            {
                "external_id": match.group(1),
                "record_type": "hawker_peddler_license",
                "text": f"{match.group(1)} {match.group(2)} {match.group(3).strip()}",
                "submitted_date": match.group(2),
                "business_name": match.group(3).strip(),
            }
        )
    return records


class SalemHawkerLicenseCollector(CivicEngageAgendaCollector):
    async def discover(self, client: httpx.AsyncClient) -> list[DiscoveredDocument]:
        response = await client.get(self.source.base_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        return [
            DiscoveredDocument(
                urljoin(self.source.base_url, str(link.get("href"))),
                "Hawker Peddlers License List 2026",
            )
            for link in soup.select("a[href*='DocumentCenter/View']")
            if "Hawker Peddlers License List 2026" in link.get_text(" ", strip=True)
        ]

    def parse(self, content: bytes, content_type: str, url: str) -> list[dict[str, str]]:
        if "pdf" not in content_type:
            return []
        text = " ".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)
        return extract_salem_hawker_licenses(text)


COLLECTORS = {
    "civic_engage_agenda": CivicEngageAgendaCollector,
    "manchester_planning": ManchesterPlanningCollector,
    "dover_business_news": DoverBusinessNewsCollector,
    "portsmouth_planning": PortsmouthPlanningCollector,
    "salem_issued_permits": SalemIssuedPermitCollector,
    "salem_hawker_licenses": SalemHawkerLicenseCollector,
}


async def collect_source(db: Session, source: Source, limit: int = 20) -> CollectionRun:
    settings = get_settings()
    run = CollectionRun(source_id=source.id)
    db.add(run)
    source.last_attempt_at = datetime.utcnow()
    db.commit()
    collector_type: Any = COLLECTORS[source.collector_name]
    collector: SourceCollector = collector_type(source)
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
                            raw_payload={
                                "source_url": item.url,
                                "title": item.title,
                                **{
                                    key: value
                                    for key, value in record.items()
                                    if key not in {"external_id", "record_type", "text"}
                                },
                            },
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
        run.status = "degraded" if run.documents_new else "failed"
        run.error = str(exc)[:2000]
        source.last_error = run.error
        source.failure_count += 1
    run.finished_at = datetime.utcnow()
    db.commit()
    return run
