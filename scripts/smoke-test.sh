#!/usr/bin/env bash
#
# Offline smoke test for the ML delivery template.
#
# Renders the template locally with the Databricks CLI and checks the generated
# stack WITHOUT needing a Databricks workspace or authentication. Use it before
# committing template changes, or to preview what a new squad project looks like.
#
# Usage:
#   scripts/smoke-test.sh [tribe] [squad] [domain]
#
# Examples:
#   scripts/smoke-test.sh                      # example_tribe / example_squad / example_domain
#   scripts/smoke-test.sh cdi promo sales      # a real squad's scaffold
#
# What it does (all offline), for BOTH project skeletons (mlops_stacks_native and kedro):
#   1. Renders the enforced monorepo flow (Project_Only) into a temp dir, for BOTH
#      feature_store settings ("yes"/"no") so the toggle is actually contrasted.
#   2. Renders the CI/CD bootstrap (CICD_and_Project) into a temp dir (feature_store=yes),
#      so the GitHub Actions workflows are exercised too.
#   3. Fails on any leftover {{ ... }} template markers (un-rendered Go template), and
#      asserts Feature Store scaffolding is present/absent as expected for both skeletons.
#   4. Parses every generated YAML file to confirm it is well-formed.
#   5. Runs `databricks bundle validate` best-effort — a missing-credentials
#      error is expected offline and is treated as a pass; any schema/config
#      error fails the smoke test.
#   6. Lists TODO_ placeholders that still need real values (informational).
#
set -euo pipefail

TRIBE="${1:-example_tribe}"
SQUAD="${2:-example_squad}"
DOMAIN="${3:-example_domain}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Output is kept under tmp/ (git-ignored) so you can inspect the generated stack.
WORK="$REPO_ROOT/tmp/smoke-test"
rm -rf "$WORK"; mkdir -p "$WORK"

RED=$'\033[31m'; GRN=$'\033[32m'; YLW=$'\033[33m'; DIM=$'\033[2m'; RST=$'\033[0m'
fail() { echo "${RED}✗ $*${RST}"; exit 1; }
pass() { echo "${GRN}✓ $*${RST}"; }
info() { echo "${DIM}  $*${RST}"; }

command -v databricks >/dev/null || fail "databricks CLI not found on PATH"
echo "Databricks CLI: $(databricks --version)"
echo "Squad identity: ${TRIBE}/${SQUAD} (domain: ${DOMAIN})"
echo

# ---------------------------------------------------------------------------
# render <mode> <output-subdir> <skeleton> <feature_store>
# ---------------------------------------------------------------------------
render() {
  local mode="$1" out="$WORK/$2" skeleton="$3" fs="$4" cfg="$WORK/$2.json"
  cat > "$cfg" <<EOF
{
  "input_setup_cicd_and_project": "${mode}",
  "input_tribe": "${TRIBE}",
  "input_squad": "${SQUAD}",
  "input_domain": "${DOMAIN}",
  "input_include_feature_store": "${fs}",
  "input_project_skeleton": "${skeleton}"
}
EOF
  mkdir -p "$out"
  if ! databricks bundle init "$REPO_ROOT" --config-file "$cfg" --output-dir "$out" >"$out/.init.log" 2>&1; then
    cat "$out/.init.log"; fail "template render failed for ${mode} (${skeleton}, feature_store=${fs})"
  fi
  pass "rendered ${mode} (${skeleton}, feature_store=${fs})"
}

# ---------------------------------------------------------------------------
# 1 + 2: render both flows, for both project skeletons, with Feature Store
# on AND off for Project_Only so both settings are actually contrasted.
# ---------------------------------------------------------------------------
render "Project_Only"     "project_only_native_fs"   "mlops_stacks_native" "yes"
render "Project_Only"     "project_only_native_nofs" "mlops_stacks_native" "no"
render "Project_Only"     "project_only_kedro_fs"    "kedro"               "yes"
render "Project_Only"     "project_only_kedro_nofs"  "kedro"               "no"
render "CICD_and_Project" "with_cicd_native"         "mlops_stacks_native" "yes"
render "CICD_and_Project" "with_cicd_kedro"          "kedro"               "yes"

# ---------------------------------------------------------------------------
# 3: no un-rendered Go template markers leaked into the output
# ---------------------------------------------------------------------------
# A rendered file may LEGITIMATELY contain {{ ... }}:
#   - GitHub Actions expressions render to  ${{ ... }}   (preceded by $)
#   - Databricks job task-values use        {{tasks...}} (starts with a word)
# A genuine leak is un-rendered *Go template* syntax, so we look only for that:
# {{ .field, {{ template, {{ if/range/end/else/with/define, {{ print/fail/regexp, {{ bundle_uuid.
LEAK_RE='(?<!\$)\{\{-?\s*(\.|template\b|if\b|range\b|end\b|else\b|with\b|define\b|print\b|fail\b|regexp\b|bundle_uuid\b)'
leaks="$(grep -rIlP "$LEAK_RE" "$WORK" 2>/dev/null | grep -v '/\.init\.log$' || true)"
if [ -n "$leaks" ]; then
  echo "$leaks" | sed 's/^/  /'
  fail "found un-rendered Go template markers in generated files"
fi
pass "no un-rendered template markers"

# ---------------------------------------------------------------------------
# 3b: Feature Store scaffolding is present iff input_include_feature_store=yes,
# for BOTH skeletons.
# ---------------------------------------------------------------------------
NATIVE_FS_FILE="feature_engineering/GenerateAndWriteFeatures.py"
KEDRO_FS_FILE="src/${TRIBE}_${SQUAD}/pipelines/feature_engineering/nodes.py"
BUNDLE_SUBPATH="domains/${TRIBE}/${SQUAD}/${TRIBE}_${SQUAD}"

assert_fs_present() {
  local label="$1" path="$2"
  [ -f "$path" ] || fail "expected Feature Store file missing ($label): $path"
}
assert_fs_absent() {
  local label="$1" path="$2"
  [ ! -f "$path" ] && return
  fail "unexpected Feature Store file present ($label): $path"
}

assert_fs_present "native, feature_store=yes" "$WORK/project_only_native_fs/${BUNDLE_SUBPATH}/${NATIVE_FS_FILE}"
assert_fs_absent  "native, feature_store=no"  "$WORK/project_only_native_nofs/${BUNDLE_SUBPATH}/${NATIVE_FS_FILE}"
assert_fs_present "kedro, feature_store=yes"  "$WORK/project_only_kedro_fs/${BUNDLE_SUBPATH}/${KEDRO_FS_FILE}"
assert_fs_absent  "kedro, feature_store=no"   "$WORK/project_only_kedro_nofs/${BUNDLE_SUBPATH}/${KEDRO_FS_FILE}"
pass "Feature Store scaffolding present/absent as expected, for both skeletons"

# ---------------------------------------------------------------------------
# 4: every generated YAML parses
# ---------------------------------------------------------------------------
if python3 - "$WORK" <<'PY'
import sys, glob, os
root = sys.argv[1]
try:
    import yaml
except ImportError:
    print("  (pyyaml not installed — skipping YAML parse check)"); sys.exit(0)
bad = 0
for f in glob.glob(os.path.join(root, "**", "*.yml"), recursive=True) + \
         glob.glob(os.path.join(root, "**", "*.yaml"), recursive=True):
    try:
        list(yaml.safe_load_all(open(f)))
    except Exception as e:
        print(f"  INVALID YAML: {f}\n    {e}"); bad += 1
sys.exit(1 if bad else 0)
PY
then pass "all generated YAML is well-formed"
else fail "invalid YAML in generated output"
fi

# ---------------------------------------------------------------------------
# 5: bundle validate (best effort, offline) — both skeletons
# ---------------------------------------------------------------------------
validate_bundle() {
  local label="$1" bundle_dir="$2"
  if [ ! -d "$bundle_dir" ]; then
    fail "expected bundle dir not generated ($label): $bundle_dir"
  fi
  local out
  out="$(cd "$bundle_dir" && databricks bundle validate -t dev 2>&1 || true)"
  if echo "$out" | grep -qiE 'cannot configure default credentials|default auth|failed to fetch host metadata'; then
    pass "bundle config validated up to the auth boundary ($label, offline OK)"
  elif echo "$out" | grep -qiE '^Error:'; then
    echo "$out" | sed 's/^/  /'; fail "bundle validate reported a config/schema error ($label)"
  else
    pass "bundle validate clean ($label)"
  fi
}
validate_bundle "native, feature_store=yes" "$WORK/project_only_native_fs/${BUNDLE_SUBPATH}"
validate_bundle "native, feature_store=no"  "$WORK/project_only_native_nofs/${BUNDLE_SUBPATH}"
validate_bundle "kedro, feature_store=yes"  "$WORK/project_only_kedro_fs/${BUNDLE_SUBPATH}"
validate_bundle "kedro, feature_store=no"   "$WORK/project_only_kedro_nofs/${BUNDLE_SUBPATH}"

# ---------------------------------------------------------------------------
# 6: TODO placeholders still to fill (informational)
# ---------------------------------------------------------------------------
todos="$(grep -rho 'TODO_[A-Za-z_]*' "$WORK"/project_only_* 2>/dev/null | sort -u || true)"
if [ -n "$todos" ]; then
  echo
  echo "${YLW}Placeholders still needing real values:${RST}"
  echo "$todos" | sed 's/^/  · /'
fi

echo
echo "${GRN}SMOKE TEST PASSED${RST}"
echo "Generated stacks kept for inspection at:"
echo "  ${DIM}$WORK/project_only_native_fs${RST}   (Project_Only, mlops_stacks_native, feature_store=yes)"
echo "  ${DIM}$WORK/project_only_native_nofs${RST} (Project_Only, mlops_stacks_native, feature_store=no)"
echo "  ${DIM}$WORK/project_only_kedro_fs${RST}    (Project_Only, kedro, feature_store=yes)"
echo "  ${DIM}$WORK/project_only_kedro_nofs${RST}  (Project_Only, kedro, feature_store=no)"
echo "  ${DIM}$WORK/with_cicd_native${RST}         (CICD_and_Project, mlops_stacks_native skeleton)"
echo "  ${DIM}$WORK/with_cicd_kedro${RST}          (CICD_and_Project, kedro skeleton)"
