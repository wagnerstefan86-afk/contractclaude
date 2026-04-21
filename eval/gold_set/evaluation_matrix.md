# Bewertungsmatrix

Eine Zeile pro **Finding × Run × Vertrag**. Die Matrix wird als CSV
gepflegt (`evaluation_matrix_template.csv`) und wächst pro Gold-Set-Vertrag.
Keine eigene Datenbank, keine zusätzliche Tooling-Schicht — flache Datei,
die sich in Git versionieren lässt.

## Spaltensemantik

| Spalte | Typ | Definition |
|---|---|---|
| `contract_id` | string | Stabile ID des Gold-Set-Vertrags, z. B. `GS-01-kalib` |
| `run_id` | string | `analysis_runs.id` aus der DB (UUID) |
| `git_sha` | string | Kurz-SHA des Code-Stands beim Run (`git rev-parse --short HEAD`) |
| `finding_id` | string | `findings.id` aus der DB (UUID) |
| `finding_title` | string | Titel wie in UI / Excel |
| `theme` | string | Theme-Enum-Wert, z. B. `audit_rights`, `sla_feasibility` |
| `lens` | string | Extraktions-Lens, z. B. `LENS-AUDIT`, `LENS-SLA` |
| `severity` | string | `info` / `low` / `medium` / `high` / `critical` |
| `materiality` | string | `low` / `medium` / `high` / `critical` |
| `playbook_id` | string | `PB-AUDIT-001` etc., leer wenn keine Zuordnung |
| `expected_outcome` | enum | `risk` / `info` / `suppress` — die Reviewer-Erwartung |
| `actual_outcome` | enum | `risk` / `info` — was das System produziert hat |
| `error_class` | enum | siehe `error_classes.md`, `ok` wenn stimmig |
| `keep_merge_split_decision` | enum | `keep` / `split` / `merge_with:<finding_id>` |
| `evidence_ok` | enum | `yes` / `no` / `partial` — passt die Evidenz zum Titel? |
| `reviewer_visible` | enum | `yes` / `no` — steht das Finding in der UI-Default-Ansicht? |
| `comment` | string | Freitext, max. 1–2 Sätze |

### Enums

- `expected_outcome`:
  - `risk`: Finding soll in der Default-Ansicht stehen und vom Reviewer
    behandelt werden.
  - `info`: risikoreduzierend, standardnah, positiv — gehört in den
    Info-Bucket.
  - `suppress`: hätte gar nicht als Finding entstehen sollen
    (Extraktions-Noise).

- `actual_outcome`:
  - `risk`: `severity` != `info`.
  - `info`: `severity` == `info` (oder Titel mit `[Informativ]` / `[Cross-Theme]`-Prefix).

- `keep_merge_split_decision`:
  - `keep`: Finding bleibt, wie es ist.
  - `split`: Finding sollte in zwei oder mehr getrennte Findings
    aufgeteilt werden (Multi-Risk / `over_aggregation_multi_risk_clause`).
  - `merge_with:<finding_id>`: Finding sollte mit anderem Finding
    verschmolzen werden (`over_split_same_risk_cluster`).

## Minimal-Zeile (Markdown-Beispiel)

| contract_id | run_id | finding_title | theme | lens | severity | materiality | playbook_id | expected_outcome | actual_outcome | error_class | keep_merge_split_decision | evidence_ok | reviewer_visible | comment |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GS-01-kalib | r_abc123 | "Unbegrenztes Auditrecht …" | audit_rights | LENS-AUDIT | high | high | PB-AUDIT-001 | risk | risk | ok | keep | yes | yes | Klar, Playbook passt. |
| GS-01-kalib | r_abc123 | "[Informativ] Maßnahmenplan 30 Tage" | audit_rights | LENS-AUDIT | info | low | – | info | info | ok | keep | yes | no | Remediation-Commitment, korrekt unterdrückt. |
| GS-01-kalib | r_abc123 | "99,99% Verfügbarkeit + unbegrenzte Strafe" | sla_feasibility | LENS-SLA | high | high | PB-SLA-002 | risk | risk | over_aggregation_multi_risk_clause | split | partial | yes | Zwei Verhandlungshebel in einem Finding; Splitting nötig. |

## Minimale Metriken (aggregiert je Vertrag × Run)

In `baseline_procedure.md` näher erklärt. Hier die Pflicht-Zahlen, die
sich aus der Matrix direkt ableiten lassen:

| Metrik | Ableitung aus der Matrix |
|---|---|
| sichtbare Findings | `count(reviewer_visible == yes)` |
| Info-Findings | `count(actual_outcome == info)` |
| Findings mit Playbook | `count(playbook_id != "")` |
| Findings ohne Playbook | `count(playbook_id == "")` |
| offensichtliche Merge-Fehler | `count(error_class == wrong_merge)` + `count(over_aggregation_multi_risk_clause)` |
| offensichtliche Split-Fehler | `count(error_class == wrong_split)` + `count(over_split_same_risk_cluster)` |
| reviewer-relevante Fehlfindings | `count(error_class in {false_positive_limiting_clause, reviewer_unfriendly_meta_finding})` |
| Multi-Risk-Findings | `count(error_class == over_aggregation_multi_risk_clause)` |
| überfragmentierte Findings | `count(error_class == over_split_same_risk_cluster)` |
| false negatives | `count(error_class == false_negative_material_risk)` (aus manueller Klausel-Liste zu ergänzen) |

`false_negative_material_risk` kann nicht allein aus der Matrix abgeleitet
werden — dafür braucht es einen kurzen manuellen Abgleich der Vertrags-Kernklauseln
gegen die Findings-Liste (siehe `baseline_procedure.md` Schritt 3b).
