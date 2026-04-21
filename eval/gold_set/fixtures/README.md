# Live Fixtures — Phase 2a Repair

## Warum

Phase 2a wurde auf **idealisierten Obligation-Texten** getestet und hat
21/21 Deterministik-Cases getroffen. Der echte Container-Lauf zeigt
jedoch:

- GS-01: 23 Obligations, 18 Findings
- GS-02: 21 Obligations, 12 Findings
- GS-03: 15 Obligations, 11 Findings

GS-03 erzeugt weiterhin zu viele sichtbare Hoch/Hoch-Findings — die
Lücke liegt zwischen der Wortwahl der deterministischen Testtexte und
dem, was der LLM im Betrieb tatsächlich produziert.

**Konsequenz**: ab Phase 2a-Repair testen wir nur noch gegen **echte
Live-Texte**, die aus dem Container exportiert und hier als Fixture
committed werden.

## Ordnerlayout

```
eval/gold_set/fixtures/
├── README.md               ← dieses Dokument
├── schema.md               ← YAML-Feldspezifikation
├── template.yaml           ← leeres Template pro Vertrag
├── GS-01-kalib.yaml        ← (zu befüllen) Live-Obligations GS-01
├── GS-02.yaml              ← (zu befüllen) Live-Obligations GS-02
├── GS-03.yaml              ← (zu befüllen) Live-Obligations GS-03
└── run_fixture_tests.py    ← Test-Harness: Matcher + Klassifikator
                               gegen echte Fixtures laufen lassen
```

Der DB-Export-Helfer liegt bei den Standard-Scripts:
`scripts/dump_run_fixtures.py`.

## Workflow

### Schritt 1 — Fixtures exportieren

Im Container, nach einem Run:

```
python scripts/dump_run_fixtures.py \
    --run-id <analysis_runs.id> \
    --contract-id GS-03 \
    --out eval/gold_set/fixtures/GS-03.yaml
```

Das Skript liest aus der Postgres-DB:
- alle Obligations des Runs (`summary`, `verbatim_quote`,
  `baseline_gap_description`, `theme`, `lens`)
- die zugehörigen Findings (via Evidence): `severity`, `materiality`,
  `playbook_entry_id`, `title`

und schreibt eine YAML-Fixture-Datei (siehe `schema.md`).

### Schritt 2 — Reviewer ergänzt Erwartung + Hypothese

Pro Obligation in der Fixture:

- `expected_outcome`: `risk` / `info` / `suppress` (welche Reviewer-
  Erwartung)
- `expected_playbook`: `PB-XXX` oder leer
- `regression_case`: `true` wenn der Fall im Test-Set bleiben soll
- `hypothesis`: kurzer Freitext — welche Regel würde greifen müssen?
- `root_cause`: Enum aus `schema.md` (matcher_negative_gap /
  classifier_positive_gap / escalation_limits_null / ...)

### Schritt 3 — Test-Harness laufen lassen

```
python eval/gold_set/fixtures/run_fixture_tests.py \
    eval/gold_set/fixtures/GS-03.yaml
```

Ausgabe:

```
GS-03 live fixtures — 15 obligations
─────────────────────────────────────────────
✓ F1  audit_rights   cls_got=info   exp=info   pb_got=—
✗ F2  sla_feasibility cls_got=risk   exp=info   pb_got=PB-SLA-001
     hypothesis: "negative_any greift nicht auf 'Wartungsfenster werden
                   aus der Berechnung herausgerechnet'"
     root_cause: matcher_negative_gap
...
```

Jedes Delta (`✗`) ist ein Regression-Fall.

### Schritt 4 — Gezielte Repair-Runde

Wenn mindestens 8–12 Regression-Fälle klassifiziert sind, wird die
Reparatur auf **1–2 Regelstellen** fokussiert (Matcher-Negativ-Liste,
Klassifikator-Positiv-Liste, Eskalations-Logik). Kein Refactoring.
Kein neuer Scope.

## Was diese Fixtures NICHT sind

- **Keine Ground Truth** auf Segmentebene — das wäre Phase 3.
- **Kein Replacement des deterministischen Tests** — deterministische
  Tests bleiben als Regression-Gate. Sie sind jetzt aber nur noch das
  **Minimum**, nicht der Akzeptanz-Beweis.
- **Keine automatische Pipeline-Änderung** — die Fixtures sind
  ausschließlich Diagnose-Input, die Reparatur bleibt manuell
  per Code-Change.

## Akzeptanzkriterium für Phase 2a-Repair

Der nächste Reparatur-Schritt gilt als erfolgreich, wenn:

1. Die 8–12 ausgewählten Live-Regression-Fälle (GS-03 dominiert) nach
   der Änderung das erwartete Verhalten zeigen
2. Alle GS-02 und GS-01 Kernfindings unverändert als `risk` mit
   korrektem Playbook erhalten bleiben
3. Der deterministische Test-Set weiterhin 21/21 trifft
4. Keine neue Heuristik, keine neuen Playbook-Einträge, keine neuen
   Lenses eingeführt werden
