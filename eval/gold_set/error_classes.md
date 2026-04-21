# Fehlerklassen-Taxonomie (Gold-Set, Phase 1)

Kompakte, reviewer-taugliche Klassifikation für Findings-Fehler. Jede
Beobachtung in der Bewertungsmatrix bekommt **genau eine** primäre
Fehlerklasse (oder `ok`). Falls ein Finding mehrere Probleme hat,
wähle die schwerwiegendste — ein freier Kommentar darf Zusatzes nennen.

Die Klassen sind bewusst wenige und eng definiert, damit die Auswertung
über mehrere Verträge stabil bleibt.

## Übersicht

| Code | Name | Kurz |
|---|---|---|
| `ok` | kein Fehler | Finding ist sachlich, klar, reviewer-tauglich |
| `false_positive_limiting_clause` | Falschmeldung auf begrenzender Klausel | risikoreduzierende Klausel als Risk gelistet |
| `false_negative_material_risk` | Materielles Risiko nicht erkannt | echte Gefahr fehlt komplett oder ist im Info-Bucket |
| `wrong_playbook_match` | Falsche Playbook-Zuordnung | Playbook passt inhaltlich nicht zum Finding |
| `missing_playbook_match` | Playbook fehlt bei klarem Risikokern | Finding ist Risk, sollte aber auf bestehenden Playbook-Eintrag mappen |
| `wrong_merge` | Falsches Verschmelzen | Findings zu unterschiedlichen Risiken wurden fälschlich zusammengezogen |
| `wrong_split` | Falsches Aufteilen | ein Risikokern steht unnötig als mehrere kleine Findings da |
| `mixed_risk_core` | Vermischter Risikokern | Titel/Empfehlung/Evidenz deuten auf zwei unterschiedliche Kerne hin |
| `evidence_misaligned` | Evidenz passt nicht zum Finding-Titel | Titel / Empfehlung und zitierter Klauseltext driften auseinander |
| `reviewer_unfriendly_meta_finding` | Meta-/Debug-Finding in sichtbarer Liste | englischer Rationale-Text, Cross-Theme-Debug-Output, "unclear" |
| `over_aggregation_multi_risk_clause` | Ein Finding bündelt mehrere Verhandlungshebel | z. B. Verfügbarkeit + Vertragsstrafe in einem Finding |
| `over_split_same_risk_cluster` | Zusammengehöriger Risikokern zerfällt | z. B. P1 / P2 / P3 Reaktionszeiten in drei Findings |
| `lens_extraction_granularity_issue` | Lens-Extraktion zu grob oder zu fein | eine Linse liefert Obligations, die inhaltlich eine sein sollten oder umgekehrt |
| `inconsistent_match_across_runs` | Matcher-Ergebnis instabil zwischen Läufen | identische Klausel → anderes Playbook / anderer Info-Status |

## Definitionen und Beispiele

### `false_positive_limiting_clause`
**Definition**: Eine risikoreduzierende oder standardnahe Klausel erscheint
als normales Risk-Finding, obwohl sie für den Reviewer keinen Handlungsbedarf
erzeugt.
**Beispiel**: "Der Auftragnehmer verfügt über eine ISO 27001 Zertifizierung
mit Testat" → sollte INFO / ausgeblendet sein.

### `false_negative_material_risk`
**Definition**: Eine im Vertragstext vorhandene, materiell verhandlungsrelevante
Klausel fehlt in der sichtbaren Findings-Liste vollständig oder steht
fälschlich im Info-Bucket.
**Beispiel**: "Verfügbarkeit 99,99% ohne Wartungsfenster" wird nicht extrahiert
oder bekommt severity=INFO.

### `wrong_playbook_match`
**Definition**: Ein Finding erhält eine Playbook-Zuordnung, die zum Risikokern
nicht passt. Die Playbook-Empfehlung führt den Reviewer in die falsche
Richtung.
**Beispiel**: "Drittprüfer ohne Vorlauf" → fälschlich auf PB-AUDIT-003
(Kostenfreiheit) statt PB-AUDIT-002 (Drittaudits).

### `missing_playbook_match`
**Definition**: Ein klarer Risikokern, für den ein passender Playbook-Eintrag
existiert, erscheint als Finding ohne Playbook-Zuordnung. Reviewer verliert
die Standardposition und die Alternativformulierungen.
**Beispiel**: "Vertragsstrafe unbegrenzt" → keine Zuordnung auf PB-SLA-005.

### `wrong_merge`
**Definition**: Zwei Findings, die unterschiedliche Risiken mit unterschiedlichen
Verhandlungshebeln beschreiben, werden in ein Finding zusammengeführt.
**Beispiel**: "Unbegrenzte Auditfrequenz" + "Kostenfreie Auditunterstützung"
landen in einem Finding. Getrennte Empfehlungen (Häufigkeit vs. Kosten) gehen
verloren.

### `wrong_split`
**Definition**: Zwei Fundstellen derselben Klausel / desselben Risikokerns
stehen als separate Findings da und verwässern die Review-Entscheidung.
**Beispiel**: "keine Begrenzung der Auditfrequenz" (§5) und "unlimited audits"
(§5.1) bilden zwei Findings mit gleichem Playbook-Match.

### `mixed_risk_core`
**Definition**: Titel, Beschreibung, Empfehlung oder Evidenz des Findings
deuten auf mehr als einen Risikokern. Der Reviewer kann keine eindeutige
Verhandlungsrichtung ableiten.
**Beispiel**: Titel "Unbegrenztes Auditrecht", Evidenzen enthalten aber auch
"Drittprüfer" und "Kostenfreie Unterlagen".

### `evidence_misaligned`
**Definition**: Die zitierten Evidenz-Segmente tragen das Finding-Thema nicht
sauber. Titel / Standardposition und Klauseltext driften auseinander.
**Beispiel**: Finding "Unrealistisch kurze Meldefrist", Evidenz zeigt aber
SLA-Verfügbarkeitsklausel.

### `reviewer_unfriendly_meta_finding`
**Definition**: Ein Finding, das eher Tool-Output als Vertragsbefund ist.
Debug-Rationale, englischer Analystenton, "unclear"-Ergebnisse, generische
Cross-Theme-Texte.
**Beispiel**: "Cross-Theme-Konflikt: Conflict detected between unlimited
audit and short incident notification — analyst debug output".

### `over_aggregation_multi_risk_clause`
**Definition**: Ein Finding bündelt mehrere inhaltlich unterschiedliche
Verhandlungshebel, die fachlich getrennt verhandelt werden müssten.
**Beispiel**: "Verfügbarkeit 99,99% UND Vertragsstrafe unbegrenzt" — zwei
Verhandlungsthemen, zwei getrennte Playbook-Standardpositionen, aber ein
Finding.

### `over_split_same_risk_cluster`
**Definition**: Ein einzelner Risikocluster wird in viele feingranulare
Findings zerlegt, die der Reviewer alle als einen Punkt abhandeln würde.
**Beispiel**: Reaktionszeiten P1, P2, P3 als drei separate Findings mit
derselben Empfehlung und derselben Standardposition.

### `lens_extraction_granularity_issue`
**Definition**: Eine Lens liefert Obligations auf der falschen Granularität —
zu grob (mehrere Inhalte in einem Obligation-Text) oder zu fein (eine
Klausel als mehrere Obligations mit minimalen Textunterschieden).
**Beispiel**: LENS-SLA liefert eine Obligation "Verfügbarkeit 99,99% auf
Monatsbasis mit unbegrenzter Vertragsstrafe" statt zweier getrennter
Obligations.

### `inconsistent_match_across_runs`
**Definition**: Zwei Läufe auf identischem oder nahezu identischem Vertragstext
führen zu unterschiedlichen Playbook-Zuordnungen oder unterschiedlichen
Info-vs-Risk-Entscheidungen.
**Beispiel**: Run 1: "Auditumfang auf Vertragsgegenstand beschränkt" → INFO.
Run 2 auf derselben Version: → RISK ohne Playbook.

## Verwendung in der Bewertungsmatrix

- In der Spalte `error_class` steht genau einer der o. g. Codes.
- `ok` für korrekte Findings.
- Mehrfachzuordnung ist bewusst nicht vorgesehen — die schwerwiegendste
  Klasse siegt, Details gehen in die `comment`-Spalte.
- Bei `over_aggregation_multi_risk_clause` zusätzlich die zu trennenden
  Verhandlungshebel im Kommentar kurz nennen.
- Bei `over_split_same_risk_cluster` zusätzlich die Finding-IDs, die
  zusammengehören, im Kommentar listen.
