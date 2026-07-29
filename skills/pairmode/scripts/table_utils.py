"""table_utils.py — the single owner of Markdown-table row splitting.

One function, one reason to change. This module imports only the Python
standard library and no sibling pairmode module, deliberately: every table
reader in `skills/pairmode/scripts/` imports it, and a module with sibling
imports at that fan-in would eventually close an import cycle (the
`flex_build` ↔ `index_integrity` pair already has to lazy-import around one).

INFRA-297 — consolidation of CER-069.
"""

from __future__ import annotations

import re

# Split on unescaped pipes only. Single-sourced here (INFRA-297/B2): this is
# the only place in `skills/pairmode/scripts/` where this literal lives.
_UNESCAPED_PIPE_RE = re.compile(r'(?<!\\)\|')


def split_table_row(stripped: str) -> list[str]:
    r"""Split one Markdown table row on unescaped pipes.

    Why this exists, not just what it does: in Markdown, ``\|`` is a *literal
    cell character* — an escaped pipe — not a column separator. A naive
    ``str.split('|')`` shreds a title cell like ``Edit\|Write`` into two extra
    "columns" and shifts every positional read after it, so a status column
    read at a fixed index silently becomes the wrong cell. That defect was
    filed as CER-066, fixed once in ``story_update.py`` (INFRA-207, Phase 94)
    and again in ``next_action._check_phase_completion`` (INFRA-222, Phase 95),
    and re-filed as CER-069 when the same shape was found at seven further
    call sites. INFRA-297 is the consolidation: the split now has one owner,
    so an eighth site cannot get it wrong by copy-paste.

    Returns the **raw** parts, including the empty string before the first
    ``|`` and the empty string after the last. No per-cell ``.strip()`` is
    applied — callers keep their own stripping and slicing (typically
    ``[1:-1]`` or a positional ``parts[1]``/``parts[3]``), so converting a
    call site is behaviour-preserving.

    The split is **non-destructive**: it does not unescape ``\|``. The escaped
    pipe stays in the returned cell verbatim::

        >>> split_table_row(r"| a | b\|c | d |")
        ['', ' a ', ' b\\|c ', ' d ', '']

    That is load-bearing, not incidental. The ``mark-phase-complete`` rewrite
    paths in ``flex_build.py`` (the phase-index and era-ledger row rewrites)
    split a row, edit one cell, rejoin the rest with ``" | "`` and write the
    row back to disk. An unescaping split would silently corrupt every row it
    touched — the rewritten row would carry a bare ``|`` where the source had
    ``\|``, turning one cell into two on the next read.

    Args:
        stripped: a single table row, typically already ``.strip()``ed.

    Returns:
        The row's parts, in order, un-stripped and un-unescaped.
    """
    return _UNESCAPED_PIPE_RE.split(stripped)
