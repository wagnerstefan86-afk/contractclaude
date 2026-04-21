# Phase-2a-Repair — Entscheidungsmatrix

Nach dem Befüllen der drei Fixtures und dem Harness-Lauf entsteht pro
Regression-Fall ein Eintrag mit `root_cause`. Diese Tabelle führt
von der Root-Cause-Verteilung zur zu ändernden Regelstelle.

## Regelstellen

| Regelstelle | Datei | Funktion |
|---|---|---|
| A. Matcher-Signatur | `scoring/playbook_matcher.py` | `PLAYBOOK_SIGNATURES[PB-XXX]` — `negative_any`, `support_groups`, `required_groups` |
| B. Klassifikator-Pattern | `scoring/finding_classifier.py` | `_EXPLICIT_LIMITS_*`, `_EXPLICIT_LIMIT_RISK_AMPLIFIERS`, `_NEGATION_NEAR_POSITIVE` |
| C. Eskalation | `extraction/baseline_matcher.py` + `scoring/materiality_scorer.py` | `match_obligation_to_baseline` + `score_obligation_materiality` |

## Mapping root_cause → Regelstelle → konkrete Aktion

| root_cause | Regelstelle | Aktion |
|---|---|---|
| `matcher_negative_gap` | A | konkrete neue Phrase in `negative_any` der betroffenen PB-XXX-Signatur einfügen (kein Refactor) |
| `matcher_over_support` | A | Support-Gruppe eingrenzen: ambiguous Wortstämme durch spezifischere Phrasen ersetzen |
| `matcher_required_wrong` | A | Required-Group-Treffer prüfen; bei Substring-Überlapp ggf. auf mehrere Mini-Gruppen splitten |
| `classifier_positive_gap` | B | fehlende Positiv-Phrase in die passende `_EXPLICIT_LIMITS_*`-Familie nehmen |
| `classifier_amplifier_overblock` | B | betroffene Phrase aus `_EXPLICIT_LIMIT_RISK_AMPLIFIERS` entfernen oder spezifischer fassen |
| `classifier_generic_negation` | B | prüfen, ob die Klausel in `_EXPLICIT_LIMIT_ALL` fällt (läuft dann vor der generischen Negation) |
| `escalation_limits_null` | C | in `baseline_matcher` prüfen, ob text-basiertes Limit-Muster `partially_supported` statt `not_supported` setzen soll |
| `escalation_baseline_gap` | C | `_has_explicit_gap`-Test anpassen, damit generische Gap-Texte die Klassifikator-Positiv-Klassifikation nicht blockieren |

## Auswahl-Heuristik

Die 1–2 Regelstellen im Repair-Schritt werden nach **Häufigkeit der
Root-Cause-Buckets** gewählt, nicht nach Einzelfall. Regel: eine
Regelstelle wird angepasst, wenn mindestens **3 unabhängige Regression-
Fälle** dort vermutet werden.

Dominante Kombinationen und empfohlene Aktionen:

| dominante Root-Causes (≥ 3) | empfohlene Regelstellen-Änderung |
|---|---|
| nur `matcher_negative_gap` | A: Negativ-Listen mit realen Wortformen anreichern |
| `matcher_negative_gap` + `classifier_positive_gap` | A + B: Negativ-Liste **und** Positiv-Liste mit den gleichen LLM-Wortformen anreichern (oft korrelieren die beiden) |
| `classifier_generic_negation` dominant | B: `explicit_limit`-Pfad vor allgemeiner Negation halten und zusätzlich spezifische Limit-Phrasen aufnehmen |
| `classifier_amplifier_overblock` dominant | B: Risk-Amplifier-Liste kürzen, wenn sie Limit-Klauseln fälschlich vetoiert |
| `escalation_limits_null` dominant | C: leichte Textheuristik in `baseline_matcher`, die offensichtliche Begrenzungen (`\b\d+x\s+j(a|ä)hrlich\b`, `gedeckelt`, `werktage vorlauf`) als `partially_supported` einstuft — minimal-invasiv |
| `escalation_baseline_gap` dominant | C: `_has_explicit_gap` nur dann als Risk behandeln, wenn `baseline_gap_description` über den generischen „keine Begrenzungen gefunden"-Text hinausgeht |

## Regression-Gate

Nach einer Regelstellen-Änderung **muss** erfüllt sein:

1. Der bisherige deterministische Test (21/21 aus commit 261a52b)
   läuft weiterhin ohne Regression.
2. Die Live-Fixtures-GS-02 und -GS-01-Anker (harte Risiken + stabile
   Kernfindings) zeigen **keine** neuen Deltas im Harness.
3. Die Live-Fixtures-GS-03-Regression-Fälle zeigen **alle** das
   erwartete `info`-Verhalten.

Wird eines dieser Kriterien verletzt, wird die Änderung nicht
gemerged. Kein Tuning auf einen Einzelfall zulasten des
Gesamtverhaltens.
