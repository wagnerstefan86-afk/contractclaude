# Empfohlene Startreihenfolge — erste 3–5 Verträge

Die Reihenfolge ist so gewählt, dass jeder neue Vertrag eine **andere**
Schwachstelle der Pipeline belastet. So werden nach 3–5 Verträgen
Muster sichtbar, die auf einem einzigen Vertrag nie aufgefallen wären.

## Position 1 — `GS-01-kalib` (bisheriger Kalibrierungsvertrag)

- **Quelle**: `tests/fixtures/test_contract.pdf` / `.docx` (bereits im
  Repo).
- **Profil**: Gemischt, mit allen drei aktiven Lenses relevant. Enthält
  unbegrenzte Auditfrequenz, 2 h Meldefrist, 99,5 % Verfügbarkeit,
  kostenfreie Audits, Drittprüfer-Klausel.
- **Zweck**: Als bekannte Baseline — hier sind die Referenzfälle aus
  `reference_cases.md` alle entstanden.
- **Erwartete Fehlerklassen**: vor allem `false_positive_limiting_clause`
  (ISO-Zertifikat, Maßnahmenplan, Scope-Begrenzung) und ggf.
  `over_aggregation_multi_risk_clause` bei zusammengefassten
  Audit-Findings.

## Position 2 — `GS-02-sla-hart`

- **Profil**: Vertrag mit explizit harten SLA-Zahlen — 99,99 %
  Verfügbarkeit, transaktionsbasiert, 15-Min-P1-Reaktion, unbegrenzte
  Vertragsstrafe, fehlende Wartungsfenster-Ausnahme.
- **Zweck**: Test der neuen Playbook-Einträge PB-SLA-004 und PB-SLA-005
  unter realistischen Bedingungen. Prüft auch das Zusammenspiel von
  Multi-Risk-Klauseln ("99,99 % + unbegrenzte Strafe im selben Absatz").
- **Erwartete Fehlerklassen**:
  `over_aggregation_multi_risk_clause`, potenziell
  `missing_playbook_match` bei fehlenden Wartungsfenstern.

## Position 3 — `GS-03-sla-weich`

- **Profil**: Gegenstück zu Position 2 — standardnahe SLAs: 99,5 %
  monatlich, Wartungsfenster ausgenommen, gedeckelte Vertragsstrafen,
  P1 innerhalb 4 h.
- **Zweck**: Stresstest der **Negativ**-Seite des Matchers — keine dieser
  Klauseln darf zu einem Risk-Finding auf PB-SLA-002 / PB-SLA-004 /
  PB-SLA-005 werden. Misst systematisch den False-Positive-Druck auf
  SLA-Klauseln.
- **Erwartete Fehlerklassen**: idealerweise keine; sonst
  `false_positive_limiting_clause` auf Standard-SLA-Klauseln.

## Position 4 — `GS-04-audit-heavy`

- **Profil**: Vertrag mit ausgeprägtem Audit- und Prüfrechtsblock —
  mehrere Absätze zu Frequenz, Vorlauf, Scope, Drittaudits,
  Mandantenschutz, kostenfreier Unterstützung, Dokumentationspflichten.
- **Zweck**: Testet die Merge-Logik auf Playbook-Identität. Viele
  Obligations matchen teils auf PB-AUDIT-001, teils auf PB-AUDIT-002,
  teils auf PB-AUDIT-003 — und dazu risikoreduzierende Klauseln
  (Mandantenschutz vorhanden). Prüft, ob Info-Klassifikator und
  Merge-Pass sauber entkoppeln.
- **Erwartete Fehlerklassen**:
  `over_aggregation_multi_risk_clause` (Frequenz + Kosten zusammen),
  `wrong_merge` (Drittaudit-Klausel zieht Mandantenschutz mit ein),
  `evidence_misaligned` wegen vieler ähnlicher Absätze.

## Position 5 — `GS-05-incident-bcm-sla-mix`

- **Profil**: Vertrag mit bewusst überlagernden Incident-/BCM-/SLA-
  Klauseln. Beispiel: "Sicherheitsvorfälle sind unverzüglich zu melden.
  Während eines BCM-Falls gelten die SLA weiter." und ähnliche
  Wechselwirkungen.
- **Zweck**: Testet die Cross-Theme-Mechanik. Nach der Hygiene-Änderung
  (`85b6326`) sind Cross-Theme-Findings INFO und ausgeblendet — der
  Vertrag zeigt, wie oft die Cross-Theme-Logik einen **echten**
  Konflikt findet, den wir reviewer-tauglich machen könnten, vs. wie oft
  sie rauscht.
- **Erwartete Fehlerklassen**:
  `reviewer_unfriendly_meta_finding` (vermutlich noch ja),
  `inconsistent_match_across_runs` (Wechselwirkungsklauseln sind
  LLM-instabil), `over_split_same_risk_cluster` bei BCM-Suspension-
  Formulierungen.

## Reihenfolge-Rationale

- **Position 1**: bekannte Basis → erlaubt Vergleich mit bisherigen
  Matrix-Erkenntnissen.
- **Position 2 und 3**: maximaler SLA-Kontrast (hart vs. weich) → deckt
  sowohl False Positives als auch False Negatives auf.
- **Position 4**: Belastet das Merge-/Klassifikator-Zusammenspiel auf
  der Audit-Seite, die bereits eine nicht triviale Signatur-Struktur
  hat.
- **Position 5**: Belastet die Cross-Theme-Mechanik und die
  Lens-übergreifende Konsistenz.

## Minimaler Pfad

Falls nur **drei** Verträge zeitlich möglich sind: Positionen 1, 2 und 4.
Diese drei decken alle Lenses und die drei wichtigsten Fehlerklassen
(FP, Multi-Risk, Merge) ab. Position 3 ist dringend empfohlen als
vierter Vertrag, weil sonst keine systematische False-Positive-Kontrolle
entsteht.

## Quellenhinweis

Die Vertragstexte selbst werden **nicht** ins Repo eingecheckt (außer
`GS-01-kalib`, da als Test-Fixture bereits vorhanden). Pro Vertrag
liegt nur ein `contracts/<id>/meta.md` mit Kurzbeschreibung und ein
`contracts/<id>/expected_clauses.md` mit der manuellen
Kernklausel-Liste (siehe `baseline_procedure.md`).
