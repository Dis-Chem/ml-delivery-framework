#!/usr/bin/env bash
set -euo pipefail

# Navigate to the project repository root relative to this script
cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "Creating Python virtual environment..."
# Initialize an isolated virtual environment matching the container's Python 3.12
uv venv .venv

echo "Installing project and development dependencies from pyproject.toml..."
# Fast-install the local project in editable mode along with its 'dev' dependency group
uv pip install --python .venv/bin/python -e .[dev]

echo "Installing complementary CLI tools..."
# Install complementary dependencies inside the virtual environment
uv pip install --python .venv/bin/python databricks

echo "Post-create environment configuration completed successfully!"
