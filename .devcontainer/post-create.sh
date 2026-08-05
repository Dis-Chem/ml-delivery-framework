#!/usr/bin/env bash
# Provision the dev container with the tooling the MLOps Stacks test suite needs.
# Mirrors versions used in .github/workflows/run-checks.yaml so local runs match CI.
set -euo pipefail

DATABRICKS_CLI_VERSION="0.236.0"   # min_databricks_cli_version in databricks_template_schema.json
ACT_VERSION="v0.2.89"              # pinned in run-checks.yaml

echo ">>> Installing Python dependencies (dev-requirements.txt)"
python -m pip install --upgrade pip
pip install -r dev-requirements.txt

echo ">>> Installing Databricks CLI v${DATABRICKS_CLI_VERSION}"
if command -v databricks >/dev/null 2>&1; then
  echo "    databricks already on PATH ($(databricks --version)); skipping."
else
  # Reuse the repo's checksum-verified installer.
  TMP_DBX="$(mktemp -d)"
  bash tests/install.sh "$TMP_DBX"
  sudo mv "$TMP_DBX/databricks" /usr/local/bin/databricks
  rm -rf "$TMP_DBX"
  databricks --version
fi

echo ">>> Installing act ${ACT_VERSION}"
if ! command -v docker >/dev/null 2>&1; then
  # `act` only works with a Docker daemon. Skip unless the docker-in-docker
  # feature is enabled in devcontainer.json (the `act` test is --large-only).
  echo "    No Docker daemon detected; skipping act (enable docker-in-docker to run 'pytest tests --large')."
elif command -v act >/dev/null 2>&1; then
  echo "    act already on PATH; skipping."
else
  OS="$(uname -s)"
  ARCH="$(uname -m)"
  case "$ARCH" in
    x86_64|amd64) ACT_ARCH="x86_64" ;;
    arm64|aarch64) ACT_ARCH="arm64" ;;
    *) echo "Unsupported architecture for act: $ARCH" >&2; exit 1 ;;
  esac
  ACT_TARBALL="act_${OS}_${ACT_ARCH}.tar.gz"
  BASE_URL="https://github.com/nektos/act/releases/download/${ACT_VERSION}"

  TMP_ACT="$(mktemp -d)"
  curl -fsSL -o "${TMP_ACT}/${ACT_TARBALL}" "${BASE_URL}/${ACT_TARBALL}"
  # Verify against the release's published checksums file before use.
  curl -fsSL -o "${TMP_ACT}/checksums.txt" "${BASE_URL}/checksums.txt"
  (cd "$TMP_ACT" && grep " ${ACT_TARBALL}\$" checksums.txt | sha256sum -c -)
  tar -xzf "${TMP_ACT}/${ACT_TARBALL}" -C "$TMP_ACT" act
  sudo mv "${TMP_ACT}/act" /usr/local/bin/act
  rm -rf "$TMP_ACT"
  act --version
fi

echo ">>> Dev container ready. Try: pytest tests   (add --large for integration tests)"
