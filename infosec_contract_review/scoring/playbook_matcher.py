"""Match obligations to playbook entries by theme and risk pattern keywords."""
from __future__ import annotations

import logging

from infosec_contract_review.models.obligation import Obligation
from infosec_contract_review.models.playbook import PlaybookEntry

logger = logging.getLogger(__name__)


def match_obligation_to_playbook(
    obligation: Obligation,
    playbook_entries: list[PlaybookEntry],
) -> PlaybookEntry | None:
    """Find the best matching playbook entry for an obligation.

    Simple keyword-based matching on theme + risk_pattern keywords.
    Returns the first matching entry or None.
    """
    obl_theme = obligation.theme.value if hasattr(obligation.theme, "value") else str(obligation.theme)
    obl_text = (obligation.summary or "").lower()

    theme_entries = [
        pe for pe in playbook_entries
        if pe.is_active and (
            pe.theme.value if hasattr(pe.theme, "value") else str(pe.theme)
        ) == obl_theme
    ]

    if not theme_entries:
        return None

    best_match: PlaybookEntry | None = None
    best_score = 0

    for pe in theme_entries:
        pattern_words = pe.risk_pattern.lower().split()
        score = sum(1 for w in pattern_words if len(w) > 3 and w in obl_text)

        applicable_words = pe.applicable_when.lower().split()
        score += sum(0.5 for w in applicable_words if len(w) > 3 and w in obl_text)

        if score > best_score:
            best_score = score
            best_match = pe

    if best_score < 2:
        return None

    return best_match
