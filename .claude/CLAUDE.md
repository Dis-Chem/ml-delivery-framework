You are building the XBL MLOps Stacks template repository for X Bigly Labs.
This is a TEMPLATE repo — it is a customised fork of the Databricks MLOps
Stacks template (https://github.com/databricks/mlops-stacks). It is consumed
by running `databricks bundle init <path-to-this-repo>` to scaffold a new
squad project inside the deployment monorepo (xbl-ml-ai-analytics-delivery-platform).

This template repo is NOT a Kedro project itself. It generates the DAB
(Databricks Asset Bundle) scaffolding layer — CI/CD workflows, databricks.yml,
resource configs, and a Kedro project skeleton — when a new squad runs
`databricks bundle init` against it.

## What already exists in this repo
- databricks_template_schema.json (customised — do not overwrite)
- dev-requirements.txt (pinned: pytest==7.4.4, mlflow>=3.1,<4, nbstripout==0.7.1)
- conftest.py (--large / --large-only pytest markers)
- Pipeline.md, stack-customization.md, README.md

## Decisions already made — DO NOT change these
- input_setup_cicd_and_project is enforced to Project_Only for interactive use
- Cloud is locked to AWS
- CI/CD platform is locked to GitHub Actions
- Monorepo path enforced to domains/<tribe>/<squad>/<project_name>
- Staging workspace: https://dbc-9f6e09b3-ca38.cloud.databricks.com
- Prod workspace: https://dbc-cd0b5c83-b24b.cloud.databricks.com
- Default branch: main, release branch: release
- Unity Catalog naming: dev_qa_data_analytics_consumption_dev (test),
  uat_data_analytics_consumption_uat (staging),
  prod_data_analytics_consumption_prod (prod)
- Schema name enforced to <tribe>_<squad>
- Inference table: dev_qa_data_analytics_consumption_dev.<tribe>_<squad>.predictions
- input_include_feature_store defaults to no, but is enabled (input_include_feature_store=yes)
  for BOTH the mlops_stacks_native and kedro project skeletons. Kedro's variant is a
  feature_engineering Kedro pipeline (src/<project>/pipelines/feature_engineering) plus matching
  catalog.yml/parameters.yml entries, in place of native's feature_engineering/ notebook tree.
  Both flavors share the same resources/feature-engineering-workflow-resource.yml job resource —
  its own internal skeleton conditional picks python_wheel_task (kedro run --pipeline
  feature_engineering) vs. notebook_task, the same pattern already used for
  model-workflow-resource.yml/batch-inference-workflow-resource.yml. See ADR-17 in
  docs/architecture-decisions.md.
- Authentication: GitHub OIDC to Databricks service principal (no stored PAT)

## What you need to build inside template/domains/{{.input_tribe}}/{{.input_squad}}/

### 1. Kedro project skeleton (inside the generated project)
Use kedro-databricks conventions. The generated project must contain:

src/{{.input_project_name}}/
  pipelines/
    data_processing/
      nodes.py          # placeholder with docstring explaining node conventions
      pipeline.py       # creates_pipeline() returning an empty Pipeline
    model_training/
      nodes.py
      pipeline.py
    model_inference/
      nodes.py
      pipeline.py
    feature_engineering/   # only present when input_include_feature_store=yes
      nodes.py
      pipeline.py
  pipeline_registry.py  # registers all pipelines; feature_engineering is registered only
                        # inside a {{ if eq .input_include_feature_store "yes" }} guard
  settings.py           # standard Kedro settings

conf/
  base/
    catalog.yml         # placeholder entries with XBL naming conventions
                        # (UC Delta tables, not local CSV)
                        # include commented examples for bronze/silver/gold/output layers
    parameters.yml      # placeholder: test_size, random_state, experiment_name,
                        # registered_model_name — all parameterised, nothing hardcoded
    logging.yml         # disable file-based logging (required for Databricks)
    databricks.yml      # kedro-databricks workflow overrides:
                        # default job_cluster, spark_version, node_type, num_workers
  dev/
    catalog.yml         # override: UC paths pointing at dev_qa catalog
  staging/
    catalog.yml         # override: UC paths pointing at uat catalog

notebooks/
  .gitkeep              # exploration only — comment explaining no production logic here

tests/
  pipelines/
    data_processing/
      test_nodes.py     # placeholder unit test structure
    model_training/
      test_nodes.py
    model_inference/
      test_nodes.py

pyproject.toml          # kedro + kedro-databricks + kedro-mlflow + mlflow>=3.1,<4
                        # ruff linting config
                        # pytest config

### 2. DAB layer (generated alongside the Kedro project)
databricks.yml          # main bundle config — DO NOT use mode: development defaults
                        # dev target must have:
                        #   run_as: service_principal_name: ${var.sp_name}
                        #   presets: name_prefix: ""  (no [dev username] prefixing)
                        #   workspace.root_path: /Shared/.bundle/dev/${bundle.name}
                        # staging and prod targets wired to correct workspace hosts
                        # variables block: sp_name (no default, must be supplied)

resources/
  model_training_job.yml    # Databricks Workflow job for training pipeline
                            # task: python_wheel_task calling kedro run
                            # --pipeline model_training --env ${bundle.target}
  model_inference_job.yml   # Databricks Workflow job for inference pipeline
  mlflow_experiment.yml     # MLflow experiment resource, path uses UC schema
  mlflow_model.yml          # Registered model in UC under <catalog>.<schema>.<model>

### 3. GitHub Actions CI/CD workflows
.github/workflows/
  ci.yml                # triggers on PR to main:
                        # - pytest + ruff (lint) — blocks merge on failure
                        # - databricks bundle validate -t dev
                        # - static check: grep for hardcoded local paths
                        # authenticates via OIDC (no stored PAT)
                        # uses: databricks/run-notebook or databricks CLI action
  cd_dev.yml            # triggers on merge to main:
                        # - kedro package (builds .whl)
                        # - databricks bundle deploy -t dev
                        # - authenticated as service principal via OIDC
  cd_staging.yml        # triggers on merge to release branch:
                        # - databricks bundle deploy -t staging

### 4. Template-level tests (not the generated project's tests)
tests/
  test_schema.py        # validates databricks_template_schema.json is valid JSON
                        # and all skip_prompt_if logic resolves without error
  test_generation.py    # runs `databricks bundle init .` with test config values
                        # and asserts the expected output directory structure exists
                        # and `databricks bundle validate -t dev` passes on output

### 5. Developer tooling
.devcontainer/
  devcontainer.json     # Python 3.11, Databricks CLI v0.236.0+,
                        # pip install -r dev-requirements.txt on create
  Dockerfile            # FROM python:3.11-slim, install CLI + dev deps

Makefile                # targets:
                        # make test       → pytest tests/
                        # make lint       → ruff check .
                        # make generate   → databricks bundle init . --config-file test_config.json
                        # make validate   → cd generated output && databricks bundle validate -t dev

## Conventions to enforce throughout all generated files
- NO hardcoded local file paths anywhere (catalog.yml must use UC paths or DBFS)
- NO hardcoded user emails or personal workspace paths
- NO mlflow.set_experiment() with personal user paths — must use parameters.yml value
- Inference pipeline must load from models:/<name>/latest (registry), not runs:/<id>/...
- All environment-specific values live in conf/<env>/ overrides, not conf/base/
- run_id must flow through the Kedro Data Catalog between training and evaluation,
  never as a live Python variable

## Do not do these things
- Do not run databricks bundle init against a live workspace (no network access needed)
- Do not create a requirements.txt — use pyproject.toml only
- Do not scaffold staging/prod Databricks Workflow runs — dev target only for PoC
- Do not generate notebooks with production logic — notebooks/ is exploration only

## Definition of done for this prompt
Running `make generate && make validate` from the repo root must:
1. Generate a project at domains/example_tribe/example_squad/example_tribe_example_squad/
2. Pass `databricks bundle validate -t dev` on the generated output (offline validation only)
3. Pass `pytest tests/` at the template level
4. Pass `ruff check .` with zero errors

Start by reading the existing databricks_template_schema.json to understand the
current parameter structure before writing any new files.