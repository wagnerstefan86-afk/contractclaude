# Fixture-YAML-Schema

Eine Fixture-Datei pro Gold-Set-Vertrag × Run. Flach genug, damit man
sie in Git diffen kann.

## Top-Level

```yaml
contract_id: GS-03
run_id: 5d9f4a7e-...           # analysis_runs.id aus der DB
git_sha: 261a52b                # HEAD-SHA zum Zeitpunkt des Runs
captured_at: 2026-04-22         # Datum des Exports
source: "live-container"        # Freitext-Quellenhinweis
active_lenses: [LENS-AUDIT, LENS-INCIDENT, LENS-SLA]
obligations:
  - ...                         # siehe unten
```

## Pro Obligation

```yaml
- obligation_id: uuid-...       # obligations.id (Primärschlüssel)
  lens: LENS-AUDIT              # aus lens_configs.lens_id
  theme: audit_rights           # Theme-Enum
  summary: >-                   # obligations.summary — LLM-Zusammenfassung
    Audits dürfen 1x jährlich mit 20 Werktagen Vorlauf durchgeführt
    werden.
  verbatim_quote: >-            # obligations.verbatim_quote — Originaltext
    Der Auftraggeber hat das Recht, einmal pro Kalenderjahr Audits mit
    einer Vorlaufzeit von 20 Werktagen durchzuführen, ...
  baseline_gap_description: >-  # aus baseline_matcher
    Keine Begrenzungen gefunden – unbegrenzte Pflichten entsprechen
    nie dem Standard.

  # --- Ist-Zustand aus dem Run ---
  current_finding_id: uuid-...  # findings.id (leer wenn keine Zuordnung)
  current_severity: high        # info|low|medium|high|critical
  current_materiality: high
  current_playbook_id: PB-AUDIT-001   # leer wenn kein Match
  current_finding_title: >-
    Audit- und Prüfungsrechte: Unbegrenztes Auditrecht ohne Vorlaufzeit
    und Häufigkeitslimit

  # --- Reviewer-Erwartung ---
  expected_outcome: info         # risk | info | suppress
  expected_playbook: null        # oder "PB-XXX" oder "null"
  regression_case: true          # im Phase-2a-Repair-Set behalten?

  # --- Diagnose ---
  hypothesis: >-                 # kurzer Freitext: welche Regel würde greifen müssen
    Die negative_any-Liste für PB-AUDIT-001 enthält "werktage vorlauf",
    aber der LLM-Text sagt "Vorlaufzeit von 20 Werktagen". Substring
    trifft nicht — Syntax-Variante fehlt.
  root_cause: matcher_negative_gap  # siehe Enum unten
```

## Enum `root_cause`

Jeder Regression-Fall bekommt genau eine dieser Klassen. Sie bildet
auf die vier Regelstellen (Matcher / Klassifikator / Eskalation /
Finding-Assembly) ab:

| Code | Regelstelle | Bedeutung |
|---|---|---|
| `matcher_negative_gap` | Matcher | `negative_any` für betroffene Signatur fängt den realen Wortlaut nicht (Wort-/Flexions-Varianz) |
| `matcher_over_support` | Matcher | Signatur-Support-Gruppe zu breit — feuert bei harmloser Klausel |
| `matcher_required_wrong` | Matcher | Required-Group triggert auf falsches Themenwort |
| `classifier_positive_gap` | Klassifikator | `_EXPLICIT_LIMIT_ALL` / Positiv-Muster erkennt den realen Wortlaut nicht |
| `classifier_amplifier_overblock` | Klassifikator | Risk-Amplifier vetoiert eine legitime Limit-Klausel |
| `classifier_generic_negation` | Klassifikator | Allgemeiner `_NEGATION_NEAR_POSITIVE` blockt Limit-Satz |
| `escalation_limits_null` | Eskalation | `all_limits_null → HIGH` in `materiality_scorer` (weil LLM die `limits`-Felder nicht gefüllt hat) |
| `escalation_baseline_gap` | Eskalation | `baseline_gap_description` triggert `_has_explicit_gap` im Klassifikator, obwohl der Gap nur generisch ist |
| `assembly_wrong_merge` | Finding-Assembly | Obligation ist auf Einzel-Obligation-Ebene korrekt (Harness liefert `informational`), wird aber im Live-Run per Playbook-ID-Merge in ein Risk-Finding gezogen und dadurch für den Reviewer sichtbar |
| `ok` | — | kein Regression-Fall (Fixture-Kontext) |

### Abgrenzung `assembly_wrong_merge` von Matcher/Klassifikator/Eskalation

- Wenn der **Harness** auf der Einzel-Obligation `cls=informational`
  und `pb_got=—` meldet, ist Matcher + Klassifikator für sich ok.
  Tritt die Obligation trotzdem **im Live-Run** als Evidenz eines
  sichtbaren Risk-Findings auf, liegt das Problem in
  `scoring/finding_generator._group_obligations_by_risk` — konkret
  im zweiten Merge-Pass, der Komponenten mit gemeinsamer Playbook-ID
  zusammenführt (erweitert gelegentlich auch auf unmatched
  Obligations via ihrer Relationen, falls eine Relation vorliegt).
  → Code: `assembly_wrong_merge`.

- Wenn der **Harness** auf der Einzel-Obligation `cls=risk` meldet,
  obwohl der Reviewer `info` erwartet, ist einer der drei anderen
  Regelstellen-Codes (`matcher_*`, `classifier_*`, `escalation_*`)
  passend. Kein `assembly_wrong_merge`.

- Eine Obligation kann im Live-Run gleichzeitig Evidenz in einem
  Risk-Finding sein (assembly-bedingt) UND ein Matcher- oder
  Klassifikator-Problem haben. In diesem Fall gewinnt die
  Einzelfall-Diagnose: der Code, der den Status der Obligation
  **alleine** erklärt, wird eingetragen. Der Merge-Aspekt kann als
  Sekundär-Hinweis in `hypothesis` dokumentiert werden.

## Convention für leere Werte

- `current_playbook_id: null` (YAML-null) statt Leerstring.
- `expected_playbook: null` wenn keine Zuordnung erwartet wird.
- `hypothesis: ""` wenn noch unklar.

## Größe

Halte Fixtures bewusst klein: **pro Vertrag maximal 15–25 Obligations**.
Nur echte Regression-Fälle und ein paar Kernfindings als Regression-
Anker. Mehr wird unübersichtlich und verwässert den Fokus.
