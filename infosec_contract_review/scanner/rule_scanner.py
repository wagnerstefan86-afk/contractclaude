"""Deterministic rule scanner based on rule_scan_config.yaml."""
from __future__ import annotations

import logging
import pathlib
import re
from dataclasses import dataclass, field
from functools import lru_cache

import yaml

logger = logging.getLogger(__name__)

SEED_DIR = pathlib.Path(__file__).parent.parent / "seed"


@dataclass
class ScanResult:
    deterministic_flags: list[str] = field(default_factory=list)
    routing_tier: str = "presumably_irrelevant"
    routed_themes: list[str] = field(default_factory=list)


@dataclass
class _CompiledHighSignal:
    pattern: re.Pattern
    flags: list[str]
    theme: str


@dataclass
class _MediumSignal:
    keyword: str
    flags: list[str]
    theme: str


@dataclass
class _StructuralSignal:
    keyword: str
    flags: list[str]


class RuleScanner:
    def __init__(self):
        config = _load_config()
        self._enabled = config.get("enabled", True)
        self._high_signals: list[_CompiledHighSignal] = []
        self._medium_signals: list[_MediumSignal] = []
        self._structural_signals: list[_StructuralSignal] = []

        for entry in config.get("high_signal_phrases", []):
            try:
                self._high_signals.append(_CompiledHighSignal(
                    pattern=re.compile(entry["pattern"]),
                    flags=entry["flags"],
                    theme=entry["theme"],
                ))
            except re.error as e:
                logger.warning("Invalid regex in rule_scan_config: %s – %s", entry["pattern"], e)

        for entry in config.get("medium_signal_keywords", []):
            self._medium_signals.append(_MediumSignal(
                keyword=entry["keyword"].lower(),
                flags=entry["flags"],
                theme=entry.get("theme", ""),
            ))

        for entry in config.get("structural_signals", []):
            self._structural_signals.append(_StructuralSignal(
                keyword=entry["keyword"].lower(),
                flags=entry["flags"],
            ))

        logger.info(
            "RuleScanner initialized: %d high, %d medium, %d structural signals",
            len(self._high_signals), len(self._medium_signals), len(self._structural_signals),
        )

    def scan(self, text: str) -> ScanResult:
        if not self._enabled:
            return ScanResult()

        flags: list[str] = []
        themes: set[str] = set()
        tier = "presumably_irrelevant"

        for hs in self._high_signals:
            if hs.pattern.search(text):
                flags.extend(f for f in hs.flags if f not in flags)
                themes.add(hs.theme)
                tier = "clearly_relevant"

        text_lower = text.lower()

        for ms in self._medium_signals:
            if ms.keyword in text_lower:
                flags.extend(f for f in ms.flags if f not in flags)
                if ms.theme:
                    themes.add(ms.theme)
                if tier not in ("clearly_relevant",):
                    tier = "potentially_relevant"

        for ss in self._structural_signals:
            if ss.keyword in text_lower:
                flags.extend(f for f in ss.flags if f not in flags)
                if tier == "presumably_irrelevant":
                    tier = "structurally_relevant"

        return ScanResult(
            deterministic_flags=flags,
            routing_tier=tier,
            routed_themes=sorted(themes),
        )


def _load_config() -> dict:
    path = SEED_DIR / "rule_scan_config.yaml"
    if not path.exists():
        logger.warning("rule_scan_config.yaml not found, scanner disabled")
        return {"enabled": False}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("rule_scan_config", {})


_scanner_instance: RuleScanner | None = None


def get_scanner() -> RuleScanner:
    global _scanner_instance
    if _scanner_instance is None:
        _scanner_instance = RuleScanner()
    return _scanner_instance
