"""File: nbt.py
Modification: 2026-10-12 — dependency-free, bounded NBT and Anvil reader.

Read-only parser for vanilla Java chunk / level.dat NBT. No world data is modified.
"""
from __future__ import annotations

from pathlib import Path
import re
import struct
import zlib


class NBTError(ValueError):
    """Malformed, unsupported or oversized NBT/region data."""


MAX_NBT_BYTES = 32 * 1024 * 1024
MAX_REGION_CHUNK_BYTES = 8 * 1024 * 1024
MAX_ITEMS = 4 * 1024 * 1024


def inflate_limited(payload: bytes, *, gzip_format: bool) -> bytes:
    """Decompress one complete stream without allocating unbounded output."""
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS if gzip_format else zlib.MAX_WBITS)
    try:
        output = decoder.decompress(payload, MAX_NBT_BYTES + 1)
        if len(output) > MAX_NBT_BYTES:
            raise NBTError('NBT decompressed size limit exceeded')
        if not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
            raise NBTError('Malformed, trailing or overlarge compressed NBT stream')
        output += decoder.flush(MAX_NBT_BYTES + 1 - len(output))
    except zlib.error as exc:
        raise NBTError(f'NBT decompression failed: {exc}') from exc
    if len(output) > MAX_NBT_BYTES:
        raise NBTError('NBT decompressed size limit exceeded')
    return output


class Reader:
    def __init__(self, data: bytes):
        if len(data) > MAX_NBT_BYTES:
            raise NBTError('NBT exceeds size limit')
        self.data = memoryview(data)
        self.idx = 0

    def take(self, size: int) -> memoryview:
        if size < 0 or self.idx + size > len(self.data):
            raise NBTError(f'NBT truncated / invalid length at byte {self.idx}')
        result = self.data[self.idx:self.idx + size]
        self.idx += size
        return result

    def unpack(self, fmt: str):
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))[0]

    def name(self) -> str:
        size = self.unpack('>H')
        try:
            return bytes(self.take(size)).decode('utf-8')
        except UnicodeDecodeError as exc:
            raise NBTError('Invalid NBT name encoding') from exc

    def read(self, typ: int, depth: int = 0):
        if depth > 96:
            raise NBTError('NBT nesting exceeds limit')
        if typ == 1:
            return self.unpack('>b')
        if typ == 2:
            return self.unpack('>h')
        if typ == 3:
            return self.unpack('>i')
        if typ == 4:
            return self.unpack('>q')
        if typ == 5:
            return self.unpack('>f')
        if typ == 6:
            return self.unpack('>d')
        if typ in (7, 11, 12):
            count = self.unpack('>i')
            width = {7: 1, 11: 4, 12: 8}[typ]
            if count < 0 or count > MAX_ITEMS:
                raise NBTError('Invalid NBT array length')
            data = self.take(count * width)
            if typ == 7:
                return bytes(data)
            return list(struct.unpack('>' + ('i' if typ == 11 else 'q') * count, data))
        if typ == 8:
            size = self.unpack('>H')
            try:
                return bytes(self.take(size)).decode('utf-8')
            except UnicodeDecodeError as exc:
                raise NBTError('Invalid NBT string encoding') from exc
        if typ == 9:
            subtype = self.unpack('>B')
            count = self.unpack('>i')
            if count < 0 or count > MAX_ITEMS or (subtype == 0 and count):
                raise NBTError('Invalid NBT list')
            return [self.read(subtype, depth + 1) for _ in range(count)]
        if typ == 10:
            result = {}
            while True:
                nexttype = self.unpack('>B')
                if nexttype == 0:
                    break
                name = self.name()
                result[name] = self.read(nexttype, depth + 1)
            return result
        raise NBTError(f'Unsupported NBT type {typ}')


def parse_nbt(data: bytes) -> dict:
    reader = Reader(data)
    typ = reader.unpack('>B')
    if typ != 10:
        raise NBTError('NBT root must be a compound')
    reader.name()  # root name: often empty
    root = reader.read(10)
    if reader.idx != len(reader.data):
        raise NBTError('Trailing bytes after NBT root')
    return root


def load_level(path: Path) -> dict:
    with (path / 'level.dat').open('rb') as handle:
        data = handle.read(MAX_NBT_BYTES + 1)
    if len(data) > MAX_NBT_BYTES:
        raise NBTError('Compressed level.dat exceeds size limit')
    try:
        return parse_nbt(inflate_limited(data, gzip_format=True))['Data']
    except (OSError, KeyError, EOFError, zlib.error) as exc:
        raise NBTError(f'Cannot read level.dat: {exc}') from exc


def region_filename(rx: int, rz: int) -> str:
    return f'r.{rx}.{rz}.mca'


REGION_NAME = re.compile(r'^r\.(-?\d+)\.(-?\d+)\.mca$')


class Region:
    """Opens one region file. Errors for individual chunks are recoverable."""
    def __init__(self, path: Path):
        self.path = path
        self.f = path.open('rb')
        self.f.seek(0, 2)
        self.length = self.f.tell()
        self.f.seek(0)
        self.header = self.f.read(4096)
        if self.length < 8192 or len(self.header) != 4096:
            self.close()
            raise NBTError(f'Invalid Anvil region header: {path}')

    def close(self):
        self.f.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def read_chunk(self, cx: int, cz: int) -> dict | None:
        idx = (cx & 31) + (cz & 31) * 32
        off = idx * 4
        sector = int.from_bytes(self.header[off:off + 3], 'big')
        sectors = self.header[off + 3]
        if sector == 0 and sectors == 0:
            return None
        if sector < 2 or sectors < 1 or sector * 4096 + 5 > self.length:
            raise NBTError(f'Invalid chunk location: {cx},{cz}')
        self.f.seek(sector * 4096)
        chunk_size = int.from_bytes(self.f.read(4), 'big')
        compression_raw = self.f.read(1)
        if not compression_raw:
            raise NBTError('Missing chunk compression marker')
        marker = compression_raw[0]
        external = (marker & 0x80) != 0
        compression = marker & 0x7f
        if not 0 < chunk_size <= MAX_REGION_CHUNK_BYTES:
            raise NBTError('Unreasonable chunk size')
        if external:
            payload_path = self.path.with_name(f'c.{cx}.{cz}.mcc')
            if not payload_path.is_file():
                raise NBTError(f'Missing external chunk: {payload_path}')
            with payload_path.open('rb') as handle:
                payload = handle.read(MAX_REGION_CHUNK_BYTES + 1)
        else:
            if chunk_size > sectors * 4096 - 4 or sector * 4096 + chunk_size + 4 > self.length:
                raise NBTError('Chunk extends beyond allocated sectors')
            payload = self.f.read(chunk_size - 1)
            if len(payload) != chunk_size - 1:
                raise NBTError('Truncated region chunk')
        if len(payload) > MAX_REGION_CHUNK_BYTES:
            raise NBTError('Compressed region payload exceeds size limit')
        if compression == 1:
            data = inflate_limited(payload, gzip_format=True)
        elif compression == 2:
            data = inflate_limited(payload, gzip_format=False)
        elif compression == 3:
            data = payload
        else:
            raise NBTError(f'Unsupported region compression {compression}; vanilla LZ4 (4) needs an optional decoder')
        root = parse_nbt(data)
        if root.get('xPos') != cx or root.get('zPos') != cz:
            raise NBTError(f'Chunk coordinates disagree with region index: {cx},{cz}')
        return root
