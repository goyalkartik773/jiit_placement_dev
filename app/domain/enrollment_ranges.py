"""Year-scoped enrollment-number ranges (config port only - no matching logic).

VERBATIM port of the reference repo ``tashifkhan/JIIT-placement-alerts``:

    services/placement/analysis/config.py:9-56      ``ENROLLMENT_RANGES``
    services/placement/analysis/config.py:91-258    ``BATCH_CONFIGS`` (ranges)
    services/placement/analysis/config.py:261-278   ``normalize_batch_year``
    services/placement/analysis/config.py:281-297   ``get_batch_config``
    services/placement/analysis/config.py:300-312   ``get_enrollment_ranges_for_year``
    services/placement/analysis/helpers.py:13-59    ``build_branch_ranges``
    services/placement/analysis/models.py:7-13      ``BranchRange``

Every number below is copied exactly - no rounding, no guessing, no
re-ordering.  ``ENROLLMENT_RANGES`` and ``BATCH_CONFIGS[..]['enrollment_ranges']``
carry the same 202526 numbers; the former is only a legacy alias kept for
traceability (config.py:1-7 says so).

SCOPE NOTE - what was deliberately NOT ported (would be dead code here):
``label``, ``graduating_batch``, ``student_counts``, ``excluded_branches``,
``STUDENT_COUNTS``, ``EXCLUDED_BRANCHES``.  Those feed the reference's own
stats/filtering, not the roll -> branch mapping this feature needs.

KEYING NOTE - the reference keys ranges by PLACEMENT year
(``202526`` = AY 2025-26, graduating batch 2026), NOT admission year.  We have
no placement-year context at read time, so :func:`ranges_for_admission_year`
derives the admission year from each range's own roll-number prefix.  See
``docs/roll_to_branch_mapping.md``.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- config.py:9-56 ---------------------------------------------------------
ENROLLMENT_RANGES: dict[str, dict[str, dict[str, int]]] = {
    "CSE": {
        "62": {
            "start": 22103000,
            "end": 22104000,
        },
        "128": {
            "start": 9922103000,
            "end": 9922104000,
        },
    },
    "ECE": {
        "62": {
            "start": 22102000,
            "end": 22103000,
        },
        "128": {
            "start": 9922102000,
            "end": 9922103000,
        },
    },
    "IT": {
        "62": {
            "start": 22104000,
            "end": 22105000,
        },
    },
    "BT": {
        "62": {
            "start": 22101000,
            "end": 22102000,
        },
    },
    "Intg. MTech": {
        "CSE": {
            "start": 21803000,
            "end": 21804000,
        },
        "ECE": {
            "start": 21802000,
            "end": 21803000,
        },
        "BT": {
            "start": 21801000,
            "end": 21802000,
        },
    },
}

DEFAULT_PLACEMENT_YEAR = "202526"

# --- config.py:91-258 (enrollment_ranges only) ------------------------------
BATCH_CONFIGS: dict[str, dict] = {
    "202526": {
        "enrollment_ranges": {
            "CSE": {
                "62": {
                    "start": 22103000,
                    "end": 22104000,
                },
                "128": {
                    "start": 9922103000,
                    "end": 9922104000,
                },
            },
            "ECE": {
                "62": {
                    "start": 22102000,
                    "end": 22103000,
                },
                "128": {
                    "start": 9922102000,
                    "end": 9922103000,
                },
            },
            "IT": {
                "62": {
                    "start": 22104000,
                    "end": 22105000,
                }
            },
            "BT": {
                "62": {
                    "start": 22101000,
                    "end": 22102000,
                }
            },
            "Intg. MTech": {
                "CSE": {
                    "start": 21803000,
                    "end": 21804000,
                },
                "ECE": {
                    "start": 21802000,
                    "end": 21803000,
                },
                "BT": {
                    "start": 21801000,
                    "end": 21802000,
                },
            },
        },
    },
    "202627": {
        "enrollment_ranges": {
            "CSE": {
                "62": {
                    "start": 23103000,
                    "end": 23104000,
                },
                "128": {
                    "start": 9923103000,
                    "end": 9923104000,
                },
            },
            "ECE": {
                "62": {
                    "start": 23102000,
                    "end": 23103000,
                },
                "128": {
                    "start": 9923102000,
                    "end": 9923103000,
                },
            },
            "EC-ACT": {
                "62": {
                    "start": 23119000,
                    "end": 23120000,
                }
            },
            "EE-VLSI": {
                "62": {
                    "start": 23118000,
                    "end": 23119000,
                }
            },
            "IT": {
                "62": {
                    "start": 23104000,
                    "end": 23105000,
                }
            },
            "BT": {
                "62": {
                    "start": 23101000,
                    "end": 23102000,
                }
            },
            "Intg. MTech": {
                "CSE": {
                    "start": 22903000,
                    "end": 22904000,
                },
                "ECE": {
                    "start": 22802000,
                    "end": 22803000,
                },
                "BT": {
                    "start": 22801000,
                    "end": 22802000,
                },
            },
        },
    },
}


# --- models.py:7-13 ---------------------------------------------------------
@dataclass
class BranchRange:
    """Enrollment number range for a branch."""

    branch: str
    start: int
    end: int


# --- config.py:261-278 ------------------------------------------------------
def normalize_batch_year(year: str | None) -> str:
    """
    Normalize a placement year to compact YYYYYY format.

    Args:
        year: Year value such as 202526, 2025-26, or 2025_26.

    Returns:
        Normalized year string, falling back to the default year.
    """
    if not year:
        return DEFAULT_PLACEMENT_YEAR
    digits = "".join(char for char in str(year) if char.isdigit())

    if len(digits) == 6:
        return digits

    return DEFAULT_PLACEMENT_YEAR


# --- config.py:281-297 ------------------------------------------------------
def get_batch_config(year: str | None = None) -> dict:
    """
    Get the batch config for a placement year.

    Unknown / malformed years silently fall back to the default year rather
    than raising (silent degrade - reference behaviour).
    """
    normalized = normalize_batch_year(year)
    config = BATCH_CONFIGS.get(normalized)

    if config is not None:
        return config

    return BATCH_CONFIGS[DEFAULT_PLACEMENT_YEAR]


# --- config.py:300-312 ------------------------------------------------------
def get_enrollment_ranges_for_year(
    year: str | None = None,
) -> dict[str, dict[str, dict[str, int]]]:
    """
    Get enrollment ranges for a placement year.

    Returns:
        Nested branch -> campus/sub -> {start, end} mapping.
    """
    return get_batch_config(year)["enrollment_ranges"]


# --- helpers.py:13-59 -------------------------------------------------------
def build_branch_ranges(
    config: dict[str, dict[str, dict[str, int]]],
) -> list[BranchRange]:
    """
    Build flattened branch ranges from configuration.

    Args:
        config: Nested dict of branch -> batch/sub -> {start, end}.

    Returns:
        Sorted list of BranchRange objects for efficient lookup.
    """
    ranges: list[BranchRange] = []

    for branch, data in config.items():
        if branch == "Intg. MTech":
            for sub_data in data.values():
                if (
                    isinstance(sub_data, dict)
                    and "start" in sub_data
                    and "end" in sub_data
                ):
                    ranges.append(
                        BranchRange(
                            branch="Intg. MTech",
                            start=sub_data["start"],
                            end=sub_data["end"],
                        )
                    )
        elif isinstance(data, dict):
            for batch_data in data.values():
                if (
                    isinstance(batch_data, dict)
                    and "start" in batch_data
                    and "end" in batch_data
                ):
                    ranges.append(
                        BranchRange(
                            branch=branch,
                            start=batch_data["start"],
                            end=batch_data["end"],
                        )
                    )

    return ranges


# ---------------------------------------------------------------------------
# OUR ADDITION - NOT in the reference repo.  See docs/roll_to_branch_mapping.md
#
# The reference is handed a placement year by its caller.  We serve students at
# request time with no placement-year context, so we recover the admission year
# from the roll-number prefix itself:
#
#     22103000   -> "22" -> 2022     9922103000 -> "99" stripped -> 2022
#     21803000   -> "21" -> 2021     23103000   -> "23" -> 2023
#
# Sanity check that this is not a guess: every range in BATCH_CONFIGS has a
# constant two-digit prefix, and the implied graduation maths is consistent -
# 4-year B.Tech 2022->2026 (202526) / 2023->2027 (202627), 5-year Intg. MTech
# 2021->2026 (202526) / 2022->2027 (202627).
# ---------------------------------------------------------------------------
CAMPUS_PREFIX = "99"
ADMISSION_YEAR_MIN = 2015
ADMISSION_YEAR_MAX = 2035
ADMISSION_YEAR_WINDOW = range(ADMISSION_YEAR_MIN, ADMISSION_YEAR_MAX + 1)


def strip_campus_prefix(digits: str) -> str:
    """Drop the 2-digit campus prefix from a long roll (``99`` + 8/10 digits).

    Live corpus has both ``9922103000`` (10) and ``992510170065`` (12), so the
    guard is "at least 10 digits" rather than "exactly 10" - an 8-digit roll
    such as ``99999999`` keeps its prefix and then fails the year window.
    """
    if len(digits) >= 10 and digits.startswith(CAMPUS_PREFIX):
        return digits[len(CAMPUS_PREFIX) :]
    return digits


def admission_year_from_digits(digits: str) -> int | None:
    """``22103000`` -> ``2022``; anything outside the window -> ``None``.

    Returns ``None`` (never raises) when the prefix cannot be a year, so an
    unknown/future admission year degrades instead of crashing.
    """
    core = strip_campus_prefix(digits)
    if len(core) < 2 or not core[:2].isdigit():
        return None

    year = 2000 + int(core[:2])
    if year not in ADMISSION_YEAR_WINDOW:
        return None
    return year


def _dedupe(ranges: list[BranchRange]) -> list[BranchRange]:
    seen: set[tuple[str, int, int]] = set()
    unique: list[BranchRange] = []
    for item in ranges:
        key = (item.branch, item.start, item.end)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def all_branch_ranges() -> list[BranchRange]:
    """Every configured range across every placement year (union, de-duped).

    Configured ranges are mutually disjoint (``218xxxxx`` / ``221xxxxx`` /
    ``228xxxxx`` / ``229xxxxx`` / ``231xxxxx`` and their ``99``-prefixed
    twins), so the union lookup is deterministic.
    """
    flat: list[BranchRange] = []
    for config in BATCH_CONFIGS.values():
        flat.extend(build_branch_ranges(config["enrollment_ranges"]))
    return _dedupe(flat)


def ranges_for_admission_year(admission_year: int | None) -> list[BranchRange]:
    """Ranges belonging to one admission year.

    ``None`` -> the union of every configured year (read-time default).
    An admission year with no configured ranges -> ``[]``, which makes the
    caller return ``"Other"`` (silent degrade, never raises).
    """
    every = all_branch_ranges()
    if admission_year is None:
        return every

    return [
        item
        for item in every
        if admission_year_from_digits(str(item.start)) == admission_year
    ]
