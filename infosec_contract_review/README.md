# InfoSec Contract Review – PoC

## Status: PoC (Proof of Concept)

Dieses Repository enthält das Datenmodell, die API-Verträge und die
Fachkonfigurationen für den 6-Wochen-PoC. Es ist kein produktionsreifes
System, sondern die technische Grundlage für einen kontrollierten Test.

## Voraussetzungen für den Start

1. Governance-Freigabe: LLM-Provider, Datenfluss, Logging, Retention
2. Gold-Set: 3 Vertragspakete manuell geprüft, Findings im Zielschema
3. Playbook v1: 30+ kuratierte Einträge aus echten Altprüfungen
4. Provider Baseline: Bestätigt durch InfoSec-Leitung

---

## Bootstrap mit Docker Compose

### Vorbereitung

```bash
cp .env.example .env   # optional, docker-compose.yml hat eigene Defaults
```

### Starten

```bash
docker compose build
docker compose up
```

Der `bootstrap`-Container führt automatisch Migration und Seeding aus und
beendet sich. Postgres bleibt laufen.

### YAML-Änderungen ohne Rebuild übernehmen

Das Seed-Verzeichnis ist beim `bootstrap`-Service als Read-only-Volume
gemountet:

```
./infosec_contract_review/seed  →  /app/infosec_contract_review/seed:ro
```

Eine geänderte YAML-Datei auf dem Host ist beim nächsten Lauf sofort
wirksam – kein `docker compose build` erforderlich:

```bash
# YAML auf dem Host ändern, dann:
docker compose run --rm bootstrap
```

### Datenbank zurücksetzen

```bash
docker compose down -v   # löscht auch das Postgres-Volume
docker compose up --build
```

---

## Lokale Entwicklung ohne Docker

### Voraussetzungen

- Python 3.11+
- PostgreSQL 15+

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Umgebungsvariablen

```bash
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/contract_review"
```

Alle verfügbaren Variablen sind in `.env.example` dokumentiert.

### Datenbank anlegen

```bash
createdb contract_review
```

### Migration ausführen

```bash
python -m infosec_contract_review.scripts.create_db
```

Oder direkt via Alembic:

```bash
alembic upgrade head
```

Erwartete Ausgabe:

```
INFO  [alembic.runtime.migration] Running upgrade  -> 0001, initial schema - all domain tables
```

### Seed-Daten laden

```bash
python -m infosec_contract_review.scripts.seed_db
```

Erwartete Ausgabe und Counts:

```
INFO  Seed loading complete. Summary:
INFO    provider_baseline         10 records   (1 Baseline + 1 Cert + 5 StdPos + 3 ServiceProfiles)
INFO    lens_configs              16 records   (3 Lenses + 13 ExpectedSafeguards)
INFO    cross_theme_rules          3 records   (CTR-001, CTR-002, CTR-003)
INFO    playbook_entries           9 records   (PB-AUDIT-001–003, PB-INC-001–003, PB-SLA-001–003)
```

Ein zweiter Lauf aktualisiert bestehende Datensätze (Upsert), erzeugt keine Duplikate.

### Datenbank zurücksetzen (nur lokal!)

```bash
python -m infosec_contract_review.scripts.reset_db
```

**Achtung:** `reset_db` löscht alle Tabellen ohne Sicherheitsabfrage und ist
ausschließlich für die lokale Entwicklung gedacht.

---

## Seed-Dateien

Alle Fachkonfigurationen liegen in `infosec_contract_review/seed/`:

| Datei                    | Inhalt                                           | Records |
|--------------------------|--------------------------------------------------|---------|
| `provider_baseline.yaml` | Provider-Baseline, Zertifizierungen, Positionen  | 10      |
| `lens_configs.yaml`      | 3 Analyse-Linsen + 13 Expected Safeguards        | 16      |
| `cross_theme_rules.yaml` | 3 themenübergreifende Prüfregeln                 | 3       |
| `playbook_v1.yaml`       | 9 Verhandlungs-Playbook-Einträge                 | 9       |
| `rule_scan_config.yaml`  | Platzhalter für Rule Scanner                     | –       |

### Lens-Übersicht

| Lens-ID        | Theme              | Safeguards |
|----------------|--------------------|------------|
| LENS-AUDIT     | audit_rights       | 6          |
| LENS-INCIDENT  | incident_reporting | 2          |
| LENS-SLA       | sla_feasibility    | 5          |
