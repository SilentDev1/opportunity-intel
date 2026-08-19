import hashlib
from pathlib import Path


class LocalArtifactStorage:
    def __init__(self, root: Path):
        self.root = root

    def put(self, content: bytes, suffix: str = ".bin") -> tuple[str, str]:
        digest = hashlib.sha256(content).hexdigest()
        path = self.root / digest[:2] / f"{digest}{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(content)
        return str(path), digest

    def get(self, path: str) -> bytes:
        return Path(path).read_bytes()
