"""Validated inputs and deterministic primitives for macOS JAR releases."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import subprocess
import tarfile
import tempfile
import zipfile


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


@dataclass(frozen=True)
class VerificationReport:
    arch: str
    payload_files: int
    payload_bytes: int


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


def _zip_info(name: str, mode: int = 0o644) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = mode << 16
    return info


def _runtime_payload(archive: Path) -> list[tuple[str, bytes, int]]:
    result: list[tuple[str, bytes, int]] = []
    with tarfile.open(archive, "r:*") as source:
        for member in source.getmembers():
            name = _safe_member_name(member.name)
            if member.issym() or member.islnk():
                raise ValueError(f"Runtime links are not allowed: {name}")
            if not member.isfile():
                continue
            handle = source.extractfile(member)
            if handle is None:
                raise ValueError(f"Unable to read runtime member: {name}")
            mode = 0o755 if member.mode & 0o111 else 0o644
            result.append((name, handle.read(), mode))
    return sorted(result)


def _compiled_launcher(root: Path) -> list[tuple[str, bytes, int]]:
    source_root = root / "launcher" / "src"
    sources = sorted(source_root.rglob("*.java"))
    if not sources:
        raise ValueError("No Java launcher sources found")
    with tempfile.TemporaryDirectory() as td:
        classes = Path(td) / "classes"
        classes.mkdir()
        command = ["javac", "--release", "21", "-encoding", "UTF-8", "-d", str(classes)]
        command.extend(str(path) for path in sources)
        completed = subprocess.run(command, cwd=root, capture_output=True, text=True)
        if completed.returncode:
            raise ValueError(f"Java launcher compilation failed: {completed.stderr.strip()}")
        return [(path.relative_to(classes).as_posix(), path.read_bytes(), 0o644)
                for path in sorted(classes.rglob("*.class"))]


def build_jar(root: Path, runtime: Path, lock: RuntimeLock, output: Path) -> None:
    root = root.resolve()
    inspect_runtime(runtime, lock)
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    payload: list[tuple[str, bytes, int]] = _runtime_payload(runtime)
    payload.extend((item.path, item.source.read_bytes(), item.mode)
                   for item in collect_application(root))
    payload.sort(key=lambda item: item[0])
    names: set[str] = set()
    manifest_lines: list[str] = []
    for name, data, mode in payload:
        if name in names:
            raise ValueError(f"Duplicate payload path: {name}")
        names.add(name)
        manifest_lines.append(
            f"{hashlib.sha256(data).hexdigest()}\t{len(data)}\t{mode:04o}\t{name}")
    payload_manifest = ("\n".join(manifest_lines) + "\n").encode("utf-8")
    jar_manifest = ("Manifest-Version: 1.0\r\n"
                    "Main-Class: io.github.omiki.lowyoutpost.Launcher\r\n"
                    "Created-By: LowYOutpostFinder reproducible builder\r\n\r\n").encode("utf-8")
    properties = f"arch={lock.arch}\nversion={version}\n".encode("utf-8")
    entries = [("META-INF/MANIFEST.MF", jar_manifest, 0o644),
               ("launcher.properties", properties, 0o644),
               ("payload-manifest.tsv", payload_manifest, 0o644)]
    entries.extend(_compiled_launcher(root))
    entries.extend((f"payload/{name}", data, mode) for name, data, mode in payload)
    entries.sort(key=lambda item: item[0])
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    part = output.with_name(output.name + ".tmp")
    try:
        with zipfile.ZipFile(part, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=9) as built:
            for name, data, mode in entries:
                built.writestr(_zip_info(name, mode), data,
                               compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        verify_jar(part, lock.arch)
        part.replace(output)
    finally:
        part.unlink(missing_ok=True)


def verify_jar(path: Path, expected_arch: str) -> VerificationReport:
    expected = ARCH_ALIASES.get(expected_arch.lower())
    if expected is None:
        raise ValueError(f"Unsupported architecture: {expected_arch}")
    with zipfile.ZipFile(path) as built:
        infos = built.infolist()
        names = [item.filename for item in infos]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate JAR entry")
        manifest = built.read("META-INF/MANIFEST.MF")
        if b"Main-Class: io.github.omiki.lowyoutpost.Launcher" not in manifest:
            raise ValueError("JAR has no launcher Main-Class")
        properties = dict(line.split("=", 1) for line in
                          built.read("launcher.properties").decode("utf-8").splitlines())
        actual_arch = properties.get("arch")
        if actual_arch != expected:
            raise ValueError(f"JAR architecture {actual_arch} does not match {expected}")
        records = built.read("payload-manifest.tsv").decode("utf-8").splitlines()
        seen: set[str] = set()
        total = 0
        for line in records:
            digest, size_text, mode, name = line.split("\t")
            if name in seen:
                raise ValueError(f"Duplicate payload path: {name}")
            seen.add(name)
            data = built.read(f"payload/{name}")
            if len(data) != int(size_text) or hashlib.sha256(data).hexdigest() != digest:
                raise ValueError(f"Payload SHA-256 mismatch: {name}")
            if mode not in ("0644", "0755"):
                raise ValueError(f"Invalid payload mode: {mode}")
            total += len(data)
        forbidden = ("data/", ".git", ".agents", ".codex", ".superpowers", ".env")
        if any(any(part in name for part in forbidden) for name in names):
            raise ValueError("JAR contains forbidden private content")
        python_data = built.read("payload/runtime/bin/python3")
        if _macho_arch(python_data[:64]) != expected:
            raise ValueError("Embedded Python architecture does not match JAR architecture")
        return VerificationReport(expected, len(records), total)
