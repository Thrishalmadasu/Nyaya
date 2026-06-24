"""Centralised graph configuration — the single source of truth for tunable limits.

Keeping these reads in one place avoids the value drifting across modules (the
round cap was previously hardcoded with four different defaults). The operative
value lives in the ``MOOT_COURT_MAX_ROUNDS`` environment variable; the fallback
here is the only place a default is written.
"""
from __future__ import annotations

import os

# Default applied only when MOOT_COURT_MAX_ROUNDS is unset in the environment.
_DEFAULT_MAX_ROUNDS = "3"


def get_max_rounds() -> int:
    """Maximum number of rounds the Judge will auto-argue before the human gate.

    Read at call time so it always reflects the current environment (after
    ``load_dotenv``). Note this caps only the *automatic* loop — at the HITL gate
    the human reviewer may still request further rounds beyond this number.
    """
    return int(os.getenv("MOOT_COURT_MAX_ROUNDS", _DEFAULT_MAX_ROUNDS))
