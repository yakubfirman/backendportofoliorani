#!/bin/bash
set -euo pipefail

echo "Setting up backend environment for PythonAnywhere..."

# Create a virtualenv in the user's home venv folder
PY_VENV=~/venv/pa-venv
python3.10 -m venv "$PY_VENV" || python3 -m venv "$PY_VENV"
source "$PY_VENV/bin/activate"

pip install --upgrade pip
pip install -r requirements.txt

# Ensure uploads folder exists
mkdir -p uploads

# Run DB initialization and seed data
python3 app.py

echo "Setup complete. Configure Web tab and WSGI as documented in DEPLOY_PYTHONANYWHERE.md"
