from opportunity_intel.processing import extract_manchester_projects, is_commercial_candidate


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


def test_false_positive_regressions_keep_mixed_use_commercial():
    assert not is_commercial_candidate("Four standalone residential condominiums in office zone")
    assert not is_commercial_candidate("Three single-family dwellings for Regan Electric")
    assert is_commercial_candidate("Mixed-use redevelopment with new commercial space")


def test_manchester_parser_does_not_bleed_across_pdsp_boundary():
    text = """MANCHESTER PLANNING BOARD
Thursday, May 7, 2026 – 6:00 PM
1. CU2026-002 Property located at 57 Bay Street (Tax Map 15, Lot 12), a conversion of
commercial space into a new cafe. Engineer for Skiff Legacy Properties, LLC.
2. PDSP2025-009 Property located at 2035 Brown Avenue (Tax Map 688, Lot 122), a new
gas station and convenience store. TF Moran, Inc. for 4KV, LLC.
III. BUSINESS MEETING:"""
    projects = extract_manchester_projects(text)
    assert [(item["project_id"], item["applicant"], item["address"]) for item in projects] == [
        ("CU2026-002", "Skiff Legacy Properties, LLC", "57 Bay Street"),
        ("PDSP2025-009", "4KV, LLC", "2035 Brown Avenue"),
    ]
