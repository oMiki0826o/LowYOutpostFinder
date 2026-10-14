from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from macos_jar import RuntimeLock, collect_application, inspect_runtime


CPU = {"x86_64": 0x01000007, "arm64": 0x0100000C}


def macho(arch: str) -> bytes:
    return struct.pack(">IIIIIIII", 0xFEEDFACF, CPU[arch], 0, 2, 0, 0, 0, 0)


def runtime_archive(path: Path, arch: str, *, tkinter: bool = True,
                    license_file: bool = True) -> None:
    entries = {
        "runtime/bin/python3": macho(arch),
        "runtime/lib/python3.13/_tkinter.so": macho(arch),
        "runtime/lib/tcl8.6/init.tcl": b"package provide Tcl 8.6\n",
        "runtime/lib/tk8.6/tk.tcl": b"package provide Tk 8.6\n",
        "runtime/LICENSE.txt": b"Python license\n",
    }
    if not tkinter:
        entries.pop("runtime/lib/python3.13/_tkinter.so")
    if not license_file:
        entries.pop("runtime/LICENSE.txt")
    with tarfile.open(path, "w:gz") as archive:
        for name, data in entries.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o755 if name.endswith("python3") else 0o644
            archive.addfile(info, io.BytesIO(data))


class MacosJarContractTests(unittest.TestCase):
    def test_runtime_lock_requires_exact_arch_and_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive = root / "runtime.tar.gz"
            runtime_archive(archive, "arm64")
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            lock_path = root / "lock.json"
            lock_path.write_text(json.dumps({"runtimes": {
                "arm64": {"url": "https://example.invalid/python.tar.gz",
                          "python": "3.13.0", "tk": "8.6", "sha256": digest,
                          "licenses": ["runtime/LICENSE.txt"]}}}))

            lock = RuntimeLock.load(lock_path, "arm64")
            self.assertEqual(lock.arch, "arm64")
            self.assertEqual(lock.sha256, digest)
            with self.assertRaisesRegex(ValueError, "x86_64"):
                RuntimeLock.load(lock_path, "x86_64")

            archive.write_bytes(archive.read_bytes() + b"tamper")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                inspect_runtime(archive, lock)

    def test_runtime_rejects_wrong_macho_architecture(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / "runtime.tar.gz"
            runtime_archive(archive, "x86_64")
            lock = RuntimeLock("arm64", "https://example.invalid/runtime", "3.13.0",
                               "8.6", hashlib.sha256(archive.read_bytes()).hexdigest(),
                               ("runtime/LICENSE.txt",))
            with self.assertRaisesRegex(ValueError, "architecture"):
                inspect_runtime(archive, lock)

    def test_runtime_requires_python_tk_and_licenses(self) -> None:
        for missing, kwargs in (("_tkinter", {"tkinter": False}),
                                ("license", {"license_file": False})):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as td:
                archive = Path(td) / "runtime.tar.gz"
                runtime_archive(archive, "arm64", **kwargs)
                lock = RuntimeLock("arm64", "https://example.invalid/runtime", "3.13.0",
                                   "8.6", hashlib.sha256(archive.read_bytes()).hexdigest(),
                                   ("runtime/LICENSE.txt",))
                with self.assertRaisesRegex(ValueError, missing):
                    inspect_runtime(archive, lock)

    def test_application_allowlist_excludes_private_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "VERSION").write_text("2.13.0\n")
            package = root / "lowy_outpost_finder"
            package.mkdir()
            (package / "__init__.py").write_text("")
            (package / "gui.py").write_text("def main(): pass\n")
            (root / "data").mkdir()
            (root / "data" / "secret.txt").write_text("secret")
            (root / ".git").mkdir()
            (root / ".git" / "config").write_text("private")

            names = [item.path for item in collect_application(root)]
            self.assertEqual(names, ["app/VERSION", "app/lowy_outpost_finder/__init__.py",
                                     "app/lowy_outpost_finder/gui.py"])


if __name__ == "__main__":
    unittest.main()
