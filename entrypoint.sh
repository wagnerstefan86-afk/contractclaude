#!/usr/bin/env bash
set -e

echo "Running Alembic migrations ..."
python -m infosec_contract_review.scripts.create_db 2>&1

echo "Loading seed data ..."
python -m infosec_contract_review.scripts.seed_db 2>&1

echo "Bootstrap complete."
