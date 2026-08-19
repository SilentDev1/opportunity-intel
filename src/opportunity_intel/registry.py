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
    {
        "name": "Manchester Zoning Board Agendas",
        "source_type": "zoning_board",
        "jurisdiction": "Manchester, NH",
        "base_url": "https://www.manchesternh.gov/Departments/Planning-and-Comm-Dev/Zoning-Board/Agendas",
        "collector_name": "manchester_planning",
    },
    {
        "name": "Bedford Planning Board Agenda Center",
        "source_type": "planning_board",
        "jurisdiction": "Bedford, NH",
        "base_url": "https://www.bedfordnh.org/129/Agendas-Minutes",
        "collector_name": "civic_engage_agenda",
    },
    {
        "name": "Portsmouth Planning Board Materials",
        "source_type": "planning_board",
        "jurisdiction": "Portsmouth, NH",
        "base_url": "https://www.portsmouthnh.gov/planportsmouth/planning-board/planning-board-archived-meetings-and-material",
        "collector_name": "portsmouth_planning",
    },
    {
        "name": "Dover Down to Business",
        "source_type": "municipal_news",
        "jurisdiction": "Dover, NH",
        "base_url": "https://www.dover.nh.gov/government/city-operations/executive/business-development/down-to-business/",
        "collector_name": "dover_business_news",
    },
    {
        "name": "Salem Issued Building Permits (Historical)",
        "source_type": "building_permit",
        "jurisdiction": "Salem, NH",
        "base_url": "https://www.salemnh.gov/323/Issued-Permits",
        "collector_name": "salem_issued_permits",
    },
    {
        "name": "Salem Hawker and Peddler Licenses",
        "source_type": "business_license",
        "jurisdiction": "Salem, NH",
        "base_url": "https://www.salemnh.gov/323/Issued-Permits",
        "collector_name": "salem_hawker_licenses",
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
