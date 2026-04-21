# Referenzfälle aus bisherigen Läufen

Diese Fälle wurden im Zuge der ersten Kalibrierung auf dem
Kalibrierungsvertrag beobachtet (Branch-Stand bis `85b6326`). Sie dienen
als **Eichmuster** für Reviewer und als Katalog der typischen
Verhaltensklassen der Pipeline. **Keine Pipeline-Änderung** wird auf Basis
dieses Dokuments vorgenommen — Phase 2 entscheidet auf Grundlage der
Gold-Set-Matrix, welche Muster tatsächlich problematisch sind.

Jeder Fall hat:
- **Typ** (korrespondiert zu einer Fehlerklasse aus `error_classes.md`)
- **Kurzbeschreibung** der Beobachtung
- **Beobachtetes aktuelles Verhalten**
- **Hinweis**, wie in der Bewertungsmatrix zu kennzeichnen

---

## Fall 1 — Scope-begrenzende Klausel fälschlich als Risk-Finding
**Typ**: `false_positive_limiting_clause`
**Klausel**: "Der Auditumfang ist auf den Vertragsgegenstand beschränkt."
**Aktuelles Verhalten**: Nach der Klassifikator-Änderung (`424eee6`) wird
sie als `[Informativ]` geführt und im UI-Default ausgeblendet, sofern der
Matcher sie nicht in die große PB-AUDIT-001-Gruppe zieht.
**Matrix-Kennzeichnung**: `expected_outcome=info`, `actual_outcome` je
nach Merge-Verhalten. Wenn sie in der PB-AUDIT-001-Gruppe als Evidenz
landet, zusätzlich `error_class=wrong_merge` oder
`mixed_risk_core` je nach Titel/Empfehlung.

---

## Fall 2 — Drittaudit / Endkundenprüfung teils doppelt, teils zu breit gemerged
**Typ**: `wrong_merge` oder `wrong_split`, je nach Lauf
**Klausel**: "Drittprüfer können ohne vorherige Ankündigung eingesetzt
werden." vs. "Endkunden des Auftraggebers haben direkten Zugang."
**Aktuelles Verhalten**: Beide matchen auf PB-AUDIT-002 und werden
per Playbook-ID zusammengeführt. Sinnvoll, wenn es derselbe Risikokern
(Drittaudit) ist. Wenn Endkunden-Auditrecht aber eigene Verhandlungs-
dimension bildet → `over_aggregation_multi_risk_clause` erwägen.
**Matrix-Kennzeichnung**: bei sauber zusammengehörigen Klauseln `ok`,
sonst `over_aggregation_multi_risk_clause` mit Kommentar zu den zwei
Verhandlungshebeln.

---

## Fall 3 — Verfügbarkeit 99,99 % + Vertragsstrafe in einem Finding
**Typ**: `over_aggregation_multi_risk_clause`
**Klausel-Kombination**: "Verfügbarkeit 99,99 % monatlich. Bei Unterschreitung
fällt eine unbegrenzte Vertragsstrafe an."
**Aktuelles Verhalten**: LENS-SLA extrahiert typischerweise **eine**
Obligation, die beides beschreibt, weil der Klauseltext beides im
selben Absatz enthält. Der Matcher mapt dann auf **ein** Playbook
(i. d. R. PB-SLA-002 wegen 99,99 %). PB-SLA-005 (ungedeckelte Strafe)
bleibt unsichtbar.
**Matrix-Kennzeichnung**: `error_class=over_aggregation_multi_risk_clause`,
`keep_merge_split_decision=split`, Kommentar: "zwei Playbook-Kerne:
SLA-002 + SLA-005".

---

## Fall 4 — Reaktionszeiten P1/P2/P3 zu fein aufgesplittet
**Typ**: `over_split_same_risk_cluster`
**Klausel**: "P1 15 Min / P2 4 h / P3 8 h" jeweils in drei Einzelzeilen
einer Tabelle.
**Aktuelles Verhalten**: LENS-SLA erzeugt möglicherweise drei Obligations
für P1, P2, P3. PB-SLA-004-Matching greift nur bei P1 (15 Min als
Tight-Time-Marker), P2 und P3 bleiben ohne Playbook und werden als
separate Findings geführt.
**Matrix-Kennzeichnung**: `error_class=over_split_same_risk_cluster`,
`keep_merge_split_decision=merge_with:<P1-finding_id>`, Kommentar:
"gleicher Risikocluster Reaktionszeit-Matrix, P1 führt den Cluster".

---

## Fall 5 — Wartungsfenster materiell, aber ohne Playbook
**Typ**: `missing_playbook_match`
**Klausel**: "Geplante Wartungsfenster sind nicht explizit von der
SLA-Messung ausgenommen."
**Aktuelles Verhalten**: PB-SLA-001 hat `min_support_hits=2` (wartung +
ausgenommen/fehlt). Wenn der LLM das Fehlen nicht explizit formuliert,
sondern nur die SLA-Klausel ohne Ausnahme zitiert, matcht die Signatur
nicht → Finding ohne Playbook, obwohl PB-SLA-001 fachlich passt.
**Matrix-Kennzeichnung**: `error_class=missing_playbook_match`, Kommentar:
"PB-SLA-001 wäre inhaltlich korrekt, Signatur zu eng".

---

## Fall 6 — Match-Verhalten zwischen zwei Läufen nicht stabil genug
**Typ**: `inconsistent_match_across_runs`
**Klausel**: identische Obligation, zwei Runs am selben Vertrag.
**Aktuelles Verhalten**: Die Obligation-Extraktion ist LLM-basiert und
kann leicht unterschiedliche `summary`-Texte produzieren. Das reicht
aus, damit z. B. PB-SLA-001 einmal matcht und einmal nicht, oder dass
der Klassifikator eine Klausel einmal als `informational` und einmal als
`risk` einstuft.
**Matrix-Kennzeichnung**: nur beim zweiten Run eines Vertrags relevant;
`error_class=inconsistent_match_across_runs` + Kommentar "Run A: …,
Run B: …".

---

## Fall 7 — Cross-Theme-Meta-Findings (historisch)
**Typ**: `reviewer_unfriendly_meta_finding`
**Aktuelles Verhalten**: Seit Commit `85b6326` bekommen Cross-Theme-
Findings `severity=INFO` und fallen aus der Default-Ansicht. Sie sind
nur noch über `?include_info=1` sichtbar.
**Matrix-Kennzeichnung**: bei Beibehaltung im Info-Bucket `ok`; falls
englischer Rationale-Text im `?include_info=1`-View weiterhin stört,
`error_class=reviewer_unfriendly_meta_finding` mit Kommentar.

---

## Nutzung

Diese Liste ist **nicht abschließend**. Beim Bewerten neuer Verträge
können weitere Muster entstehen. Neue, wiederkehrende Muster werden hier
ergänzt, **bevor** eine Pipeline-Änderung erwogen wird. Das hält die
Taxonomie stabil und verhindert Ad-hoc-Tuning auf Einzelklauseln.
