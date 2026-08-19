from opportunity_intel.processing import extract_manchester_projects


def test_extracts_commercial_and_suppresses_residential():
    text = """MANCHESTER PLANNING BOARD
Thursday, July 16, 2026 – 6:00 PM
1. SP2026-011
Property located at 1265 South Willow Street (Tax Map 1, Lot 2), a site plan application
to construct a new fueling station with a convenience store and drive-through restaurant.
Engineer, Inc. for Aranosian Oil Company, Inc. (Reviewed under Current Zoning Ordinance)
2. SP2026-099
Property located at 12 Home Street (Tax Map 2, Lot 3), a site plan for a 9-dwelling unit
building. Engineer, Inc. for Home Owner, LLC. (Reviewed under Current Zoning Ordinance)
III. BUSINESS MEETING:"""
    projects = extract_manchester_projects(text)
    assert len(projects) == 1
    assert projects[0]["project_id"] == "SP2026-011"
    assert projects[0]["applicant"] == "Aranosian Oil Company, Inc"
    assert projects[0]["address"] == "1265 South Willow Street"
