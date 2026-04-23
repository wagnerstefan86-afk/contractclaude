# InfoSec Contract Review – Phase 2a / 2b Freeze

**Datum:** 23.04.2026
**Branch:** `claude/setup-infosec-contract-review-63lK9`
**Freeze-Commit:** `42db6fd` (Phase 2b matcher extensions)
**Vorläufer-Stand:** siehe `InfoSec_ContractReview_PoC_Baseline.md` (21.04.2026)

Kurze, review-taugliche Zusammenfassung des Scorings-Stands nach Phase 2a
(Calibration) und Phase 2b (Missing-Playbook-Wiring). Dieses Dokument ist
der Referenzpunkt für die nächste Iteration; Baseline-Dokument bleibt als
Historie.

---

## 1. Zielbild des Freeze-Stands

- **GS-03 (milder Print-Vertrag)**: ruhig genug — nur echte materielle
  Risikokerne sichtbar, Standardklauseln (Frequenz-Cap, Notice-Period,
  Cost-Model, Scope-Limit, Priority-Matrix, DR-Suspension) sind
  informational und bleiben als Evidenz erhalten.
- **GS-02 (harter Hosting-Vertrag)**: alle harten SLA-Kerne sichtbar und
  an Playbook gebunden, keine Severity-Flut (keine CRITICAL-Inflation
  mehr), ISO-Zertifizierung und moderate Priority-Matrix-Werte bleiben
  korrekt informational.
- **GS-01 (Kalibrierungsvertrag)**: stabile Kernfindings, keine Regression
  gegenüber dem PoC-Baseline-Stand.

Als „belastbarer Demo-/Baseline-Stand" gilt: die Ampel-Logik
(Risk vs. Info) entsteht wiederholbar aus Vertragstext + deterministischen
Regeln + den 11 bestehenden Playbook-Einträgen. Keine neuen Playbooks,
keine neuen Lenses, keine Modelländerungen.

## 2. Was Phase 2a behoben hat

**Classifier (`scoring/finding_classifier.py`)** — zusätzliche
`_EXPLICIT_LIMITS_*`-Patterns, damit Standardformulierungen nicht mehr als
Risk surfacen:

- `COST_MODEL`: „nach tatsächlichem Aufwand", „vereinbarten Tagessätze"
- `MAINTENANCE_EXCLUDED`: „aus der Berechnung der Verfügbarkeit
  herausgerechnet" (positive Form); dazu `nicht aus der berechnung` als
  Risk-Amplifier, damit die negierte Form NICHT fälschlich info wird
- `PENALTY_CAP`: „auf maximal" (für „Gutschrift auf maximal 10 %")
- `NOTICE`: „einer Vorlaufzeit von", „Vorlaufzeit von mindestens"
- `TIMEWINDOW`: „während der Servicezeiten" + Varianten; Mirror in
  `_EXPLICIT_LIMIT_RISK_AMPLIFIERS` für „außerhalb der Servicezeiten"
- `DEFENSIVE_SCOPE_LIMIT`: „erforderlichen Unterlagen/Auskünfte",
  „nur aus wichtigem Grund verweigern"

**Generator (`scoring/finding_generator.py`)**:

- **Pass-2-Guard**: eine Komponente, die solo rein informational ist,
  wird nicht mehr über Playbook-ID in einen Risk-Cluster gemerged.
- **Mixed-Cluster-Split**: wenn ein Risk-Cluster gemischte Mitglieder
  enthält, werden solo-informational Mitglieder als eigene Info-Findings
  aus dem Cluster ausgelagert. Evidenz bleibt erhalten.
- **Severity-Log**: pro Finding eine `logger.info`-Zeile mit Theme,
  Playbook, Severity, Materiality, Mitgliederzahl, Classifier-Reason.

**Classifier-Architektur (`scoring/finding_classifier.py`)**:

- `_has_missing_safeguard_for_group` gesplittet in „strong" (direkte
  `ms.obligation_id`-Bindung) vs. „weak" (Lens-Ebene).
- `classify_group` ist in Tiers umsortiert: starke Signale
  (Playbook-Match, obligation-linked MS, contradicts) gewinnen immer;
  danach Positive-Text-Check; Lens-level MS und baseline_gap feuern
  nur, wenn der Text selbst nicht klar positiv ist. Das verhindert die
  beobachtete GS-03-Regression, bei der eine einzige Lens-Ebenen-MS
  alle Audit-Obligations auf Risk zurückgeflippt hat.

**Matcher (`scoring/playbook_matcher.py`)**:

- `PB-AUDIT-001.negative_any`: „einer Vorlaufzeit von", „Vorlaufzeit von
  mindestens" (blockt die 20-Werktage-Klausel).
- `PB-SLA-003.required_groups[2]`: „gelten uneingeschränkt auch während",
  „uneingeschränkt während" — GS-02-Phrasierung.
- `PB-SLA-005.support_groups`: „besteht nicht" — für „Eine Deckelung
  der Vertragsstrafe besteht nicht.".

**Materiality (`scoring/materiality_scorer.py`)**:

- Rule 3 (MissingSafeguards) wird jetzt pro Obligation/Lens gefiltert.
  Vorher führte 3+ MS **irgendwo im Run** zu CRITICAL auf **jeder**
  Obligation — das erklärt die GS-02-22.04-Kritisch/Kritisch-Flut.

## 3. Was Phase 2b ergänzt hat

Drei gezielte Keyword-Erweiterungen an bestehenden Playbook-Signaturen.
Keine neuen Playbook-Einträge.

| Klausel | Vorher | Nachher |
|---|---|---|
| „Wartungsfenster werden nicht aus der Berechnung herausgerechnet" (GS-01, GS-02) | HIGH ohne PB | HIGH **PB-SLA-001** |
| „Eine Aussetzung der SLAs ist ausgeschlossen." (GS-02) | HIGH ohne PB | HIGH **PB-SLA-003** (Cluster-Merge mit „uneingeschränkt") |
| „RPO null (0) Minuten" (GS-02) | HIGH ohne PB | HIGH **PB-SLA-004** (Cluster-Merge mit P1/RTO/24/7) |

Details:
- `PB-SLA-001.required_groups[0]` += `berechnung`; `support_groups[0]` +=
  `nicht herausgerechnet`, `nicht aus der berechnung`. Positive Form
  („werden herausgerechnet" ohne `nicht`) matcht weiterhin NICHT.
- `PB-SLA-003.required_groups[1]` += `aussetzung`, `suspension`;
  `required_groups[2]` += `ist ausgeschlossen`, `sind ausgeschlossen`,
  `ist unzulässig`, `sind unzulässig`.
- `PB-SLA-004.required_groups[0]` += `rpo`, `rto`, `recovery point`,
  `recovery time`, `datenverlusttoleranz`; `required_groups[1]` +=
  ` 0 minuten` (mit führendem Space gegen Substring-Kollision mit
  "10 minuten" etc.), `null 0`, `null minuten`, `zero minutes`.

## 4. Bewusst offene Themen (kein Fix im Freeze)

- **GS-03 „99,5 % Verfügbarkeit"** bleibt als sichtbares Risk-Finding
  ohne Playbook-Match. Das ist keine Limit-/Informationsklausel, sondern
  das SLA-Ziel selbst. Ob 99,5 % „zu niedrig" ist, hängt am Baseline
  (Print Services vs. Core Hosting) und gehört in die Baseline-Matcher-
  bzw. Policy-Diskussion, nicht in die Classifier-Kalibrierung.
- **Einzelne no-PB-Findings** bleiben sichtbar, weil sie echte Risk-
  Kerne sind und die bestehenden 11 Playbook-Einträge sie nicht
  abdecken — ein Fix erforderte neue Playbook-Einträge und damit
  Scope-Expansion. Aktuell:
  - GS-01: „Auditunterstützung aktiv und ohne gesonderte Vergütung"
  - GS-02: „Soweit der Auftragnehmer eigene Meldepflichten hat,
    stimmt er die Meldung vorab mit dem Auftraggeber ab"
  - GS-03: „5 % Gutschrift je 0,1 Prozentpunkte Unterschreitung"
- **Keine weitere Severity-/Materiality-Kalibrierung**. Rule-3-Scoping
  ist die einzige Materiality-Änderung in Phase 2a/2b. Die Base-Regeln
  (baseline_match_status=not_supported → HIGH, limits_null → HIGH,
  contradicts → HIGH, lens-scoped MS → HIGH/CRITICAL) bleiben
  unverändert.
- **PB-SLA-005 als Cluster-Leader**: „Deckelung besteht nicht" matcht
  dank Phase 2a PB-SLA-005, landet aber im PB-SLA-002-Cluster, weil die
  SLA-99,99 %-Obligation das erste Playbook im Component war. Die
  Evidenz ist erhalten, aber die dominante Title-Auswahl ist nicht
  optimal — bewusst nicht geändert, weil das Cluster-Leader-Ranking
  ein breiterer Umbau wäre.

## 5. Warum dieser Stand belastbar ist

- **Harness + Live-Run**: alle drei 22.04-Fixtures im Harness 22/22,
  21/21, 16/16 ✓; im Live-Pipeline-Run (lokales Postgres, rekonstruierte
  Relations, injizierte lens-level MissingSafeguards) sind die Zählungen
  reproduzierbar und stabil.
- **Explizite Regressions-Anker**: „Wartungsfenster NICHT herausgerechnet"
  bleibt risk (Amplifier); „werden herausgerechnet" (positive Form)
  bleibt info. PB-SLA-003 matcht „gelten auch während" UND „gelten
  uneingeschränkt auch während". P1 mit tight-time bleibt risk,
  P2/P3/P4-Standardzeiten bleiben info.
- **Deterministisch und auditfähig**: alle Änderungen in Phase 2a/2b
  sind Keyword-Listen oder Reihenfolge-Änderungen in Python-Data
  (git-diffable). Keine Modellparameter, keine Gewichte, keine LLM-
  Aufrufe. Reviewer kann jeden Pattern-Eintrag nachvollziehen.
- **Nichts Versprochenes aus dem Baseline-Dokument wurde zurückgenommen**.
  Die Limitierungen in `InfoSec_ContractReview_PoC_Baseline.md` §3 und
  §8 gelten weiter.

## 6. Referenzartefakte

- `scripts/run_fixture_live.py` — Live-Pipeline-Run gegen eine
  Fixture-Datei in einer lokalen DB. Nur Tests.
- `scripts/diag_severity.py` — Read-only Pro-Finding-Severity/
  Materiality-Diagnostik für einen gegebenen `analysis_runs.id`.
- `eval/gold_set/fixtures/GS-0{1,2,3}-2026-04-22.yaml` —
  22.04-Live-Fixtures mit Reviewer-Annotationen (expected_outcome,
  root_cause, regression_case, hypothesis).
- `eval/gold_set/fixtures/run_fixture_tests.py` — Harness.

## 7. Relevante Commits in Phase 2a / 2b

| Commit | Beschreibung |
|---|---|
| `9645505` | Phase 2a-repair: classifier/matcher/generator keyword additions |
| `d1b84fe` | 22.04-Fixture-Annotationen |
| `7cd346a` | Phase 2a-live-reconcile: Cluster-Split + PB-SLA-003 + scoped materiality |
| `53e5517` | Phase 2a.2: Servicezeiten-TIMEWINDOW + Live-Run-Harness |
| `c09c92b` | Mini-2a.3: GS-03 Audit-Cleanup (Erforderliche Unterlagen + wichtiger Grund) |
| `acd73a8` | Mini-2a.4: two-tier MissingSafeguard-Signal |
| `a76c38a` | Phase 2a complete |
| `42db6fd` | Phase 2b: PB-SLA-001 / 003 / 004 Keyword-Erweiterungen |
