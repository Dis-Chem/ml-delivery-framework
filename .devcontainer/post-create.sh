#!/usr/bin/env bash
set -euo pipefail

# Navigate to the project repository root relative to this script
cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "Creating Python virtual environment..."
# 2. Initialize an isolated virtual environment matching the container's Python 3.12
uv venv

# 2. Activate the virtual environment for the rest of the script
source .venv/bin/activate

echo "Installing project and development dependencies from pyproject.toml..."
# 3. Fast-install the local project in editable mode along with its 'dev' dependency group
uv pip install -e .[dev]

echo "Installing complementary CLI tools..."
# 4. Install complementary dependencies inside the virtual environment
uv pip install databricks

echo "Post-create environment configuration completed successfully!"
