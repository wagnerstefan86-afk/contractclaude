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

## Bootstrap: Datenbank einrichten

### Voraussetzungen

- Python 3.11+
- PostgreSQL 15+ (lokal oder remote)
- Die Datenbank `contract_review` muss existieren

### Installation

```bash
pip install -r requirements.txt
```

### Umgebungsvariablen

| Variable       | Default                                                      | Beschreibung         |
|----------------|--------------------------------------------------------------|----------------------|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/contract_review` | SQLAlchemy-DB-URL |

Beispiel:

```bash
export DATABASE_URL="postgresql://user:pass@host:5432/contract_review"
```

### Postgres-Datenbank anlegen (falls noch nicht vorhanden)

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

Erwartete Ausgabe:

```
INFO  Seed loading complete. Summary:
INFO    provider_baseline           X records
INFO    lens_configs                X records
INFO    cross_theme_rules           X records
INFO    playbook_entries            X records
```

Ein zweiter Lauf aktualisiert bestehende Datensätze (Upsert), erzeugt keine Duplikate.

### Datenbank zurücksetzen (nur lokal!)

```bash
python -m infosec_contract_review.scripts.reset_db
```

Löscht alle Tabellen, führt Migration erneut aus und lädt Seeds.

### Seed-Dateien

Alle Fachkonfigurationen liegen in `infosec_contract_review/seed/`:

| Datei                    | Inhalt                                  |
|--------------------------|-----------------------------------------|
| `provider_baseline.yaml` | Provider-Baseline inkl. Zertifizierungen |
| `lens_configs.yaml`      | Analyse-Linsen + Expected Safeguards     |
| `cross_theme_rules.yaml` | Themenübergreifende Prüfregeln          |
| `playbook_v1.yaml`       | Verhandlungs-Playbook                   |
| `rule_scan_config.yaml`  | Platzhalter für Rule Scanner            |
