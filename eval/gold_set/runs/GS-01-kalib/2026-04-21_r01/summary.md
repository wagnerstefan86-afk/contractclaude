# GS-01-kalib — Run 2026-04-21 r01

Erstbewertung des Kalibrierungsvertrags mit dem Gold-Set-Rahmen.

## Lauf-Metadaten

| Feld | Wert |
|---|---|
| `contract_id` | GS-01-kalib |
| Run-Label | 2026-04-21_r01 |
| `git_sha` | bf0f72b |
| `run_id` (aus DB) | — nachzutragen |
| Aktive Lenses | LENS-AUDIT, LENS-INCIDENT, LENS-SLA |

## Ausgangslage

Bewertet wurde die **Default-sichtbare** Findings-Liste des Runs (also
`severity != info`). Der Reviewer hat für jedes Finding eine
primäre Fehlerklasse nach `../../error_classes.md` vergeben. Die
vollständige Matrix liegt in `evaluation_matrix.csv` nebenan.

## Minimal-Metriken

Direkt aus der Matrix abgeleitet (siehe `../../baseline_procedure.md`).

| Metrik | Wert |
|---|---|
| Sichtbare Findings (Default) | 10 |
| Info-Findings (ausgeblendet) | nicht Teil dieser Bewertung (Default-View) |
| Findings mit Playbook | 5 |
| Findings ohne Playbook | 5 |
| Merge-Fehler (`wrong_merge` + `over_aggregation_multi_risk_clause`) | 2 |
| Split-Fehler (`wrong_split` + `over_split_same_risk_cluster`) | 1 |
| Reviewer-relevante Fehlfindings (`false_positive_limiting_clause` + `reviewer_unfriendly_meta_finding`) | 0 |
| Multi-Risk-Findings (`over_aggregation_multi_risk_clause`) | 1 |
| Überfragmentierte Findings (`over_split_same_risk_cluster`) | 1 |
| False Negatives (aus `expected_clauses.md` fehlend) | noch nicht geprüft |
| Inkonsistenzen zum Vorlauf (`inconsistent_match_across_runs`) | n/a (erster Run) |

## Fehlerklassen-Verteilung

| Klasse | n |
|---|---|
| `ok` | 3 |
| `missing_playbook_match` | 3 |
| `wrong_merge` | 1 |
| `over_aggregation_multi_risk_clause` | 1 |
| `lens_extraction_granularity_issue` | 1 |
| `over_split_same_risk_cluster` | 1 |

**Quote**: 3/10 `ok`, 7/10 mit Fehlerklasse.

## Zentrale Beobachtungen

- **Playbook-Abdeckung bleibt der größte Hebel**. 5 von 10 sichtbaren
  Findings haben keinen Playbook-Match, obwohl für vier davon (F02,
  F07, F08) ein passender Playbook-Eintrag existiert (PB-AUDIT-002,
  PB-SLA-001, PB-SLA-004). Nur F02 ist inhaltlich in den Cluster von
  F01 aufzulösen.
- **Audit-Cluster ist über-aggregiert**. F01 (PB-AUDIT-002) zieht
  mehrere Verhandlungshebel zusammen. F02 gehört zum selben Cluster,
  bekommt aber kein Playbook. Der Merge-Pass greift auf Playbook-ID
  und übersieht inhaltlich verwandte Findings ohne Match.
- **SLA-Reaktionszeiten sind über-fragmentiert**. F08 (P1, 15 Min),
  F09 (P3, 4 h) und F10 (P2, 30 Min) sind drei Findings zum selben
  Risikocluster. Nur F08 würde PB-SLA-004 treffen; F09/F10 bleiben
  ohne Playbook. F09 ist zusätzlich Rauschen aus der Extraktion.
- **SLA 99,99 % + Vertragsstrafe im selben Finding**. F05 trägt zwei
  Verhandlungshebel und nur ein Playbook (PB-SLA-002). Die
  Pönale-Komponente fehlt mit PB-SLA-005 als Sekundär-Match.
- **Kein False Positive auf begrenzenden Klauseln**. Der in Phase 1
  eingebaute Klassifikator unterdrückt die erwarteten
  risikoreduzierenden Klauseln (ISO-Zertifikat, Maßnahmenplan,
  Scope-Limit) zuverlässig — sie tauchen in der Default-Ansicht
  nicht mehr auf.
- **Keine Cross-Theme-/Meta-Findings sichtbar**. Die Hygiene-Änderung
  aus `85b6326` wirkt: `reviewer_unfriendly_meta_finding` = 0.

## Sekundärklassen (aus Kommentaren)

Diese sind bewusst nicht in der Matrix-Spalte erfasst, aber für die
Phase-2-Analyse relevant:

| Finding | Primär | Sekundär |
|---|---|---|
| F01 | `wrong_merge` | `mixed_risk_core` |
| F05 | `over_aggregation_multi_risk_clause` | `missing_playbook_match` (PB-SLA-005 für Pönale) |
| F08 | `missing_playbook_match` | `over_split_same_risk_cluster` (Cluster F08+F09+F10) |

## Offene Punkte bis Phase 2

- **`expected_clauses.md` vs. Findings durchlaufen** und
  `false_negative_material_risk` ergänzen. Das ist in dieser
  Erstbewertung noch nicht gemacht worden.
- **`run_id` aus der DB nachtragen** (Spalte ist Platzhalter).
- **Info-Findings-Seite nachbewerten**. Aktuell nur Default-View
  bewertet — `?include_info=1` ist separat anzuschauen und als
  zweiter Abschnitt in die Matrix zu ergänzen (ISO-Zertifikat,
  Maßnahmenplan, Auditumfang, etc.).

## Verweise auf Akzeptanzkriterien Phase 2

Dieser Run zeigt an welchen Stellen Phase 2 greifen muss
(`../../acceptance_criteria_phase2.md`):

- **Ziel-Metrik „weniger `missing_playbook_match` auf PB-AUDIT / PB-INC
  / PB-SLA"**: aktuell 3/10 → in Phase 2 messbar reduzieren.
- **Ziel-Metrik „weniger Multi-Risk-Findings"**: aktuell 1/10 (F05) →
  Splitting auf extraction- oder post-extraction-Ebene erforderlich.
- **Ziel-Metrik „weniger über-fragmentierte Findings"**: aktuell 1/10
  (F10, zusammen mit F08/F09 als Cluster) → Lens- oder
  Merge-Strategie schärfen.
- **Harte Regel „keine Regression auf Kerntreffer"**: F03, F04, F06
  sind korrekt; diese dürfen in Phase 2 nicht verloren gehen.
