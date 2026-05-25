#!/usr/bin/env bash
set -euo pipefail
# Create a virtual environment in this folder, install requirements, and run the app
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r ../requirements.txt
python ../server.py
