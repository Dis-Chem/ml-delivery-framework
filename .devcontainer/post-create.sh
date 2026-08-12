#!/usr/bin/env bash
set -euo pipefail

# Navigate to the project repository root relative to this script
cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "Upgrading package managers and tools..."
python -m pip install --upgrade pip
pip install databricks-cli
pip install -r dev-requirements.txt

echo "Post-create environment configuration completed successfully!"