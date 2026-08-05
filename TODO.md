# TODO — Split into `ml-delivery-framework` + `data-science-projects`

Tracking doc for the two-repo split. The template-repo-side work below is **done**; what
remains is real-world setup that only the platform team can do (creating the actual
`data-science-projects` repo, cutting a git tag, configuring OIDC).

## Context

`ml-delivery-framework` (https://github.com/Dis-Chem/ml-delivery-framework) is the Databricks Asset
Bundle **template** repo (locked to AWS + GitHub Actions, GitHub OIDC, enforced
`domains/<tribe>/<squad>/` placement, enforced `Project_Only` scaffolding). It contains a
**deployment repo starter kit** at `deployment-repo/` — content meant to be copied into a real,
separate deployment repo, **`data-science-projects`**, which will own squad code, CI/CD, and the
guided notebook that calls out to this template repo to scaffold new projects.

**Confirmed decisions:**
- Kit directory is `deployment-repo/` (staging content for a future repo, not "the monorepo" itself).
- Enforced monorepo path renamed `teams/` → **`domains/<tribe>/<squad>/`** (matches the original
  `.claude/CLAUDE.md` project spec; `domain` stays a governance tag, not a path segment — a domain
  contains multiple tribes).
- dev_qa, UAT, and prod are **three separate Databricks workspaces**, each with its own host and
  OIDC service principal (`DEV_CLIENT_ID` / `STAGING_CLIENT_ID` / `PROD_CLIENT_ID`).
- Template invocation from the notebook pins to a **git tag** via the CLI's native `--tag` flag
  (verified via `databricks bundle init --help`), not a mutable branch like `main`.
- `CICD_Only` mode is kept as an **optional escape hatch** (not removed) — the primary CI/CD path
  for every squad is the shared `deployment-repo/` kit.
- Kedro adoption is confirmed moving forward; serverless compute stays the default (not yet proven
  against a real Kedro workload — tracked as N-09 in the ADR doc).

## Done

- [x] Schema (`databricks_template_schema.json`): `input_root_dir` default →
      `domains/{{.input_tribe}}/{{.input_squad}}`; added `input_databricks_dev_workspace_host`
      (`https://dbc-26cf5e15-d40d.cloud.databricks.com`); tribe/squad/domain descriptions clarified
      (domain = parent grouping of tribes, metadata only); `CICD_Only` description updated to
      "optional escape hatch"
- [x] `library/template_variables.tmpl`: added `databricks_dev_workspace_host` define
- [x] `databricks.yml.tmpl`: `dev` target now uses the dedicated dev_qa host; removed the incorrect
      `mode: development` (caught by the smoke test — it requires a user-scoped `root_path`,
      incompatible with the shared, CI-deployed `dev` target)
- [x] `_params_testing_only.txt.tmpl`: added the new dev host var
- [x] `scripts/smoke-test.sh`, `notebooks/local-testing.ipynb`: `teams/` → `domains/`; stripped
      stale committed outputs from the notebook (nbstripout wasn't applied when it was first written)
- [x] Built `deployment-repo/` for real (it did not previously exist on disk despite earlier
      tracking saying so): `bundles.yml`, `.github/workflows/{monorepo-ci,monorepo-deploy}.yml`,
      `.github/scripts/monorepo_scope.py`, `test-requirements.txt`, `README.md`,
      `notebooks/create-a-project.ipynb` — all using `domains/` paths, three client-ID vars, the
      real template URL, and `--tag TEMPLATE_REF` pinning
- [x] `docs/architecture-decisions.md`: added ADR-16 (repo split); updated ADR-02 (template repo
      needs no OIDC), ADR-03 (three client-ID vars), ADR-05 (Kedro + serverless), ADR-10 (domain/tribe
      hierarchy resolved), ADR-11 (cross-ref ADR-16, `CICD_Only` as escape hatch), ADR-14 (three
      workspaces, corrected), ADR-15 (`deployment-repo/` naming); reworded N-01; added N-09 (Kedro
      compute open question)
- [x] Verified: `pytest tests -q` → 42 passed, 9 skipped; `scripts/smoke-test.sh cdi promo sales`
      passes; `deployment-repo/` YAML + notebook JSON valid; scope script logic correct

## Still to do (real-world setup, not template-repo edits)

- [ ] Create the actual `data-science-projects` GitHub repo
- [ ] Copy `deployment-repo/`'s contents into its root (drop the `deployment-repo/` prefix)
- [ ] Create GitHub OIDC federation policies for `data-science-projects` (one per workspace: dev_qa,
      UAT, prod) and set `DEV_CLIENT_ID` / `STAGING_CLIENT_ID` / `PROD_CLIENT_ID` as Actions variables
- [ ] Register the first project(s) in `bundles.yml`
- [ ] Delete `deployment-repo/` from `ml-delivery-framework` once the copy is confirmed working
- [ ] Cut the first git tag on `ml-delivery-framework` (e.g. `v0.1.0`) — **do not do this silently**,
      confirm explicitly first since pushing a tag is a visible shared-remote action
- [ ] Once a tag exists and `data-science-projects` is live: dry-run
      `databricks bundle init https://github.com/Dis-Chem/ml-delivery-framework --tag <TEMPLATE_REF>
      --config-file <cfg> --output-dir <tmp>` end-to-end

## Feature Store parity for the kedro skeleton

`input_include_feature_store` worked for `mlops_stacks_native` only; it was silently ignored for
`kedro` (see ADR-17 in `docs/architecture-decisions.md`). This section tracks wiring it up for
both skeletons and fixing the generation/smoke tests that didn't contrast FS on vs. off.

- [x] Kedro `feature_engineering` pipeline (`src/<project>/pipelines/feature_engineering/
      {nodes,pipeline,__init__}.py`) + `tests/pipelines/feature_engineering/test_nodes.py`,
      registered in `pipeline_registry.py` only when `input_include_feature_store=yes`
- [x] `conf/base/catalog.yml`/`parameters.yml` FS-conditional entries; `pyproject.toml`
      `databricks-feature-engineering` dependency gated the same way
- [x] `resources/feature-engineering-workflow-resource.yml.tmpl` extended with the
      `input_project_skeleton` conditional (python_wheel_task for kedro, notebook_task for
      native) — same pattern as `model-workflow-resource.yml.tmpl`
- [x] `update_layout.tmpl` skip logic: resource file skip moved out of the native-only branch
      (applies to both skeletons now); new kedro-branch skip for the `feature_engineering`
      pipeline/tests when FS=no
- [x] Schema (`input_project_skeleton` description), ADR-17, project `README.md.tmpl` updated to
      describe the kedro FS path instead of saying it's unsupported
- [x] `tests/test_create_project.py::test_generate_project_check_feature_store_output`
      parametrized across both skeletons
- [x] `scripts/smoke-test.sh` renders Project_Only with FS on **and** off for both skeletons, and
      asserts the feature-engineering file's presence/absence explicitly
- [ ] Verification: run `pytest tests --large -q` and `scripts/smoke-test.sh <tribe> <squad>` and
      confirm both pass (needs the `databricks` CLI + network-free `bundle init`/`validate` —
      not run automatically as part of this edit)
