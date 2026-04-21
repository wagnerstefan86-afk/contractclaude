# GS-01-kalib — Kalibrierungsvertrag

Erster Vertrag im Gold-Set. Dient als bekannte Baseline, auf der die
bisherigen Referenzfälle aus `eval/gold_set/reference_cases.md`
entstanden sind.

## Quelle

- Dateien: `tests/fixtures/test_contract.pdf` und `tests/fixtures/test_contract.docx`
  im Repo (erzeugt von `tests/create_fixtures.py`).
- Typ: synthetischer Rahmenvertrag IT-Services mit Audit-, Incident-,
  SLA-, Haftungs- und Subunternehmer-Klauseln.
- Keine echten Kundendaten — als Test-Fixture gedacht.

## Profilsteckbrief

| Aspekt | Kurz |
|---|---|
| Aktive Lenses | LENS-AUDIT, LENS-INCIDENT, LENS-SLA |
| Audit-Schwerpunkt | Unbegrenzte Frequenz, Drittprüfer ohne Ankündigung, kostenfreie Unterlagen, Scope auf Vertrag begrenzt |
| Incident-Schwerpunkt | 2 h Meldefrist, Meldepflicht für jedes Security-Event |
| SLA-Schwerpunkt | 99,99 %, Wartungsfenster-Frage, P1/P2/P3-Reaktionsmatrix, Vertragsstrafe |
| Risikoreduzierende Elemente | ISO-27001-Nachweis, Maßnahmenplan 30 Tage, Scope-Limit |

## Genutzt für

- Phase 1 Erstbewertung: `../../runs/GS-01-kalib/2026-04-21_r01/`
- Referenzfälle-Sammlung: `../../reference_cases.md`

## Nicht im Repo

Keine externen Vertragsdokumente — nur die im Repo vorhandene Test-
Fixture. Für spätere echte Kundenverträge wird ausschließlich diese
meta.md + eine `expected_clauses.md` geführt.
