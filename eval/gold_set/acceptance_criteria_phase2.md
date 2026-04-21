# Akzeptanzkriterien für Phase 2 (spätere Kalibrierung)

Ziel dieser Kriterien: Phase 2 startet **nicht** mit Ad-hoc-Tuning,
sondern mit klar definierten Zielzuständen, die über mehrere Verträge
hinweg gemessen werden.

Alle Kriterien beziehen sich auf den **Vergleich** zwischen einem
Before-Run (aktueller Code-Stand, Phase 1 Baseline) und einem
After-Run (Code-Stand nach Phase-2-Änderungen) auf **denselben**
Gold-Set-Verträgen.

## Harte Kriterien (müssen erfüllt sein)

1. **Keine Regression auf Kerntreffer**
   - Jede Klausel, die im Before-Run korrekt mit Playbook-Zuordnung aus
     PB-AUDIT-001/002/003, PB-INC-001/002/003, PB-SLA-002/004/005
     erkannt wurde, wird im After-Run ebenfalls korrekt erkannt.
   - Kein Finding mit Playbook-Match fällt in den Info-Bucket, ohne dass
     die Matrix ein `false_positive_limiting_clause` dafür zeigt.

2. **Kein neuer Noise**
   - Anzahl `reviewer_unfriendly_meta_finding` in der Default-Ansicht
     wächst nicht.
   - Englischer Debug-/Analysten-Text taucht im Default-Export nicht auf.

3. **Evidenz bleibt stabil**
   - Anzahl der Evidence-Zeilen je Vertrag ändert sich zwischen Before
     und After maximal um +/- 5 % ohne erklärenden Eintrag in der
     Matrix.

## Messbare Verbesserungen (Zielrichtung)

Die folgenden Metriken sollten sich gegenüber dem Before-Run in **Summe
über alle Gold-Set-Verträge** verbessern. Phase 2 gilt als erfolgreich,
wenn mindestens 4 der 6 Metriken sich verbessern und keine sich
verschlechtert.

| Metrik | Ziel |
|---|---|
| `false_positive_limiting_clause` | weniger |
| `missing_playbook_match` auf PB-AUDIT / PB-INC / PB-SLA | weniger |
| `wrong_merge` + `over_aggregation_multi_risk_clause` | weniger |
| `wrong_split` + `over_split_same_risk_cluster` | weniger |
| `evidence_misaligned` | weniger |
| `inconsistent_match_across_runs` | weniger |

## Weiche Kriterien (qualitativ)

- **Titel-Konsistenz**: Finding-Titel folgen durchgängig dem Schema
  `<Theme-Label>: <Playbook-Risk-Pattern>` (für Risk) bzw.
  `[Informativ] <Theme-Label>: <Kurztext>` (für Info).
- **Empfehlungen**: Bei Findings mit Playbook enthält die Empfehlung
  mindestens eine Alternativformulierung und eine Bieterfrage aus dem
  Playbook.
- **SLA-Findings**: 99,99 %-Fall und ungedeckelte Strafe erscheinen als
  getrennte Findings, wenn sie im Vertragstext getrennt verhandelbar
  sind.

## Explizite Non-Goals für Phase 2

- Keine Erweiterung auf neue Themes (SUBCONTRACTOR, BCM_ITSCM,
  DATA_PROTECTION, etc.) — kommt frühestens Phase 3.
- Keine komplette Überarbeitung des Klassifikators. Nur gezielte
  Ergänzungen basierend auf den Häufigkeiten der Fehlerklassen in der
  Matrix.
- Keine Änderung an der LLM-Prompt-Architektur (Developer-Prompt-Struktur
  mit 4 Fokusfeldern bleibt).
- Kein Umbau der DB-Schicht.

## Wann wird Phase 2 eröffnet?

Phase 2 startet, sobald mindestens **3 Verträge** ausgefüllte
Bewertungsmatrizen haben **und** pro Vertrag ein `summary.md` vorliegt.
Vorher ist jede Änderung wieder Einzelvertrags-Kalibrierung und
verletzt den Gold-Set-Rahmen.
