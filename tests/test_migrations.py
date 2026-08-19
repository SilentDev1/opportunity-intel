from pathlib import Path


def test_initial_migration_exists():
    assert (
        "Base.metadata.create_all"
        in Path("migrations/versions/20260819_0001_initial.py").read_text()
    )
