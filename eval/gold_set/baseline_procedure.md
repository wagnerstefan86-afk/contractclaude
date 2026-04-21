# Baseline-Vorgehen je Gold-Set-Vertrag

Ziel: Für jeden Vertrag im Gold-Set einen **reproduzierbaren** Baseline-Run
erzeugen, dessen Output in Git versionierbar ist. Keine eigene
Eval-Infrastruktur, keine DB-Dumps. Nur flache, nachvollziehbare Artefakte.

## Pro Vertrag × Run

### 1. Vorbereitung
- Stabile `contract_id` vergeben, z. B. `GS-01-kalib`, `GS-02-audit-heavy`.
- Dokument(e) unter `eval/gold_set/contracts/<contract_id>/` ablegen
  (nur Metadaten und Hinweise — keine echten Kundendokumente ins Repo
  einchecken; nur Platzhalter-Fixtures, wenn nötig).
- Aktuellen Code-Stand festhalten:
  `git rev-parse --short HEAD` notieren als `git_sha`.

### 2. Run erzeugen
- Paket in der UI anlegen, Dokument hochladen, parsen, Analyse starten.
- Die `analysis_runs.id` ist unsere `run_id`.
- Nach Abschluss: Findings-Liste aufrufen.

### 3. Artefakte sichern

Alle Artefakte landen unter
`eval/gold_set/runs/<contract_id>/<run_id>/`:

3a. **Excel-Export** — zweimal herunterladen:
- Default (`/ui/packages/<id>/findings/export.xlsx`)
- Mit Info-Findings (`/ui/packages/<id>/findings/export.xlsx?include_info=1`)

Dateinamen: `findings_default.xlsx`, `findings_include_info.xlsx`.

3b. **Manuelle Kernklausel-Liste** (für false-negative Erkennung):
- Datei `expected_clauses.md` je Vertrag.
- Pro materieller Kernklausel ein Bullet mit Kurzbeschreibung und
  Vertragsabschnitt, z. B.:
  - "SLA 99,99% Verfügbarkeit (§3)"
  - "Unbegrenzte Vertragsstrafe (§6.2)"
- Nach dem Run prüfen, welche dieser Klauseln **nicht** als Finding
  aufgetaucht sind → sind Kandidaten für `false_negative_material_risk`.

3c. **Bewertungsmatrix-Zeilen**:
- In `evaluation_matrix_template.csv` eine Zeile pro Finding anlegen
  (Spalten aus `evaluation_matrix.md`).
- Fehlerklasse vergeben, Kommentar kurz halten.

3d. **Aggregierte Kennzahlen**:
- In Datei `summary.md` im Run-Ordner die Minimal-Metriken notieren.
- Siehe Template unten.

3e. **Optional: Screenshot** der Findings-Liste mit Default-Filter.

### 4. Vorher / Nachher-Vergleich

Pro Vertrag wird beim zweiten und jedem weiteren Run zusätzlich ein
Vergleich mit dem Vorlauf dokumentiert:

- Liste: welche Findings neu, welche verschwunden, welche mit
  geändertem `severity` / `playbook_id` / `error_class`.
- Diff zwischen den beiden `findings_default.xlsx` oder
  `findings_include_info.xlsx` (z. B. per `diff` über CSV-Ansicht).
- Bei **Regression** auf einem Kerntreffer (Audit / Incident / SLA) →
  als explizit rot markieren.

## Minimale Metriken je Run

Die folgende Tabelle wird pro Run in `summary.md` ausgefüllt. Alle Zahlen
direkt aus der Matrix ableitbar (siehe `evaluation_matrix.md`):

| Metrik | Wert |
|---|---|
| Sichtbare Findings (Default) | |
| Info-Findings (ausgeblendet) | |
| Findings mit Playbook | |
| Findings ohne Playbook | |
| Merge-Fehler (`wrong_merge` + `over_aggregation_multi_risk_clause`) | |
| Split-Fehler (`wrong_split` + `over_split_same_risk_cluster`) | |
| Reviewer-relevante Fehlfindings (`false_positive_limiting_clause` + `reviewer_unfriendly_meta_finding`) | |
| Multi-Risk-Findings (`over_aggregation_multi_risk_clause`) | |
| Überfragmentierte Findings (`over_split_same_risk_cluster`) | |
| False negatives (aus `expected_clauses.md` fehlend) | |
| Inkonsistenzen zum Vorlauf (`inconsistent_match_across_runs`) | |

## Datei- und Ordnerlayout

```
eval/gold_set/
  README.md
  error_classes.md
  evaluation_matrix.md
  evaluation_matrix_template.csv
  baseline_procedure.md            ← dieses Dokument
  reference_cases.md
  acceptance_criteria_phase2.md
  contract_order.md
  contracts/
    GS-01-kalib/
      meta.md                      ← Beschreibung, Vertragsquelle, Scope
      expected_clauses.md          ← Kernklauseln für false-negative-Check
    GS-02-audit-heavy/
      …
  runs/
    GS-01-kalib/
      <run_id>/
        summary.md
        findings_default.xlsx
        findings_include_info.xlsx
        screenshot_default.png     (optional)
    GS-02-audit-heavy/
      …
```

## Bewusste Verzicht-Punkte

- Keine automatisierte Metrik-Berechnung. Die Matrix ist klein genug,
  um per Hand / mit einfachem `awk` / Tabellenkalkulation zu aggregieren.
- Keine Ground-Truth-Annotation der Vertragstexte auf Segmentebene.
  Das wäre Phase 3, nicht Phase 1.
- Keine Gewichtung der Fehlerklassen. Alle zählen in Phase 1 gleich,
  Priorisierung erfolgt in Phase 2 beim Auswerten der Häufigkeiten.
