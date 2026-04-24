# Matrix v1.3 → System Mapping

**Quelle:** `docs/InfoSec_ContractReview_Master_Matrix_v1_3.csv`
**Branch:** `claude/setup-infosec-contract-review-63lK9`
**Bezugssystem-Stand:** Phase 2a/2b Freeze (`4ea06b6` + `42db6fd`)

Analyse der Matrix-v1.3-Regeln gegen die bestehende PoC-Architektur.
Nur Regeln mit `status=approved` UND `review_needed=no` kommen als
**automatische** Ableitung in Frage. Alle übrigen Regeln gehen nach
`docs/Matrix_v1_3_Deferred_Rules.md`.

## 1. Kurzbeschreibung der CSV

Semikolon-separierter Export des final abgestimmten
Matrix-Tabs. 44 Regeln über sechs Themen. Pro Regel sind
`clause_pattern`, `evidence_markers` (Risiko-Trigger), `safe_markers`
(positive/begrenzende Klauseln), `standard_position`, `scope_notes`,
`playbook_id` (soweit vorhanden) und Status/Review-Flag ausgewiesen.

## 2. Größe und Verteilung

### Anzahl

| Gruppe | n |
|---|---|
| Gesamt | 44 |
| `approved` + `review_needed=no` (Automatisierungskandidaten) | 25 |
| `approved` + `review_needed=yes` (nicht blind automatisieren) | 17 |
| `review` (nur dokumentieren) | 2 |

### Nach Theme

| Theme | n |
|---|---|
| audit_rights | 11 |
| incident_reporting | 9 |
| governance_controls | 7 |
| bcm_resilience | 6 |
| regulatory_obligations | 6 |
| certifications | 5 |

### Nach decision_class

| decision_class | n |
|---|---|
| high_risk | 18 |
| acceptable | 15 |
| negotiable | 9 |
| no_go | 2 |

### Playbook-Abdeckung

9 von 44 Regeln verweisen auf einen bestehenden Playbook-Eintrag
(PB-AUDIT-001 ×3, PB-AUDIT-002 ×2, PB-AUDIT-003 ×1, PB-INC-002 ×1,
PB-INC-003 ×1, PB-SLA-001 ×1, PB-SLA-003 ×1). Die übrigen 35 Regeln
haben keine Playbook-Zuordnung — davon sind viele absichtlich
Policy-/Kontext-Themen, die **ohne neuen Playbook-Eintrag** nicht
automatisiert werden können.

## 3. Verwendete technische Zielstellen

- **playbook_matcher** — `infosec_contract_review/scoring/playbook_matcher.py`, Signaturen `required_groups` / `support_groups` / `negative_any` je Playbook-ID.
- **finding_classifier** — `infosec_contract_review/scoring/finding_classifier.py`, Pattern-Listen `_EXPLICIT_LIMITS_*`, `_POSITIVE_CERTIFICATION`, `_REMEDIATION_*`, `_DEFENSIVE_SCOPE_LIMIT`, `_EXPLICIT_LIMIT_RISK_AMPLIFIERS`.
- **baseline_matcher** — `infosec_contract_review/extraction/baseline_matcher.py`. Wird in Phase 2a/2b nicht mehr kalibriert; Baseline-Signale landen im Downstream-Classifier.
- **finding_generator** — nur struktureller Kram (Cluster-Merge, Severity-Log). Keine neuen Regelquellen.
- **manual_only** — nicht technisch abbildbar, Reviewer-Hinweis nötig.
- **docs_only** — dokumentiert, Kategorie `future_playbook` / `future_lens` / `needs_policy_decision`.

## 4. Status-Kategorien (interne Taxonomie)

| Kategorie | Bedeutung |
|---|---|
| **already_covered** | Keine Code-Änderung nötig. Bestehende Pattern greifen. |
| **covered_with_small_adjustment** | Minimal-invasive Keyword-Ergänzung in bestehender Pattern-Liste. Keine neue Struktur. |
| **manual_review_only** | Hängt an Policy-Zahlen / Legal-Kontext / Schwellwertfragen. Nicht automatisierbar. |
| **needs_future_playbook** | Eigene Risiko-Kategorie ohne bestehenden Playbook-Eintrag. Bewusst ausgeschlossen — kein neuer Playbook. |
| **not_fit_for_current_architecture** | Bräuchte neue Lens / Migration / Modell. Außerhalb Scope. |

## 5. Regelinventar

### audit_rights (11)

| rule_id | decision_class | PB | Kategorie | Zielstelle | Begründung |
|---|---|---|---|---|---|
| AUD-001 | acceptable | PB-AUDIT-001 | already_covered | playbook_matcher + finding_classifier | `einmal jährlich` / `pro kalenderjahr` / `1x jährlich` sind in `_EXPLICIT_LIMITS_FREQUENCY` und `PB-AUDIT-001.negative_any` vorhanden. |
| AUD-002 | acceptable | PB-AUDIT-001 | already_covered | finding_classifier | `mit vorlaufzeit von` / `vorlaufzeit von mindestens` / `tage vorlauf` in `_EXPLICIT_LIMITS_NOTICE`; `tage vorlauf` matcht auch `kalendertage vorlauf` per Substring. |
| AUD-003 | acceptable | PB-AUDIT-001 | covered_with_small_adjustment | finding_classifier | `kalendertage vorab`, `werktage vorab` fehlen in `_EXPLICIT_LIMITS_NOTICE`. Ergänzen (Audit-Fragebogen-Vorbereitung). |
| AUD-004 | acceptable | PB-AUDIT-003 | covered_with_small_adjustment | finding_classifier + playbook_matcher | Cost-Model-Pattern ist breit (`nach tagessatz`, `nach tatsächlichem aufwand`), aber `personentage inklusive` / `pt inklusive` als spezifische Formulierung nicht enthalten. |
| AUD-005 | acceptable | — | manual_review_only | docs_only | 50-PT-Schwellwert ist Vorstandspolicy, keine aus Text ableitbare Limit-/Risiko-Formulierung. |
| AUD-006 | negotiable | — | manual_review_only | docs_only | Regulatorischer Carveout — Legal-Entscheidung im Einzelfall. |
| AUD-007 | high_risk | — | needs_future_playbook | docs_only | „Sammelaudit / Verbundaudit" ist eigenes Risiko-Muster ohne Playbook-Eintrag. |
| AUD-008 | high_risk | PB-AUDIT-002 | already_covered | playbook_matcher | `endkunde/dritte` + `jederzeit/ohne ankündigung` matcht. Optional: `ohne mandat` als weiterer Support-Marker (klein). |
| AUD-009 | high_risk | — | needs_future_playbook | docs_only | Pentest/Vulnerability-Scan — eigenes Muster; CSV-Notiz bestätigt „Kein eigener Playbook-Eintrag vorhanden - Lücke für spätere Pipeline-Ableitung." |
| AUD-010 | acceptable | — | already_covered | finding_classifier | `auf den vertragsgegenstand` in `_DEFENSIVE_SCOPE_LIMIT`. Optional: `unmittelbarer zusammenhang` für Vollständigkeit. |
| AUD-011 | acceptable | PB-AUDIT-002 | covered_with_small_adjustment | playbook_matcher | Positive Variante zu AUD-008. `PB-AUDIT-002.negative_any` hat `mit zustimmung/genehmigung` — fehlen `schriftliches mandat`, `wirtschaftsprüfer`, `zur verschwiegenheit verpflichtet`. Ergänzen, damit kontrollierte Drittaudits nicht fälschlich als Risk eskalieren. |

### incident_reporting (9)

| rule_id | decision_class | PB | Kategorie | Zielstelle | Begründung |
|---|---|---|---|---|---|
| INC-001 | high_risk | PB-INC-002 | already_covered | playbook_matcher | `PB-INC-002` fordert `meldung/meldepflicht` + `jedes/alle/ohne schwellenwert`. Near-Misses / Verdachtsfälle sind im `required_groups[1]` via `jedes`/`alle` erfasst. |
| INC-002 | high_risk | PB-INC-003 | already_covered | playbook_matcher | PB-INC-003 matcht `meldepflicht` + `aufsichtsbehörde/regulatorisch`. Safe-Form „verbleibt beim auftraggeber" bleibt im info-Cluster / baseline_gap — ok. |
| INC-003 | high_risk | — | already_covered | playbook_matcher | Tight-Time-Meldefristen (<2h / Minuten) über PB-INC-001 bereits abgedeckt. CSV-Regel ist Policy-Standardposition (72h nach Triage) — das ist gut gematchte Gegenposition, Risiko-Pattern steht im Matcher. |
| INC-004 | acceptable | — | already_covered | finding_classifier | „stimmt meldung vorab ab" passt in die bestehende Consent-Logik und/oder wird in der Default-View bereits nicht dominant. Keine neue Regel. |
| INC-005 | acceptable | — | already_covered | finding_classifier | Abschlussbericht/RCA ist Positiv-Commitment. `_REMEDIATION_TIMEBOX` + `_REMEDIATION_PATTERN` matchen bereits: GS-01-Fixture 22.04 zeigt `b7e69499` (Abschlussbericht 5 Werktage) korrekt als info. |
| INC-007 | high_risk | — | needs_future_playbook | docs_only | SIEM/SOC-spezifischer Service — eigenes Risiko-Muster, CSV-Kontext ist `service_context=security_service`. Kein Playbook-Eintrag, kein Lens-Spezifikum. |
| INC-008 | high_risk | — | manual_review_only | docs_only | Kausalitäts-/Einflussbereichsprüfung zentral — aus Text allein nicht robust ableitbar. |
| INC-009 | high_risk | — | manual_review_only | docs_only | „alle Informationen" / „soweit erforderlich" ist Formulierungsfrage mit rechtlicher Bewertung. |

### certifications (5)

| rule_id | decision_class | PB | Kategorie | Zielstelle | Begründung |
|---|---|---|---|---|---|
| CERT-001 | acceptable | — | already_covered | finding_classifier | `iso 27001`, `iso 22301`, `iso 27017`, `iso 27018` sind in `_POSITIVE_CERTIFICATION`. `iso 27005` fehlt — kleine Ergänzung. |
| CERT-002 | acceptable | — | covered_with_small_adjustment | finding_classifier | `isae 3402` fehlt in `_POSITIVE_CERTIFICATION`. Ergänzen, damit ISAE-Nachweis-Klauseln als positive Evidenz klassifiziert werden. |
| CERT-003 | acceptable | — | covered_with_small_adjustment | finding_classifier | `en 50600` / `vk3` / `rechenzentrumszertifizierung` fehlen in `_POSITIVE_CERTIFICATION`. Ergänzen. |
| CERT-004 | negotiable | — | — | docs_only | `status=review`, `review_needed=yes` — nicht in diesem Schritt. |
| CERT-005 | high_risk | — | manual_review_only | docs_only | „sämtliche Policies/Risikoanalysen auf Verlangen" vs. „SoA-Extrakt/Exec-Summary" — Scope-Diskriminierung benötigt Kontext. |

### governance_controls (7)

| rule_id | decision_class | PB | Kategorie | Zielstelle | Begründung |
|---|---|---|---|---|---|
| GOV-001 | acceptable | — | covered_with_small_adjustment | finding_classifier | „IS-Risikomanagement" / „ISMS" / „ISO 27005" sollen als positive Belegformen markiert sein. Bisher nur allgemeines `nachweis`/`iso 27001` im Cert-Katalog. |
| GOV-002..006 | — | — | — | docs_only | Alle `review_needed=yes` — nicht blind automatisieren. |
| GOV-007 | acceptable | — | manual_review_only | docs_only | Eignungsleihe mit Back-to-back-Kopplung — Legal/Compliance-Flag. Aus Text allein nicht klar abzuleiten. |

### bcm_resilience (6)

| rule_id | decision_class | PB | Kategorie | Zielstelle | Begründung |
|---|---|---|---|---|---|
| BCM-004 | no_go | PB-SLA-003 | already_covered | playbook_matcher | Phase-2b wire-up deckt PB-SLA-003 für „Aussetzung ausgeschlossen" und „gelten uneingeschränkt" ab. |
| BCM-005 | high_risk | PB-SLA-001 | already_covered | playbook_matcher | Phase-2b wire-up deckt PB-SLA-001 für „nicht herausgerechnet" ab. |
| BCM-001..003, BCM-006 | — | — | — | docs_only | Alle `review_needed=yes`. Leitplanke: BCM nur sehr vorsichtig anfassen. |

### regulatory_obligations (6)

Alle sechs Regeln haben `review_needed=yes`. Die Leitplanke fordert:
„governance_controls und regulatory_obligations nicht gewaltsam in
bestehende Lenses pressen". Entsprechend **keine** automatische
Ableitung — siehe Deferred-Doc.

## 6. Implementierungs-Entscheidung je Regel

**Wird in diesem Schritt implementiert** (nur `approved`+`review=no` +
sauber passend):

- AUD-001 — schon abgedeckt, Explizit-Check in Mapping-Doc
- AUD-002 — schon abgedeckt, Explizit-Check
- AUD-003 — `_EXPLICIT_LIMITS_NOTICE` erhält `kalendertage vorab`, `werktage vorab`
- AUD-004 — `_EXPLICIT_LIMITS_COST_MODEL` erhält `personentage inklusive`, `pt inklusive`
- AUD-008 — `PB-AUDIT-002.support_groups` erhält `ohne mandat`
- AUD-010 — `_DEFENSIVE_SCOPE_LIMIT` erhält `unmittelbarer zusammenhang`
- AUD-011 — `PB-AUDIT-002.negative_any` erhält `schriftliches mandat`, `wirtschaftsprüfer`, `zur verschwiegenheit verpflichtet`
- CERT-001 — `_POSITIVE_CERTIFICATION` erhält `iso 27005`
- CERT-002 — `_POSITIVE_CERTIFICATION` erhält `isae 3402`
- CERT-003 — `_POSITIVE_CERTIFICATION` erhält `en 50600`, `vk3`, `rechenzentrumszertifizierung`
- GOV-001 — `_POSITIVE_CERTIFICATION` erhält `is-risikomanagement`, `ismssystem`

**Nicht in diesem Schritt** (→ Deferred-Doc):

- AUD-005, AUD-006, AUD-007, AUD-009
- INC-007, INC-008, INC-009
- CERT-005, GOV-007
- Alle BCM (außer 004/005, die Phase 2b schon abdeckt)
- Alle GOV mit `review_needed=yes` (002–006)
- Alle REG (001–006)
- INC-006, CERT-004 (`status=review`)
- INC-001, INC-002, INC-003, INC-004, INC-005 sind bereits durch
  bestehenden Matcher/Classifier abgedeckt; keine zusätzliche
  Code-Änderung, Referenz im Mapping.

## 7. Begründungen im Detail

Die vollständigen Begründungen je deferter Regel stehen in
`docs/Matrix_v1_3_Deferred_Rules.md`.

Für jede implementierte Keyword-Ergänzung gilt:

1. Die Ergänzung steht im Einklang mit dem `safe_markers`- bzw.
   `evidence_markers`-Feld der Regel.
2. Kein neues Pattern-Feld, keine neue Kategorie — nur Einträge in
   bestehende Tupel.
3. Regressions-Test über Harness + Live-Pipeline-Smoke auf den drei
   22.04-Fixtures plus lens-MS-Injection (Realitätsbedingung).
