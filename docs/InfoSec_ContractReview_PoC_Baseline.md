# InfoSec Contract Review – PoC Baseline Stand

**Datum:** 21.04.2026  
**Branch:** `claude/setup-infosec-contract-review-63lK9`  
**Letzter Commit:** `424eee6` (Finding-Classifier + Info-Filter)  
**Server:** IONOS Ubuntu, 217.154.146.110:8002  
**Repository:** github.com/wagnerstefan86-afk/contractclaude

---

## 1. Was das System kann

### End-to-End-Workflow im Browser
Ein Nutzer kann direkt im Browser einen Vertrag hochladen, analysieren lassen und die Ergebnisse reviewen – ohne CLI oder API-Kenntnisse.

**Flow:** Paket anlegen → PDF hochladen → Dokumente parsen → Analyse starten → Findings ansehen → Status ändern → Excel exportieren → Paket löschen

### Analyse-Pipeline
- **PDF/DOCX/XLSX-Parser** mit deterministischem Rule Scanner (Segment-Erkennung, Relevanz-Flags)
- **LLM-basierte Obligation Extraction** via OpenAI GPT-4o mit Structured Outputs
- **2 aktive Linsen:** LENS-AUDIT (Audit- und Prüfungsrechte), LENS-INCIDENT (Incident Reporting und Meldepflichten)
- **Deterministische Nachverarbeitung:** MissingSafeguards, Baseline-Match, Relation Detection, Cross-Theme-Checks, Materiality Scoring
- **Finding-Generierung** mit Connected-Component-Gruppierung und Playbook-Matcher
- **Info/Risk-Klassifikation:** Risikoreduzierende und Standardklauseln werden als "informational" heruntergestuft und im UI/Export ausgeblendet

### UI-Features
- Paketliste mit Status, Findings-Anzahl, letzte Analyse
- Paketdetailseite mit Upload, Parse, Analyse-Aktionen
- Findings-Liste mit Filtern (Thema, Schweregrad, Materialität, Status)
- Finding-Detail mit Beschreibung, Empfehlung, Evidenzen, MissingSafeguards, Review-Aktion
- Deutsche Labels durchgängig (Themes, Severity, Materiality, Status, Dokumenttypen)
- Excel-Export aller Findings (Standard: nur Risk, Optional: inkl. INFO per `?include_info=1`)
- Paket-Löschung inkl. DB-Kaskade und Filesystem-Cleanup
- Info-Banner mit Hinweis auf ausgeblendete informationale Findings

### Technischer Stack
- FastAPI + Jinja2 (Server-Side Rendering)
- PostgreSQL + SQLAlchemy + Alembic (4 Migrationen)
- OpenAI GPT-4o (Structured Outputs, json_schema)
- Docker Compose (Backend, DB, Bootstrap)
- openpyxl (Excel-Export)

---

## 2. Verifizierte Ergebnisse

### Kalibrierungsvertrag (Testvertrag_Kalibrierung_ManagedService_v1.pdf)
Bewusst gestufter Vertrag: MusterBank eG / TechServ GmbH, Managed Workplace Service.

**Letzter Run (21.04.2026):**
- 15 Obligations extrahiert
- 9 Findings generiert (7 Risk, 2 Info)
- 4 Playbook-Matches: PB-AUDIT-001, PB-AUDIT-002, PB-AUDIT-003, PB-INC-003
- 0 MissingSafeguards
- ~4.400 Tokens

**Findings mit Playbook-Match (reviewer-tauglich):**

| Finding | Severity | Playbook | Inhalt |
|---------|----------|----------|--------|
| Unbegrenztes Auditrecht ohne Vorlaufzeit | Hoch | PB-AUDIT-001 | Jederzeit, ohne Ankündigung, inkl. Dritte |
| Direktes Auditrecht für Endkunden/Dritte | Hoch | PB-AUDIT-002 | Standardposition, Eskalationshinweis, Alternativformulierung |
| Kostenfreie Auditunterstützung | Mittel | PB-AUDIT-003 | Kostenfrei + ohne Einschränkung Zugang |
| Regulatorische Meldepflichten durchgereicht | Hoch | PB-INC-003 | DSGVO Art. 33, No-Go-Eskalation |

### AlphaBank-Vertrag (Dienstleistungsvertrag_AlphaBank_SecureNet_ManagedFirewall_v1.pdf)
Realer regulatorischer Vertrag mit KWG, MaRisk, BAIT, DORA-Bezügen.

**Run (20.04.2026):**
- 26 Obligations, 15 Findings
- Deutlich höhere Komplexität, alle Findings Hoch/Hoch
- System reagiert nachweislich auf echtes Vertragsdeutsch

---

## 3. Bekannte Schwächen und Limitierungen

### Finding-Qualität (Kalibrierung)
- **Scope-Begrenzungen teils noch als Risiko:** "Umfang auf Vertragsgegenstand beschränkt" wird als Hoch/Hoch angezeigt statt als Info
- **Einzelne Audit-/Incident-Kerne noch falsch gesplittet:** "Endkunden dürfen eigene Prüfungen" steht separat statt im PB-AUDIT-002-Finding
- **Evidenzverteilung teilweise unsauber:** Regulatorische Meldepflichten und Blanket Event Reporting teilweise in falschen Findings
- **Match-Logik heuristisch und vertragssensitiv:** Substring-basierte Signaturen, keine numerische Fristenlogik

### Architektur / Technische Schulden
- **Starlette 1.0 TemplateResponse:** Muss bei jedem Claude-Code-Commit nachgeprüft werden (neue Signatur: `request=request, name=..., context=...`)
- **Jinja2-Cache:** Muss deaktiviert bleiben (`templates.env.cache = None`)
- **OpenAI Schema:** `time_constraint` erfordert `anyOf` mit `additionalProperties: false`
- **Baseline-Matcher:** Produziert grobe `not_supported`-Signale, Korrektur erfolgt downstream über Classifier
- **Playbook-Key:** Wird aus `risk_pattern` abgeleitet statt stabiler Business-ID
- **ReviewDecision:** unique=True auf finding_id → nur 1 Decision pro Finding statt Audit-Trail
- **Review-Kommentar:** Wird geloggt aber nicht in DB gespeichert
- **Synchrone Verarbeitung:** Parse und Analyse blockieren den Request
- **Keine Fortschrittsanzeige** während der Analyse

### Nicht implementiert
- LENS-SLA (Seed existiert, aber nicht in LLM-Extraktion aktiviert)
- Cross-Theme liefert 0 Kandidaten (braucht SLA-Linse)
- OCR für gescannte PDFs
- Benutzerverwaltung / Authentifizierung
- CSRF-Schutz
- HTTPS / TLS

---

## 4. Seed-Daten

### Linsen (LensConfig)
| ID | Beschreibung | Status |
|----|-------------|--------|
| LENS-AUDIT | Audit- und Prüfungsrechte | Aktiv |
| LENS-INCIDENT | Incident Reporting und Meldepflichten | Aktiv |
| LENS-SLA | SLA-Machbarkeit | Seed vorhanden, nicht aktiviert |

### Playbook-Einträge
| ID | Risiko | Linse |
|----|--------|-------|
| PB-AUDIT-001 | Unbegrenztes Auditrecht ohne Vorlaufzeit/Häufigkeitslimit | AUDIT |
| PB-AUDIT-002 | Direktes Auditrecht für Endkunden oder Dritte | AUDIT |
| PB-AUDIT-003 | Kostenfreie Auditunterstützung | AUDIT |
| PB-INC-001 | Unrealistisch kurze Meldefrist (<2h) | INCIDENT |
| PB-INC-002 | Meldepflicht für jedes Security-Event ohne Schwellenwert | INCIDENT |
| PB-INC-003 | Regulatorische Meldepflichten durchgereicht | INCIDENT |

### Erwartete Schutzmechanismen
13 ExpectedSafeguards über Audit/Incident/SLA (frequency_limit, notice_period, scope_limitation, cost_limit, tenant_protection, time_limit, severity_threshold, escalation_procedure, etc.)

---

## 5. Docker / Deployment

```bash
# Ports (in docker-compose.yml)
DB: 5433:5432
Backend: 8002:8000

# Start
docker compose up -d
# Seeds laden (nach fresh DB)
docker compose run --rm bootstrap

# OPENAI_API_KEY in .env
echo "OPENAI_API_KEY=sk-proj-..." > .env
```

### Wiederkehrende Fixes nach git pull
Falls Claude Code die Dateien überschreibt, müssen diese drei Fixes geprüft werden:
1. `ui.py`: TemplateResponse-Signatur (request=request, name=..., context=...)
2. `ui.py`: templates.env.cache = None
3. `schemas.py`: time_constraint anyOf mit additionalProperties: false
4. `docker-compose.yml`: Ports 5433/8002

Diese Fixes sind seit Commit `a4b9ca5` im Branch. Bei einem `git reset --hard` auf einen älteren Commit gehen sie verloren.

---

## 6. Nächste Phase: Kalibrierung mit Gold-Set

### Vorgehen
Nicht weiter auf einem Einzelvertrag optimieren. Stattdessen systematische Kalibrierung gegen 3-5 verschiedene Vertragstypen.

### Fehlerklassen für das Gold-Set

| Fehlerklasse | Beispiel | Prüfmethode |
|-------------|---------|-------------|
| False Positive bei begrenzenden Klauseln | "Scope auf Vertragsgegenstand beschränkt" als Hoch | Positive Pattern erweitern |
| False Negative bei Drittprüfer-Triggern | Endkunden-Prüfrecht nicht gematcht | Signatur-Gruppen erweitern |
| Falsche Merges | Verschiedene Risikokerne in einem Finding | Merge-Regeln verschärfen |
| Falsche Splits | Gleicher Risikokern als separate Findings | Playbook-ID-Merge prüfen |
| Evidenz-Fehlzuordnung | Evidenz im falschen Finding | LLM-Extraktion + Gruppierung prüfen |
| Severity/Materiality-Drift | Standardklausel als Hoch bewertet | Scoring-Regeln kalibrieren |

### Prioritäten nach PoC

1. **LENS-SLA aktivieren** (Prompt-Template, Cross-Theme-Checks)
2. **Scoring-Kalibrierung** (Severity-Regeln, Materiality-Logik)
3. **Playbook-Key härten** (stabile Business-ID statt risk_pattern-Ableitung)
4. **Fortschrittsanzeige** (Background-Thread + Polling)
5. **Gold-Set aufbauen** (3-5 echte Verträge, manuelle Bewertung)
6. **Governance-Entscheidung** LLM-Provider für Produktion

---

## 7. Commit-Historie (relevant)

| Commit | Beschreibung |
|--------|-------------|
| 424eee6 | Finding-Classifier + Info-Filter |
| e24273f | Playbook-Matcher Kalibrierung + Finding-Dedup |
| 33829b5 | Package-Deletion (DB + Filesystem) |
| a4b9ca5 | Starlette 1.0 Fix, Jinja2 Cache, Schema Fix |
| 5c380cd | Excel-Export |
| b7c4eb8 | Intake-Flow UI + Deutsche Labels |
| 0699cbc | AP7 Materiality Scoring + Finding-Generierung |

---

## 8. Nicht für Produktivbetrieb behaupten

- Keine verlässliche Vollständigkeit der Vertragsprüfung
- Keine stabile Scoring-Kalibrierung über verschiedene Vertragstypen
- Keine breit validierte Match-Qualität
- Kein belastbares Verhalten über verschiedene Vertragstypen hinweg
- Kein Audit-Trail für Review-Entscheidungen
- Keine Authentifizierung, kein CSRF, kein HTTPS

**Dieser Stand ist ein funktionierender PoC, der nachweist, dass KI-gestützte Vertragsprüfung für InfoSec-Governance technisch machbar und fachlich plausibel ist.**
