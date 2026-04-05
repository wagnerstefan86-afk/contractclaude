#!/usr/bin/env bash
set -e

echo "Running Alembic migrations ..."
python -m infosec_contract_review.scripts.create_db

echo "Loading seed data ..."
python -m infosec_contract_review.scripts.seed_db

echo "Bootstrap complete."
