"""Validated inputs and deterministic primitives for macOS JAR releases."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import tarfile


ARCH_CPU_TYPES = {"x86_64": 0x01000007, "arm64": 0x0100000C}
ARCH_ALIASES = {"amd64": "x86_64", "x86_64": "x86_64",
                "aarch64": "arm64", "arm64": "arm64"}
MAX_RUNTIME_FILES = 50_000
MAX_RUNTIME_BYTES = 2_000_000_000


@dataclass(frozen=True)
class RuntimeLock:
    arch: str
    url: str
    python_version: str
    tk_version: str
    sha256: str
    licenses: tuple[str, ...]

    @classmethod
    def load(cls, path: Path, arch: str) -> "RuntimeLock":
        normalized = ARCH_ALIASES.get(arch.lower())
        if normalized is None:
            raise ValueError(f"Unsupported architecture: {arch}")
        try:
            item = json.loads(path.read_text(encoding="utf-8"))["runtimes"][normalized]
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"No complete runtime lock for {normalized}") from exc
        required = ("url", "python", "tk", "sha256", "licenses")
        if any(key not in item for key in required):
            raise ValueError(f"Incomplete runtime lock for {normalized}")
        digest = str(item["sha256"])
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("Runtime SHA-256 must be 64 lowercase hexadecimal characters")
        licenses = tuple(str(value) for value in item["licenses"])
        if not licenses:
            raise ValueError("Runtime lock requires at least one license")
        return cls(normalized, str(item["url"]), str(item["python"]),
                   str(item["tk"]), digest, licenses)


@dataclass(frozen=True)
class RuntimeLayout:
    arch: str
    python_path: str
    members: tuple[str, ...]


@dataclass(frozen=True)
class PayloadFile:
    source: Path
    path: str
    mode: int


def _safe_member_name(name: str) -> str:
    if "\\" in name:
        raise ValueError(f"Unsafe runtime path: {name}")
    pure = PurePosixPath(name)
    if pure.is_absolute() or not pure.parts or any(part in ("", ".", "..") for part in pure.parts):
        raise ValueError(f"Unsafe runtime path: {name}")
    return pure.as_posix()


def _macho_arch(data: bytes) -> str:
    if len(data) < 8:
        raise ValueError("Mach-O executable is truncated")
    magic_be = struct.unpack(">I", data[:4])[0]
    magic_le = struct.unpack("<I", data[:4])[0]
    if magic_be in (0xFEEDFACE, 0xFEEDFACF):
        cpu = struct.unpack(">I", data[4:8])[0]
    elif magic_le in (0xFEEDFACE, 0xFEEDFACF):
        cpu = struct.unpack("<I", data[4:8])[0]
    else:
        raise ValueError("Runtime executable is not a supported thin Mach-O file")
    for arch, expected in ARCH_CPU_TYPES.items():
        if cpu == expected:
            return arch
    raise ValueError(f"Unsupported Mach-O CPU type: 0x{cpu:08x}")


def inspect_runtime(archive: Path, lock: RuntimeLock) -> RuntimeLayout:
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != lock.sha256:
        raise ValueError("Runtime archive SHA-256 does not match lock")
    names: list[str] = []
    seen: set[str] = set()
    python_path = ""
    tkinter_found = False
    tcl_found = False
    tk_found = False
    license_found = set()
    total_size = 0
    with tarfile.open(archive, "r:*") as source:
        members = source.getmembers()
        if len(members) > MAX_RUNTIME_FILES:
            raise ValueError("Runtime archive contains too many files")
        for member in members:
            name = _safe_member_name(member.name)
            if name in seen:
                raise ValueError(f"Duplicate runtime member: {name}")
            seen.add(name)
            if member.issym() or member.islnk():
                raise ValueError(f"Runtime links are not allowed: {name}")
            if not member.isfile():
                continue
            total_size += member.size
            if total_size > MAX_RUNTIME_BYTES:
                raise ValueError("Runtime archive is too large")
            names.append(name)
            if name.endswith("/bin/python3") or name.endswith("/bin/python"):
                handle = source.extractfile(member)
                if handle is None:
                    raise ValueError("Unable to inspect Python executable")
                actual = _macho_arch(handle.read(64))
                if actual != lock.arch:
                    raise ValueError(f"Runtime architecture {actual} does not match {lock.arch}")
                python_path = name
            if "_tkinter" in PurePosixPath(name).name:
                tkinter_found = True
            if "/tcl" in name and name.endswith("init.tcl"):
                tcl_found = True
            if "/tk" in name and name.endswith("tk.tcl"):
                tk_found = True
            if name in lock.licenses:
                license_found.add(name)
    if not python_path:
        raise ValueError("Runtime is missing Python executable")
    if not tkinter_found:
        raise ValueError("Runtime is missing _tkinter")
    if not (tcl_found and tk_found):
        raise ValueError("Runtime is missing Tcl/Tk libraries")
    missing_licenses = set(lock.licenses) - license_found
    if missing_licenses:
        raise ValueError(f"Runtime is missing license: {sorted(missing_licenses)[0]}")
    return RuntimeLayout(lock.arch, python_path, tuple(sorted(names)))


def collect_application(root: Path) -> list[PayloadFile]:
    version = root / "VERSION"
    package = root / "lowy_outpost_finder"
    if not version.is_file() or not package.is_dir():
        raise ValueError("Project requires VERSION and lowy_outpost_finder package")
    result = [PayloadFile(version, "app/VERSION", 0o644)]
    for source in sorted(package.rglob("*.py")):
        if source.is_symlink() or not source.is_file():
            continue
        relative = source.relative_to(root).as_posix()
        result.append(PayloadFile(source, f"app/{relative}", 0o644))
    return result
