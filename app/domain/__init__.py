"""Pure, side-effect-free domain helpers.

No DB, no network, no settings - just deterministic functions over constants.
Deliberately importable from anywhere (scripts, serializers, tests) without
wiring up the container.
"""

from app.domain.enrollment_ranges import (
    ADMISSION_YEAR_WINDOW,
    BATCH_CONFIGS,
    DEFAULT_PLACEMENT_YEAR,
    ENROLLMENT_RANGES,
    BranchRange,
    all_branch_ranges,
    build_branch_ranges,
    get_batch_config,
    get_enrollment_ranges_for_year,
    normalize_batch_year,
    ranges_for_admission_year,
)
from app.domain.roll_mapper import resolve_branch, resolve_batch_year

__all__ = [
    "ADMISSION_YEAR_WINDOW",
    "BATCH_CONFIGS",
    "DEFAULT_PLACEMENT_YEAR",
    "ENROLLMENT_RANGES",
    "BranchRange",
    "all_branch_ranges",
    "build_branch_ranges",
    "get_batch_config",
    "get_enrollment_ranges_for_year",
    "normalize_batch_year",
    "ranges_for_admission_year",
    "resolve_branch",
    "resolve_batch_year",
]
