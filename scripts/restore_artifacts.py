"""Restore the frozen snapshot using only the Python standard library."""
import hashlib
import json
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def restore(root=ROOT):
    root = Path(root).resolve()
    manifest = json.loads((root / "artifacts/manifest.json").read_text())
    archive = root / manifest["archive"]["path"]
    if sha(archive.read_bytes()) != manifest["archive"]["sha256"]:
        raise ValueError("Snapshot archive checksum mismatch")
    expected = {item["path"]: item for item in manifest["files"]}
    pending = []
    with tarfile.open(archive, "r:xz") as bundle:
        members = bundle.getmembers()
        if len(members) != len(expected) or {m.name for m in members} != set(expected):
            raise ValueError("Archive inventory differs from the manifest")
        for member in members:
            name = PurePosixPath(member.name)
            target = (root / member.name).resolve()
            if not member.isfile() or name.is_absolute() or ".." in name.parts or not target.is_relative_to(root):
                raise ValueError(f"Unsafe archive member: {member.name}")
            data = bundle.extractfile(member).read()
            record = expected[member.name]
            if len(data) != record["bytes"] or sha(data) != record["sha256"]:
                raise ValueError(f"File checksum mismatch: {member.name}")
            if target.exists() and target.read_bytes() != data:
                raise ValueError(f"Existing file differs; keep or move it before restoring: {member.name}")
            if not target.exists():
                pending.append((target, data))
    # Validate every member and existing target before writing anything.
    for target, data in pending:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return {"verified_files": len(expected), "restored_files": len(pending), "archive_sha256": manifest["archive"]["sha256"]}


if __name__ == "__main__":
    print(json.dumps(restore(), indent=2))
