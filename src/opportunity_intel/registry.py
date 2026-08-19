from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Source

SOURCES = [
    {
        "name": "Nashua Planning Board Archive",
        "source_type": "planning_board",
        "jurisdiction": "Nashua, NH",
        "base_url": "https://www.nashuanh.gov/AgendaCenter/Planning-Board-23",
        "collector_name": "civic_engage_agenda",
    },
    {
        "name": "Manchester Planning Board Agendas",
        "source_type": "planning_board",
        "jurisdiction": "Manchester, NH",
        "base_url": "https://www.manchesternh.gov/Departments/Planning-and-Comm-Dev/Planning-Board/Agendas",
        "collector_name": "manchester_planning",
    },
    {
        "name": "Salem Planning Board Agenda Center",
        "source_type": "planning_board",
        "jurisdiction": "Salem, NH",
        "base_url": "https://www.salemnh.gov/AgendaCenter",
        "collector_name": "civic_engage_agenda",
    },
]


def seed_sources(db: Session) -> int:
    added = 0
    for values in SOURCES:
        if not db.scalar(select(Source).where(Source.name == values["name"])):
            db.add(Source(**values, authority_level=5, is_official=True, schedule="weekly"))
            added += 1
    db.commit()
    return added
