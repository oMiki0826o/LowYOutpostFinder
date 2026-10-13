"""File: search_conditions.py
Modification: 2026-10-13 — canonical threshold and nearest-with-evidence evaluation.

This module never converts estimates or unresolved chunks into confirmed results.
"""
from __future__ import annotations

import math

# Only these terminal statuses provide conclusive evidence for a candidate.
CONCLUSIVE = frozenset({'absent', 'verified_tower'})


def conclusive(row: dict) -> bool:
    if row.get('status') == 'absent':
        return True
    if row.get('status') != 'verified_tower':
        return False
    try:
        return math.isfinite(float(row.get('structure_center_y'))) and math.isfinite(float(row.get('base_plate_y')))
    except (ValueError, TypeError):
        return False


def accepted_tower(row: dict, *, center_below: float | None, max_y: int | None) -> bool:
    """Apply all active filters identically when stopping and when exporting."""
    if row.get('status') != 'verified_tower':
        return False
    try:
        center = float(row.get('structure_center_y'))
        base = float(row.get('base_plate_y'))
    except (ValueError, TypeError):
        return False
    if not (math.isfinite(center) and math.isfinite(base)):
        return False
    return (center_below is None or center < center_below) and (max_y is None or base <= max_y)


def summarize_search(rows: list[dict], *, center_below: float | None,
                     max_y: int | None, total_candidates: int,
                     priority: str = 'near-origin') -> dict:
    """Return evidence; never claim nearest when earlier candidates are unresolved.

    A first passing tower is nearest within the *specified radius* only when
    every earlier near-origin candidate was conclusively checked. A truncated
    no-hit scan cannot prove absence in the radius.
    """
    if total_candidates < len(rows):
        raise ValueError('More audit rows than candidate positions')
    hits = [i for i,row in enumerate(rows) if accepted_tower(row, center_below=center_below, max_y=max_y)]
    first = hits[0] if hits else None
    unresolved_before = sum(not conclusive(row)
                            for row in rows[:first] if first is not None) if first is not None else 0
    if first is None:
        status = 'no_hit_exhaustive' if (priority == 'near-origin'
                  and len(rows) == total_candidates and
                  all(conclusive(row) for row in rows)) else 'not_proven'
    else:
        status = ('nearest_proven_within_radius' if priority == 'near-origin'
                  and not unresolved_before else 'not_proven')
    # 'Lowest' requires complete, conclusive coverage of the entire requested
    # square, never just an early-stopped sample or an experimental terrain rank.
    exhausted = (priority == 'near-origin' and len(rows) == total_candidates
                 and all(conclusive(row) for row in rows))
    lowest_status = ('lowest_verified_within_radius' if hits else
                     'no_eligible_towers_within_radius') if exhausted else 'not_proven'
    return {'nearest_status': status, 'lowest_status': lowest_status,
            'confirmed_hits': len(hits),
            'checked': len(rows), 'candidate_count': total_candidates,
            'unchecked': total_candidates-len(rows),
            'unresolved_before_first_hit': unresolved_before,
            'priority': priority,
            'warning': 'This is not a worldwide lowest-Y proof and not a seed-only height calculation.'}
