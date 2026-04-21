# Gold-Set — Phase 1 (Vorbereitung)

Dieser Ordner bildet den Rahmen für die nächste Kalibrierungsphase der
InfoSec-Contract-Review-Pipeline. Er enthält **keine** Code- oder
Pipeline-Änderungen, sondern nur Dokumentation, Vorlagen und
Referenzfälle, auf deren Basis wir anschließend strukturiert iterieren.

## Ziel

Eine belastbare Grundlage schaffen, um die Qualität der Findings systematisch
über **mehrere** Verträge hinweg zu messen und zu verbessern — statt auf
einem einzigen Kalibrierungsvertrag hin und her zu tunen.

## Scope von Phase 1

- Struktur, Artefakte und Prozess definieren
- Fehlerklassen-Taxonomie festlegen
- Bewertungsmatrix als Markdown + CSV-Template bereitstellen
- Baseline-Vorgehen je Vertrag beschreiben
- Bereits beobachtete Muster aus dem Kalibrierungsvertrag als
  Referenzfälle einfrieren
- Akzeptanzkriterien für Phase 2 formulieren
- Reihenfolge der ersten 3–5 Gold-Set-Verträge festlegen

**Nicht Scope** (wird bewusst NICHT gemacht):

- Neue Lenses, neue Playbook-Einträge, neue Matcher-Signaturen
- Anpassung der Klassifikator-Heuristik
- Tuning auf einzelne Klauseln
- Modell- oder Migrationsänderungen

## Dokumente in diesem Ordner

| Datei | Inhalt |
|---|---|
| `README.md` | Dieses Dokument — Übersicht und Prozess |
| `error_classes.md` | Fehlerklassen-Taxonomie inkl. Definitionen und Beispielen |
| `evaluation_matrix.md` | Beschreibung der Bewertungsmatrix und Spaltensemantik |
| `evaluation_matrix_template.csv` | CSV-Vorlage zum Ausfüllen je Vertrag × Run |
| `baseline_procedure.md` | Wie ein Baseline-Run je Vertrag erzeugt und festgehalten wird |
| `reference_cases.md` | Konkrete Muster aus bisherigen Läufen (Referenz-Fehlertypen) |
| `acceptance_criteria_phase2.md` | Akzeptanzkriterien für die folgende Kalibrierungsphase |
| `contract_order.md` | Empfohlene Reihenfolge der ersten 3–5 Verträge |

## Kurzer Phasen-Workflow (Vorausblick)

```
                  Phase 1 (jetzt)             Phase 2 (danach)
                  ───────────────             ────────────────
Rahmen schaffen  →  Verträge 1..N baseline →  Fehlerklassen    →  gezielte
(dieser Ordner)     bewerten                   aggregieren        Iteration
                                                                   auf Muster
```

Phase 2 startet **erst**, wenn mindestens 3 Verträge mit ausgefüllter
Bewertungsmatrix vorliegen — sonst sind einzelne Änderungen wieder
Ad-hoc-Tuning auf einem Einzelvertrag.

## Artefakte, die pro Run festgehalten werden

Siehe `baseline_procedure.md` für Details. Minimum:

1. `package_id`, `run_id`, `timestamp`, `git_sha`
2. Excel-Export der Findings (`?include_info=1` UND Default)
3. Ausgefüllte Zeile(n) in `evaluation_matrix_template.csv`
4. Optional: Screenshot der Findings-Liste mit aktuellen Filtern

Dies sind flache, versionierbare Artefakte — bewusst kein DB-Dump, keine
eigene Evaluations-Infrastruktur.
