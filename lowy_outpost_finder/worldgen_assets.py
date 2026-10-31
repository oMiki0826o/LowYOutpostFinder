"""Pinned Minecraft Java 1.21.8 outpost assets used by the seed-only model.

The scanner does not open a game JAR.  This module gives maintainers an
optional, reproducible way to detect when a future Minecraft asset differs
from the version whose placement geometry and biome tag were implemented.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile


OUTPOST_ASSET_SHA256: dict[str, str] = {
    "data/minecraft/worldgen/structure/pillager_outpost.json": "9389a0a9ff5c933b7c0a41814f07cb70ff8de00a8b314ec1bbb1ffdba799340d",
    "data/minecraft/worldgen/structure_set/pillager_outposts.json": "ef50ffd8d1b6fbe6c48bb15e9d4793ac9630560b354a35b0150b9966439ed53c",
    "data/minecraft/tags/worldgen/biome/has_structure/pillager_outpost.json": "fc8bd6d3184456aa070a82394878ad621425eb993b696314eb8380aca7d94f72",
    "data/minecraft/tags/worldgen/biome/is_mountain.json": "da761310afa4c0a9cd978036150b91ecb0c427e65192d4d60486eb7206b03fe4",
    "data/minecraft/structure/pillager_outpost/base_plate.nbt": "84355755e68a62a98435e44904b2b65c3cf1377b1257c2ab84d927aa85a7141c",
    "data/minecraft/structure/pillager_outpost/watchtower.nbt": "987c57670e3bdcfa5a1e620ffe74d49aa10f03cd451ceacdce85f19dd2d7fdf8",
}

# Stable audit label for seed-only output.  It deliberately does not call the
# terrain sampler exact: placement geometry and structure/biome assets are
# pinned to 1.21.8, while Y remains an independently labelled estimate.
OUTPOST_ASSET_MODEL = "minecraft-java-1.21.8-outpost-assets-pinned"


def verify_outpost_assets(jar: Path) -> dict[str, str]:
    """Return mismatched asset digests; an empty result means exact 1.21.8 assets."""
    mismatches: dict[str, str] = {}
    with ZipFile(jar) as source:
        for name, expected in OUTPOST_ASSET_SHA256.items():
            try:
                actual = sha256(source.read(name)).hexdigest()
            except KeyError:
                actual = "missing"
            if actual != expected:
                mismatches[name] = actual
    return mismatches
