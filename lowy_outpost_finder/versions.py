"""File: versions.py
Modification: 2026-10-12 — bounded, evidence-based Java Edition support from 1.21 to 26.3.

Version metadata is deliberately separate from the seed placement RNG.
Unknown future releases are NOT automatically asserted compatible.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VersionSupport:
    id: str
    placement: str = 'pillager_outposts_1.21'
    status: str = 'candidate_algorithm_only'


# Java Edition stable releases only; 1.21 introduced ominous bottles.
# The generator-level acceptance of structure placement does not prove
# terrain, biome, or Jigsaw results for any particular seed/version.
VERSIONS = tuple(VersionSupport(ver) for ver in (
    '1.21', '1.21.1', '1.21.2', '1.21.3', '1.21.4', '1.21.5',
    '1.21.6', '1.21.7', '1.21.8', '1.21.9', '1.21.10', '1.21.11',
    '26.1', '26.1.1', '26.1.2', '26.2', '26.3',
))
SUPPORTED = frozenset(v.id for v in VERSIONS)
KNOWN_DATAVERSIONS = {4440: '1.21.8', 5023: '26.3'}  # 26.3 from the supplied server.jar version.json.


def check_version(version: str) -> str:
    if version not in SUPPORTED:
        raise ValueError(
            f'Unsupported Java version {version!r}. Select a listed 1.21–26.3 stable version; '
            'future releases need new placement/NBT regression checks.'
        )
    return version


def detect_world_version(info: dict, requested: str = 'auto') -> tuple[str, int]:
    """Accept only explicitly known world versions, never infer by nearest DataVersion.

    `Version.Name` in level.dat is preferred. Older/incomplete level.dat requires a
    known unambiguous DataVersion. Chunk DataVersion must separately match.
    """
    if requested != 'auto':
        check_version(requested)
    dv = info.get('DataVersion')
    if not isinstance(dv, int) or dv < 0:
        raise ValueError('level.dat has missing/invalid DataVersion')
    metadata = info.get('Version', {})
    name = metadata.get('Name') if isinstance(metadata, dict) else None
    if isinstance(name, str) and name:
        check_version(name)
        expected_dv = next((num for num, ver in KNOWN_DATAVERSIONS.items() if ver == name), None)
        if expected_dv is not None and dv != expected_dv:
            raise ValueError(f'level.dat declares {name} but has unexpected DataVersion {dv}; expected {expected_dv}')
    else:
        name = KNOWN_DATAVERSIONS.get(dv)
        if name is None:
            raise ValueError('level.dat has no recognized Version.Name; cannot infer version from DataVersion')
    if requested != 'auto' and requested != name:
        raise ValueError(f'World is {name}, but selected version is {requested}; refusing cross-version verification')
    return name, dv
