# Matrix v1.3 → System Mapping

**Quelle:** `docs/InfoSec_ContractReview_Master_Matrix_v1_3.csv` (44 Regeln)
**Branch:** `claude/setup-infosec-contract-review-63lK9`
**Bezugs-Commit:** `95ab49b` (Matrix v1.3 Keyword-Ergänzungen)

Ein-zu-eins-Inventar aller Regeln der Matrix v1.3 mit technischem
Status und Zielstelle. Jede `rule_id` aus der CSV kommt genau einmal
vor und ist entweder **technisch übernommen** oder **deferred**
(`docs/Matrix_v1_3_Deferred_Rules.md`).

Keine Code-Änderung, nur Traceability und Summenkonsistenz.

## 1. CSV im Überblick

- **Total rule_ids in CSV:** 44
- **Unique rule_ids:** 44 (keine Duplikate)
- **Themes (6):** audit_rights (11), incident_reporting (9), governance_controls (7), bcm_resilience (6), regulatory_obligations (6), certifications (5)
- **decision_class:** high_risk (18), acceptable (15), negotiable (9), no_go (2)
- **status:** approved (42), review (2)
- **review_needed:** no (25), yes (19)
- **status × review_needed:**
  - approved / review_needed=no: 25
  - approved / review_needed=yes: 17
  - review / review_needed=yes: 2

## 2. Taxonomie

### Technischer Status

| Status | Bedeutung |
|---|---|
| `already_covered` | Risikomuster ist bereits durch bestehende Phase 2a/2b-Regeln abgedeckt. Kein Code-Change in diesem Schritt. |
| `covered_with_small_adjustment` | Minimale Keyword-Ergänzung in bestehender Pattern-Liste / Playbook-Signatur. |
| `manual_review_only` | Nicht aus Klauseltext ableitbar. Reviewer-/Legal-/Policy-Arbeit. |
| `needs_future_playbook` | Eigenes Risikomuster ohne bestehenden Playbook-Eintrag. Bewusst ausgeschlossen. |
| `not_fit_for_current_architecture` | Bräuchte neue Lens / Migration / Modell. Außerhalb Scope. |

### Zielstelle

| Zielstelle | Bedeutung |
|---|---|
| `playbook_matcher` | `scoring/playbook_matcher.py` — Signature in PLAYBOOK_SIGNATURES. |
| `finding_classifier` | `scoring/finding_classifier.py` — `_EXPLICIT_LIMITS_*`, `_POSITIVE_*`, `_REMEDIATION_*`, `_DEFENSIVE_SCOPE_LIMIT`. |
| `baseline_matcher` | `extraction/baseline_matcher.py`. |
| `finding_generator` | Cluster-/Merge-Struktur. Wird in diesem Schritt nicht angefasst. |
| `manual_only` | Reviewer-Arbeit, kein automatisches Surface. |
| `docs_only` | Dokumentiert (Deferred), kein Code-Surface in diesem Schritt. |

## 3. Vollständiges rule_id-Inventar (44/44)

### audit_rights (11)

| rule_id | status / review | technischer Status | Zielstelle | Kurzbegründung |
|---|---|---|---|---|
| AUD-001 | approved / no | `already_covered` | `playbook_matcher` | `PB-AUDIT-001.negative_any` enthält `einmal jährlich / 1x jährlich / pro kalenderjahr / annually`. |
| AUD-002 | approved / no | `already_covered` | `finding_classifier` | `_EXPLICIT_LIMITS_NOTICE` enthält `tage vorlauf / mit vorlaufzeit von / vorlaufzeit von mindestens`; `tage vorlauf` matcht `kalendertage vorlauf` per Substring. |
| AUD-003 | approved / no | `covered_with_small_adjustment` | `finding_classifier` | `_EXPLICIT_LIMITS_NOTICE` += `kalendertage vorab / werktage vorab / tage vorab`. |
| AUD-004 | approved / no | `covered_with_small_adjustment` | `finding_classifier` | `_EXPLICIT_LIMITS_COST_MODEL` += `personentage/pt inklusive`; `PB-AUDIT-003.negative_any` ebenfalls. |
| AUD-005 | approved / no | `manual_review_only` | `docs_only` | 50-PT-Schwellwert ist Vorstandspolicy, kein robustes Textsignal. |
| AUD-006 | approved / no | `manual_review_only` | `docs_only` | Regulatorischer Audit-Carveout ist Legal-Einzelfall. |
| AUD-007 | approved / no | `needs_future_playbook` | `docs_only` | Sammel-/Verbundaudit ohne Playbook-Eintrag. |
| AUD-008 | approved / no | `covered_with_small_adjustment` | `playbook_matcher` | `PB-AUDIT-002.support_groups` += `ohne mandat` als zusätzliches Risk-Support-Signal. |
| AUD-009 | approved / no | `needs_future_playbook` | `docs_only` | Pentest/Vulnerability-Scan hat keinen Playbook-Eintrag (CSV-Notiz bestätigt). |
| AUD-010 | approved / no | `covered_with_small_adjustment` | `finding_classifier` | `_DEFENSIVE_SCOPE_LIMIT` += `unmittelbarer zusammenhang`-Varianten. |
| AUD-011 | approved / no | `covered_with_small_adjustment` | `playbook_matcher` | `PB-AUDIT-002.negative_any` += `schriftliches mandat / wirtschaftsprüfer / zur verschwiegenheit verpflichtet`-Varianten (positive Variante zu AUD-008). |

### incident_reporting (9)

| rule_id | status / review | technischer Status | Zielstelle | Kurzbegründung |
|---|---|---|---|---|
| INC-001 | approved / no | `already_covered` | `playbook_matcher` | `PB-INC-002` matcht `meldung/meldepflicht` + `jedes/alle/ohne schwellenwert`. |
| INC-002 | approved / no | `already_covered` | `playbook_matcher` | `PB-INC-003` matcht `meldepflicht` + `aufsichtsbehörde/regulatorisch`. |
| INC-003 | approved / no | `already_covered` | `playbook_matcher` | `PB-INC-001` matcht tight-time-Meldefristen (<2h / Minuten / unverzüglich). |
| INC-004 | approved / no | `already_covered` | `finding_classifier` | `_EXPLICIT_LIMITS_CONSENT` / Default-View behandeln Vorab-Abstimmung als Standardklausel. |
| INC-005 | approved / no | `already_covered` | `finding_classifier` | `_REMEDIATION_PATTERN` + `_REMEDIATION_TIMEBOX` matchen `abschlussbericht / innerhalb X werktagen` (GS-01-Fixture bestätigt). |
| INC-006 | review / yes | `manual_review_only` | `docs_only` | `status=review`. SaaS-Statuspage-Thematik, bleibt bis Matrix-Update außen vor. |
| INC-007 | approved / no | `needs_future_playbook` | `docs_only` | SIEM/SOC-spezifisches Muster ohne Playbook-Eintrag. |
| INC-008 | approved / no | `manual_review_only` | `docs_only` | Kausalitäts-/Einflussbereichsprüfung nicht aus Text ableitbar. |
| INC-009 | approved / no | `manual_review_only` | `docs_only` | Scope-Diskriminierung „alle Informationen" vs. „insoweit erforderlich" braucht Kontext. |

### certifications (5)

| rule_id | status / review | technischer Status | Zielstelle | Kurzbegründung |
|---|---|---|---|---|
| CERT-001 | approved / no | `covered_with_small_adjustment` | `finding_classifier` | `_POSITIVE_CERTIFICATION` += `iso 27005`. |
| CERT-002 | approved / no | `covered_with_small_adjustment` | `finding_classifier` | `_POSITIVE_CERTIFICATION` += `isae 3402 / isae3402`. |
| CERT-003 | approved / no | `covered_with_small_adjustment` | `finding_classifier` | `_POSITIVE_CERTIFICATION` += `en 50600 / vk3 / rechenzentrumszertifizierung`. |
| CERT-004 | review / yes | `manual_review_only` | `docs_only` | `status=review`. NDA-/Einzelfallfreigabe — Reviewer. |
| CERT-005 | approved / no | `manual_review_only` | `docs_only` | „Sämtliche Policies auf Verlangen" vs. „SoA-Extrakt" — Kontext nötig. |

### governance_controls (7)

| rule_id | status / review | technischer Status | Zielstelle | Kurzbegründung |
|---|---|---|---|---|
| GOV-001 | approved / no | `covered_with_small_adjustment` | `finding_classifier` | `_POSITIVE_CERTIFICATION` += `is-risikomanagement / ismssystem`. |
| GOV-002 | approved / yes | `not_fit_for_current_architecture` | `docs_only` | Generisches IKS/ERM ohne InfoSec-Lens — würde eigene Governance-Lens erfordern. |
| GOV-003 | approved / yes | `not_fit_for_current_architecture` | `docs_only` | Vertragsspezifisches IKS ohne Lens-Fit — Usecase-Policy. |
| GOV-004 | approved / yes | `not_fit_for_current_architecture` | `docs_only` | Wirksamkeitsnachweis sämtlicher Kontrollen — ohne Lens nicht robust. |
| GOV-005 | approved / yes | `manual_review_only` | `docs_only` | Gemeinsame Risikobewertung ist Consulting-Delivery-Entscheidung. |
| GOV-006 | approved / yes | `not_fit_for_current_architecture` | `docs_only` | Zentrale Risikomanagement-Integration benötigt Governance-Lens. |
| GOV-007 | approved / no | `manual_review_only` | `docs_only` | Eignungsleihe mit Back-to-back-Kopplung ist Legal-Thema. |

### bcm_resilience (6)

| rule_id | status / review | technischer Status | Zielstelle | Kurzbegründung |
|---|---|---|---|---|
| BCM-001 | approved / yes | `manual_review_only` | `docs_only` | Provider-BCMS-Baseline als Nachweis-/Vertriebsentscheidung. |
| BCM-002 | approved / yes | `manual_review_only` | `docs_only` | Scope-Abgrenzung gegen Kundenumgebung, kontextsensitiv. |
| BCM-003 | approved / yes | `manual_review_only` | `docs_only` | Kundenspezifisches BCM — Solution-Design-Policy. |
| BCM-004 | approved / yes | `already_covered` | `playbook_matcher` | `PB-SLA-003` matcht „Aussetzung ausgeschlossen / gelten uneingeschränkt" (Phase 2a/2b). |
| BCM-005 | approved / yes | `already_covered` | `playbook_matcher` | `PB-SLA-001` matcht „Wartungsfenster nicht herausgerechnet" (Phase 2b). |
| BCM-006 | approved / yes | `manual_review_only` | `docs_only` | Notfallmitwirkung im Einfluss-/Verantwortungsbereich — Einzelfall. |

### regulatory_obligations (6)

| rule_id | status / review | technischer Status | Zielstelle | Kurzbegründung |
|---|---|---|---|---|
| REG-001 | approved / yes | `manual_review_only` | `docs_only` | Pauschale regulatorische Übernahme ist no_go-Policy, Legal-Standardposition. |
| REG-002 | approved / yes | `not_fit_for_current_architecture` | `docs_only` | DORA-Artikelbezug ohne Regulatorik-Lens. |
| REG-003 | approved / yes | `not_fit_for_current_architecture` | `docs_only` | NIS2-Adressatenbestimmung ohne Regulatorik-Lens. |
| REG-004 | approved / yes | `not_fit_for_current_architecture` | `docs_only` | KRITIS-Betreiberpflichten — Legal-Standardposition. |
| REG-005 | approved / yes | `not_fit_for_current_architecture` | `docs_only` | MaRisk AT 9 — Legal-Einzelfall. |
| REG-006 | approved / yes | `not_fit_for_current_architecture` | `docs_only` | Regulatorische Sonderleistungen — Consulting-Kontext. |

## 4. Summen (kanonisch)

| Gruppe | n |
|---|---|
| **Total rules in CSV** | **44** |
| Technisch übernommen (already_covered + covered_with_small_adjustment) | **18** |
| davon `already_covered` | 9 |
| davon `covered_with_small_adjustment` | 9 |
| **Deferred (→ Matrix_v1_3_Deferred_Rules.md)** | **26** |
| davon `manual_review_only` | 10 |
| davon `needs_future_playbook` | 3 |
| davon `needs_policy_decision` | 3 |
| davon `not_fit_for_current_architecture` | 9 |
| davon `outside_current_scope` | 1 |

Kontrolle: 9 + 9 + 10 + 3 + 3 + 9 + 1 = **44** ✓

### Zielstellen-Verteilung (nur technisch übernommen, 18)

| Zielstelle | n | rule_ids |
|---|---|---|
| `playbook_matcher` | 7 | AUD-001, AUD-008, AUD-011, INC-001, INC-002, INC-003, BCM-004, BCM-005 (→ 8) |
| `finding_classifier` | 11 | AUD-002, AUD-003, AUD-004, AUD-010, INC-004, INC-005, CERT-001, CERT-002, CERT-003, GOV-001 (→ 10) |

Hinweis: AUD-008 und AUD-011 ändern beide `PB-AUDIT-002` (matcher),
AUD-004 ändert primär `finding_classifier` und sekundär
`PB-AUDIT-003.negative_any`. In obiger Zuordnung zählt die **primäre**
Zielstelle. Tatsächliche Verteilung:

- `playbook_matcher`: 8 (AUD-001, AUD-008, AUD-011, INC-001, INC-002, INC-003, BCM-004, BCM-005)
- `finding_classifier`: 10 (AUD-002, AUD-003, AUD-004, AUD-010, INC-004, INC-005, CERT-001, CERT-002, CERT-003, GOV-001)
- Summe: 18 ✓

## 5. Kontrollsektion

| Check | Ergebnis |
|---|---|
| total rules in csv | **44** |
| total rules mapped | **44** |
| duplicate rule_ids found? | **no** |
| missing rule_ids? | **none** |
| extra rule_ids not in csv? | **none** |
| adopted + deferred == total | 18 + 26 = **44** ✓ |
| overlap adopted ∩ deferred | **{}** |
