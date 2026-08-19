# X, Bigly Labs ML Delivery Framework

> Based on [Databricks MLOps Stacks](https://docs.databricks.com/en/dev-tools/bundles/mlops-stacks.html) — customized for X, Bigly Labs with org-specific workflows and deployment targets.

This repo provides a customizable stack for starting new ML projects
on Databricks that follow production best-practices out of the box.

Using this ML Delivery Framework, data scientists can quickly get started iterating on ML code for new projects while ML engineers configure ML resources and model lifecycle management. This is a customized fork with org-specific domains, catalogs, and branch naming conventions pre-configured. More information on the base MLOps Stacks pattern can be found at https://docs.databricks.com/en/dev-tools/bundles/mlops-stacks.html.

The default stack in this repo includes two primary modular components: 

| Component                   | Description                                                                                                                                                           | Why it's useful                                                                                                                                                                         |
|-----------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [ML Code](template/{{.input_root_dir}}/{{template%20`project_name_alphanumeric_underscore`%20.}}/)                     | Example ML project structure ([training](template/{{.input_root_dir}}/{{template%20`project_name_alphanumeric_underscore`%20.}}/training) and [batch inference](template/{{.input_root_dir}}/{{template%20`project_name_alphanumeric_underscore`%20.}}/deployment/batch_inference), etc), with unit tested Python modules and notebooks                                                                                           | Quickly iterate on ML problems, without worrying about refactoring your code into tested modules for productionization later on.                                                        |
| [ML Resources as Code](template/{{.input_root_dir}}/{{template%20`project_name_alphanumeric_underscore`%20.}}/resources) | ML pipeline resources ([training](template/{{.input_root_dir}}/{{template%20`project_name_alphanumeric_underscore`%20.}}/resources/model-workflow-resource.yml.tmpl) and [batch inference](template/{{.input_root_dir}}/{{template%20`project_name_alphanumeric_underscore`%20.}}/resources/batch-inference-workflow-resource.yml.tmpl) jobs, etc) defined through [databricks CLI bundles](https://docs.databricks.com/dev-tools/cli/bundle-cli.html)    | Govern, audit, and deploy changes to your ML resources (e.g. "use a larger instance type for automated model retraining") through pull requests, rather than adhoc changes made via UI. |

See the [FAQ](#FAQ) for questions on common use cases.

## ML pipeline structure and development loops

An ML solution comprises data, code, and models. These resources need to be developed, validated (staging), and deployed (production). In this repository, we use the notion of dev, staging, and prod to represent the execution
environments of each stage. 

An instantiated project from MLOps Stacks contains an ML pipeline with CI/CD workflows to test and deploy automated model training and batch inference jobs across your dev, staging, and prod Databricks workspaces. 

<img src="doc-images/mlops-stack-summary.png">

Data scientists can iterate on ML code and file pull requests (PRs). This will trigger unit tests and integration tests in an isolated staging Databricks workspace. Model training and batch inference jobs in staging will immediately update to run the latest code when a PR is merged into main. After merging a PR into main, you can cut a new release branch as part of your regularly scheduled release process to promote ML code changes to production.

### Develop ML pipelines
https://github.com/databricks/mlops-stacks/assets/87999496/00eed790-70f4-4428-9f18-71771051f92a


### Create a PR and CI
https://github.com/databricks/mlops-stacks/assets/87999496/f5b3c82d-77a5-4ee5-85f5-8f00b026ae05


### Merge the PR and deploy to Staging
https://github.com/databricks/mlops-stacks/assets/87999496/7239e4d0-2327-4d30-91cc-5e7f8328ef73

https://github.com/databricks/mlops-stacks/assets/87999496/013c0d32-c283-494b-8c3f-2a9a60366207


### Deploy to Prod
https://github.com/databricks/mlops-stacks/assets/87999496/0d220d55-465e-4a69-bd83-1e66ad2e8464


[See this page](Pipeline.md) for detailed description and diagrams of the ML pipeline structure defined in the default stack. 

## Using MLOps Stacks

### Prerequisites
 - Python 3.11+
 - [Databricks CLI](https://docs.databricks.com/en/dev-tools/cli/databricks-cli.html) >= v0.236.0

[Databricks CLI](https://docs.databricks.com/en/dev-tools/cli/databricks-cli.html) contains [Databricks asset bundle templates](https://docs.databricks.com/en/dev-tools/bundles/templates.html) for the purpose of project creation.

Please follow [the instruction](https://docs.databricks.com/en/dev-tools/cli/databricks-cli-ref.html#install-the-cli) to install and set up databricks CLI. Releases of databricks CLI can be found in the [releases section](https://github.com/databricks/cli/releases) of databricks/cli repository.

[Databricks asset bundles](https://docs.databricks.com/en/dev-tools/bundles/index.html) and [Databricks asset bundle templates](https://docs.databricks.com/en/dev-tools/bundles/templates.html) are in public preview.


### Start a new project

To create a new project, run:

    databricks bundle init mlops-stacks

This will prompt for the following initialization parameters:

**Project and naming:**
 * ``input_project_name``: Name of the ML project (e.g., `credit_risk_model`). Used throughout resource names and experiment tracking.
 * ``input_root_dir``: Root directory for the project (e.g., `domains/data_analytics_ai`). Allows both monorepo and polyrepo setups.
 * ``input_schema_name``: Name of the Unity Catalog schema where the model will be registered. Recommend matching the project name. Service principals must have `USE_CATALOG`, `USE_SCHEMA`, `MODIFY`, `CREATE_MODEL`, and `CREATE_TABLE` permissions.

**Organization and domains:**
 * ``input_domain``: Organizational domain for resource naming (e.g., `data_analytics_ai`, `customer_engagement`). Used to construct Databricks group names for permissions.

**Git branching strategy:**
 * ``input_dev_branch``: Development branch name (default: `dev_qa`). ML code on this branch is deployed to the dev environment.
 * ``input_test_branch``: Test/UAT branch name (default: `uat`). ML code on this branch is deployed to the UAT environment.
 * ``input_prod_branch``: Production branch name (default: `prod`). ML code on this branch is deployed to the prod environment.

**Databricks workspace URLs:**
 * ``input_databricks_dev_workspace_host``: URL of the dev Databricks workspace (e.g., `https://dbc-xxxxx.cloud.databricks.com`).
 * ``input_databricks_uat_workspace_host``: URL of the UAT Databricks workspace.
 * ``input_databricks_prod_workspace_host``: URL of the production Databricks workspace.

**Access control:**
 * ``input_run_role_group``: User group granted RUN (execute) permissions on ML jobs (e.g., `data_scientist`, `data_engineer`). Must exist in all three workspaces.
 * ``input_dev_manage_role_group``: User group granted MANAGE (edit) permissions on ML jobs in the dev environment.
 * ``input_unity_catalog_read_user_group``: User group granted READ/EXECUTE privileges on the registered model in [Unity Catalog](https://docs.databricks.com/en/mlflow/models-in-uc.html#models-in-unity-catalog).

**Unity Catalog setup:**
 * ``input_dev_catalog_name``: Dev environment Unity Catalog name (e.g., `dev_qa_data_analytics_ai`). Must already exist.
 * ``input_uat_catalog_name``: UAT environment Unity Catalog name (e.g., `uat_data_analytics_ai`). Must already exist.
 * ``input_prod_catalog_name``: Production environment Unity Catalog name (e.g., `prod_data_analytics_ai`). Must already exist.

**Feature engineering (optional):**
 * ``input_include_feature_store``: Set to `yes` to include [Databricks Feature Store](https://docs.databricks.com/machine-learning/feature-store/index.html) components: feature modules, feature engineering jobs, and integration tests.

**Monitoring (optional):**
 * ``input_inference_table_name``: Fully qualified name of an inference table for model monitoring (e.g., `prod_data_analytics_ai.my_schema.predictions`). Must already exist in Unity Catalog.

See the generated ``README.md`` in your project directory for next steps!

## Customize MLOps Stacks
Your organization can use the default stack as is or customize it as needed, e.g. to add/remove components or
adapt individual components to fit your organization's best practices. See the
[stack customization guide](stack-customization.md) for more details.

## FAQ

### Do I need separate dev/staging/prod workspaces to use MLOps Stacks?
We recommend using separate dev/staging/prod Databricks workspaces for stronger
isolation between environments. For example, Databricks REST API rate limits
are applied per-workspace, so if using [Databricks Model Serving](https://docs.databricks.com/applications/mlflow/model-serving.html),
using separate workspaces can help prevent high load in staging from DOSing your
production model serving endpoints.

### I have an existing ML project. Can I productionize it using MLOps Stacks?
Yes. Currently, you can instantiate a new project and copy relevant components
into your existing project to productionize it. MLOps Stacks is modularized, so
you can e.g. copy just the GitHub Actions workflows under `.github` or ML resource configs
 under ``{{.input_root_dir}}/{{template `project_name_alphanumeric_underscore` .}}/resources`` 
and ``{{.input_root_dir}}/{{template `project_name_alphanumeric_underscore` .}}/databricks.yml`` into your existing project.

### Can I adopt individual components of MLOps Stacks?
For this use case, we recommend instantiating via [Databricks asset bundle templates](https://docs.databricks.com/en/dev-tools/bundles/templates.html) 
and copying the relevant subdirectories. For example, all ML resource configs
are defined under ``{{.input_root_dir}}/{{template `project_name_alphanumeric_underscore` .}}/resources``
and ``{{.input_root_dir}}/{{template `project_name_alphanumeric_underscore` .}}/databricks.yml``, while CI/CD is defined e.g. under `.github`
if using GitHub Actions. 

### Can I customize my MLOps Stack?
Yes. We provide the default stack in this repo as a production-friendly starting point for MLOps.
However, in many cases you may need to customize the stack to match your organization's
best practices. See [the stack customization guide](stack-customization.md)
for details on how to do this.

### Does the MLOps Stacks cover data (ETL) pipelines?

Since MLOps Stacks is based on [databricks CLI bundles](https://docs.databricks.com/dev-tools/cli/bundle-commands.html),
it's not limited only to ML workflows and resources - it works for resources across the Databricks Lakehouse. For instance, while the existing ML
code samples contain feature engineering, training, model validation, deployment and batch inference workflows,
you can use it for Delta Live Tables pipelines as well.

### How can I provide feedback?

Please provide feedback (bug reports, feature requests, etc) via GitHub issues.

## Contributing

We welcome community contributions. For substantial changes, we ask that you first file a GitHub issue to facilitate
discussion, before opening a pull request.

MLOps Stacks is implemented as a [Databricks asset bundle template](https://docs.databricks.com/en/dev-tools/bundles/templates.html)
that generates new projects given user-supplied parameters. Parametrized project code can be found under
the `{{.input_root_dir}}` directory.

### Installing development requirements

To run tests, install [actionlint](https://github.com/rhysd/actionlint),
[databricks CLI](https://docs.databricks.com/dev-tools/cli/databricks-cli.html), [npm](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm), and
[act](https://github.com/nektos/act). Then install the Python dependencies using [uv](https://docs.astral.sh/uv/):

    uv sync --all-extras --dev

### Running the tests
**NOTE**: This section is for open-source developers contributing to the default stack
in this repo.  If you are working on an ML project using the stack (e.g. if you ran `databricks bundle init`
to start a new project), see the `README.md` within your generated
project directory for detailed instructions on how to make and test changes.

Run unit tests:

```
pytest tests
```

Run all tests (unit and slower integration tests):

```
pytest tests --large
```

Run integration tests only:

```
pytest tests --large-only
```

### Previewing changes
When making changes to MLOps Stacks, it can be convenient to see how those changes affect
a generated new ML project. To do this, you can create an example
project from your local checkout of the repo, and inspect its contents/run tests within
the project.

We provide example project configs for AWS (using GitHub) under `tests/example-project-configs`.
To create an example AWS project, using GitHub Actions for CI/CD, run:
```
# Note: update MLOPS_STACKS_PATH to the path to your local checkout of the MLOps Stacks repo
MLOPS_STACKS_PATH=~/mlops-stacks
databricks bundle init "$MLOPS_STACKS_PATH" --config-file "$MLOPS_STACKS_PATH/tests/example-project-configs/aws/aws-github.json"
```