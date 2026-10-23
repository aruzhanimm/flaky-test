"""Test that a damaged snapshot cannot overwrite local files or escape its root."""
import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from restore_artifacts import restore


class RestoreTests(unittest.TestCase):
    def fixture(self, root, name="data/example.txt", content=b"evidence"):
        (root / "artifacts").mkdir()
        archive = root / "artifacts/test.tar.xz"
        with tarfile.open(archive, "w:xz") as bundle:
            member = tarfile.TarInfo(name)
            member.size = len(content)
            bundle.addfile(member, io.BytesIO(content))
        manifest = {"archive": {"path": "artifacts/test.tar.xz", "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}, "files": [{"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}]}
        (root / "artifacts/manifest.json").write_text(json.dumps(manifest))
        return archive

    def test_restore_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            self.assertEqual(restore(root)["restored_files"], 1)
            self.assertEqual(restore(root)["restored_files"], 0)
            self.assertEqual((root / "data/example.txt").read_bytes(), b"evidence")

    def test_preserves_changed_local_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            restore(root)
            target = root / "data/example.txt"
            target.write_bytes(b"local changes")
            with self.assertRaisesRegex(ValueError, "Existing file differs"):
                restore(root)
            self.assertEqual(target.read_bytes(), b"local changes")

    def test_rejects_archive_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = self.fixture(root)
            archive.write_bytes(archive.read_bytes() + b"changed")
            with self.assertRaisesRegex(ValueError, "archive checksum"):
                restore(root)

    def test_rejects_parent_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root, "../escape.txt")
            with self.assertRaisesRegex(ValueError, "Unsafe archive member"):
                restore(root)


if __name__ == "__main__":
    unittest.main()
