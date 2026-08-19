from opportunity_intel.models import ReviewItem, Source


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_validation_empty_is_truthful(client):
    data = client.get("/validation/summary").json()
    assert data["opportunities"] == 0 and data["actionable_conversion_rate"] is None


def test_admin_collection_is_restricted(client, db):
    source = Source(
        name="disabled",
        source_type="other",
        jurisdiction="NH",
        base_url="https://example.gov",
        collector_name="civic_engage_agenda",
        enabled=False,
    )
    db.add(source)
    db.commit()
    assert client.post(f"/collect/{source.id}").status_code == 403
    assert (
        client.post(f"/collect/{source.id}", headers={"x-admin-key": "test-secret"}).status_code
        == 404
    )


def test_dashboard_escapes_external_content(client, db):
    source = Source(
        name="<script>alert(1)</script>",
        source_type="other",
        jurisdiction="NH",
        base_url="https://example.gov",
        collector_name="civic_engage_agenda",
    )
    db.add(source)
    db.commit()
    body = client.get("/dashboard/sources").text
    assert "&lt;script&gt;" in body and "<script>alert(1)</script>" not in body


def test_review_action_is_admin_only(client, db):
    item = ReviewItem(
        review_type="uncertain", entity_type="opportunity", entity_id="123", reason="check"
    )
    db.add(item)
    db.commit()
    payload = {"resolution": "uncertain", "notes": "Needs another source"}
    assert client.post(f"/review/{item.id}", json=payload).status_code == 403
    response = client.post(
        f"/review/{item.id}", json=payload, headers={"x-admin-key": "test-secret"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "resolved"
