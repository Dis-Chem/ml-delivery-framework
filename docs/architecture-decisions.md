# Architecture Decision Record — ML Delivery Framework

**Subject:** Customisation of the Databricks MLOps Stacks bundle template for X Bigly Labs / Dis-Chem.
**Stack:** Databricks on **AWS** · **GitHub Actions** CI/CD · **GitHub OIDC** auth · monorepo delivery.
**Status:** Proposed / in review — all changes on branch `feature/initial-commit`, not yet committed.
**Last updated:** 2026-07-31.

This document records the architectural decisions taken while locking down the template, the reasoning
behind each, the alternatives considered, and the consequences. Reference documentation for review is
collected at the end.

---

## Decision summary

| # | Decision | Reasoning in one line |
|---|----------|-----------------------|
| [ADR-01](#adr-01--lock-the-template-to-aws--github-actions) | Lock to AWS + GitHub Actions | We only run one stack; remove choice, keep the code paths cheap to maintain |
| [ADR-02](#adr-02--authenticate-cicd-with-github-oidc-federation) | GitHub OIDC federation for CI/CD auth | No long-lived Databricks tokens to store or rotate |
| [ADR-03](#adr-03--clientids-and-hosts-as-actions-variables-not-secrets) | Client IDs / hosts as Actions **variables** | They aren't secrets; secrets add friction with no security gain |
| [ADR-04](#adr-04--dev_qa-only-poc-with-a-dormant-prod-path) | dev_qa-only PoC, prod dormant | Match the current rollout; auto-enable prod later without edits |
| [ADR-05](#adr-05--serverless-compute-by-default) | Serverless compute by default | Already the resource default; drop cloud-specific cluster sizing |
| [ADR-06](#adr-06--register-ml-assets-in-the-consumptiongold-catalog) | ML assets → Consumption/Gold catalog | ML outputs are data products per the medallion guide |
| [ADR-07](#adr-07--governance-tags-via-bundle-presets) | Governance tags via bundle `presets` | One place, applies to every taggable resource |
| [ADR-08](#adr-08--snake_case-identifiers-everywhere) | snake_case identifiers everywhere | The org naming guide forbids hyphens in UC names |
| [ADR-09](#adr-09--keep-the-mlops-stacks-branch-model) | Keep MLOps Stacks branch model | Deferred remap; lower risk during the PoC |
| [ADR-10](#adr-10--one-identity-discovery-model) | One-identity discovery model | Discovery lives in UC/MLflow; align repo⇄UC⇄tags |
| [ADR-11](#adr-11--enforce-the-monorepo-structure-placement--identity) | Enforce monorepo placement + identity | New projects always land in `domains/<tribe>/<squad>` |
| [ADR-12](#adr-12--enforce-project_only-as-a-constant) | Enforce `Project_Only` as a constant | Squad creation, not standalone repos; CI/CD is a root concern |
| [ADR-13](#adr-13--narrow-the-test-suite-to-awsgithub) | Narrow the test suite to AWS/GitHub | Tests should reflect the only supported stack |
| [ADR-14](#adr-14--environment--branch-mapping) | Environment ↔ branch mapping | `dev`→dev_qa, `main`→UAT, `release`→prod, driven by branch |
| [ADR-15](#adr-15--central-deployment-scope-registry--matrix) | Central deployment-scope registry + matrix | Deploy only registered projects that changed, after tests pass |
| [ADR-16](#adr-16--split-template-and-deployment-repos-pin-template-invocation-to-a-tag) | Split template and deployment repos; pin invocation to a tag | Template repo needs zero Databricks access; scaffolds are reproducible, not drifting with `main` |
| [ADR-17](#adr-17--add-a-kedro-project-skeleton-as-an-alternate-flavor) | Add a Kedro project skeleton as an alternate flavor | Some squads already use Kedro; DAB deploy machinery (ADR-06/07) stays the single source of truth for both flavors |

---

## ADR-01 — Lock the template to AWS + GitHub Actions

**Decision.** Support exactly one cloud (AWS) and one CI/CD platform (GitHub Actions). Implemented by pinning
`input_cloud` and `input_cicd_platform` to single-value enums that never prompt, rather than deleting every
`eq .input_cloud` branch in the templates. Azure DevOps and GitLab template directories were removed.

**Reasoning.** We only operate on AWS with GitHub. Removing the *choice* prevents misconfiguration, but ripping
out every cloud conditional would be a large, error-prone change that diverges hard from upstream MLOps Stacks
and makes future rebases painful. Pinning to a hidden constant keeps the existing guards evaluating to the AWS
branch while removing them from the UI.

**Alternatives considered.** (a) Full removal of all non-AWS/GitHub code — rejected as high-churn, low-benefit.
(b) Leave all options selectable with AWS/GitHub as defaults — rejected; it invites unsupported combinations.

**Consequences.** The `.azure` / `.gitlab` trees and the GitLab-only Docker input are gone. Doc links always
resolve to `docs.databricks.com`. Remaining `eq .input_cloud` guards are harmless (always AWS).

---

## ADR-02 — Authenticate CI/CD with GitHub OIDC federation

**Decision.** GitHub Actions authenticates to Databricks via **OAuth token federation (OIDC)**. Every workflow
sets `permissions: id-token: write`, `DATABRICKS_AUTH_TYPE: github-oidc`, `DATABRICKS_HOST`, and
`DATABRICKS_CLIENT_ID`. The previous PAT approach (`DATABRICKS_TOKEN` from `*_WORKSPACE_TOKEN` secrets) and all
Azure ARM branches were removed.

**Reasoning.** OIDC exchanges a short-lived GitHub identity token for a Databricks OAuth token at runtime — there
is **no long-lived Databricks credential to store, leak, or rotate**. This is Databricks' explicitly recommended
method for automated workloads.

**Consequences.** A one-time setup per service principal: create a federation policy scoping the trust to the
repo (see docs below). The `WORKFLOW_TOKEN` GitHub secret remains — it is a GitHub PAT for opening the deploy PR,
unrelated to Databricks auth.

**Update (see ADR-16).** `ml-delivery-framework` itself is never deployed to Databricks and needs **no OIDC
setup of its own** — its CI only renders the template offline (`scripts/smoke-test.sh`, pytest). OIDC federation
is configured on **`data-science-projects`** (the separate deployment repo), which is what actually runs
`databricks bundle deploy`. This ADR's OIDC mechanism is unchanged; only *which repo* holds the federation
policy and workflows moved.

---

## ADR-03 — Client IDs and hosts as Actions **variables**, not secrets

**Decision.** Store the service-principal application (client) IDs as GitHub Actions **variables** — one per
Databricks workspace (`vars.DEV_CLIENT_ID`, `vars.STAGING_CLIENT_ID`, `vars.PROD_CLIENT_ID`; see ADR-14 for why
there are three, not two). Workspace hosts are baked into the workflows and `databricks.yml`. Nothing is stored
as a secret except the unrelated `WORKFLOW_TOKEN`.

**Reasoning.** Under OIDC there is no credential to protect (ADR-02). A workspace host URL and an SP client ID are
not sensitive — the host appears in every browser URL and in `databricks.yml`. Putting non-secrets in *secrets*
buys nothing and costs debuggability: secrets are masked in logs (making CLI errors read as `***`) and can't be
read back for auditing. Variables keep them out of code while remaining visible and auditable.

**Consequences.** Flipping a `vars.*` reference to `secrets.*` is a one-line change per workflow if org policy
ever requires it.

---

## ADR-04 — dev_qa-only PoC with a dormant prod path

**Decision.** During the PoC only the **dev_qa (UAT)** workspace is used. The bundle `dev`/`staging`/`test`
targets and their CI jobs point at dev_qa; the `prod` target and its deploy/validate jobs are **dormant** — they
activate automatically once a `PROD_CLIENT_ID` Actions variable exists (`if: ${{ vars.PROD_CLIENT_ID != '' }}`).
The prod catalog default is a clearly-marked `TODO_` placeholder.

**Reasoning.** We are only deploying to dev_qa now, but we want to enable prod later **without editing workflows**.
Gating prod jobs on the presence of a variable makes activation a config action, not a code change, and keeps
red X's off PRs in the meantime.

**Consequences.** Prod host is pre-filled for later; the prod catalog must be set before prod is enabled.

---

## ADR-05 — Serverless compute by default

**Decision.** Jobs run on **serverless** compute (the resource YAML already uses `environments:` /
`environment_version`). The dead `cloud_specific_node_type_id` helper and its references were removed.

**Reasoning.** Serverless removes cluster sizing/tuning per environment and matches the platform direction. The
cloud-specific node-type helper only existed to pick classic instance types per cloud — irrelevant once we are
serverless and single-cloud.

**Update — Kedro.** The team is proceeding with Kedro pipelines on this template. Serverless remains the
default compute for Kedro pipelines too — no known requirement forces classic compute today. This isn't fully
confirmed yet: if a specific Kedro/Spark dependency (a particular cluster library, GPU, a custom init script)
turns out to need classic compute, that becomes a per-task exception, not a change to this default. Tracked as
open issue N-09.

---

## ADR-06 — Register ML assets in the Consumption/Gold catalog

**Decision.** Models, feature tables, and experiments register into the **Consumption (Gold)** layer:
`dev_qa_data_analytics_consumption_dev` for dev_qa, schema = `<tribe>_<squad>`.

**Reasoning.** In the org medallion model, ML outputs are consumption-ready **data products**, which live in the
Gold/Consumption layer — not in raw/curated/trusted. Aligning the ML catalog to that layer keeps the medallion
taxonomy coherent and makes ML assets discoverable alongside other Gold products.

**Alternatives considered.** A dedicated `..._ml_<stage>` catalog — cleaner isolation but one more catalog to
provision; deferred as an open option (see ADR-10 open decisions).

---

## ADR-07 — Governance tags via bundle presets

**Decision.** Apply the org governance tags — `Company`, `Tribe`, `Squad`, `Domain`, `Environment`, `Purpose`,
`ManagedBy`, `OwnerTeam`, `CostCenter`, `DataClass` — through Databricks Asset Bundle **`presets.tags`**, so every
taggable resource in the bundle inherits them. `Environment` is derived from `${bundle.target}`. `ManagedBy` is
set to `databricks_asset_bundle`.

**Reasoning.** `presets.tags` is the single, bundle-wide mechanism for tags and avoids per-resource duplication.
It validated cleanly under `databricks bundle validate`. We set `ManagedBy=databricks_asset_bundle` rather than
the tags guide's literal `terraform`, because these assets are managed by DABs, not Terraform — accuracy over
literal adherence (confirmed with the owner).

**Consequences.** `Tribe`/`Squad`/`Domain` come from template inputs; `OwnerTeam`/`CostCenter`/`DataClass` remain
`TODO_` placeholders for the team to fill.

---

## ADR-08 — snake_case identifiers everywhere

**Decision.** All generated identifiers use `lower_snake_case`. The model name is `<project>_model` and the
experiment base `<project>_experiment` (previously hyphenated). Template inputs `tribe`/`squad`/`domain` are
pattern-validated to `^[a-z][a-z0-9_]*$`.

**Reasoning.** The org naming guide mandates lowercase snake_case and **forbids hyphens** — and hyphens are
invalid in several Unity Catalog object names regardless. The stock `<project>-model` would have produced an
invalid/registered-name-unfriendly model.

---

## ADR-09 — Keep the MLOps Stacks branch model

**Decision.** Retain the upstream branch→environment mapping (`main` stages to staging, the `release` branch
feeds prod) rather than remapping to the platform's documented `main`=PROD / `release/*`=UAT model.

**Reasoning.** A deliberate, owner-approved deferral. The platform branching doc inverts the stack's semantics;
remapping touches triggers across every workflow and adds risk during a PoC that isn't deploying to prod yet.
**Revisit before prod deploys begin.**

---

## ADR-10 — One-identity discovery model

**Decision.** Treat discovery as a **Unity Catalog + MLflow registry** concern, not a folder concern. Anchor every
plane to one identity keyed on `<tribe>_<squad>`: repo path ⇄ UC schema ⇄ registered-model name ⇄ experiment path
⇄ tags. Keep the repo **team-first** for ownership; make the UC namespace **domain-aware**; use **tags as the
bridge** (every asset carries `Tribe`, `Squad`, and `Domain`). Features are organised in **tiers**
(squad → tribe → platform), so reuse is a promotion, not a copy.

**Reasoning.** Databricks' own guidance is that data/feature/model discovery happens through UC search, tags,
comments, lineage, the Feature Store UI, and the domain-organised UC marketplace — folders can't make an asset
findable. Team-first repos give clear ownership; domain-first catalogs give discovery. Tags reconcile the two so
neither is compromised.

**Companion design note.** Full rationale, the proposed tree, and the namespace mapping table:
<https://claude.ai/code/artifact/be7b711a-9bdf-423c-a9c1-68c9ff77b493>

**Update — domain/tribe hierarchy resolved.** Confirmed: a domain contains **multiple tribes** (domain is the
broader org grouping; tribe is a team within it) — the two are not siblings. This is recorded as **metadata
only**: the repo path stays team-first (`domains/<tribe>/<squad>/`, unchanged structurally — see ADR-11), and
`Domain` remains a governance tag, not a path segment. The top-level folder is named `domains/` (renamed from
an earlier `teams/`) purely to match the org's own naming for this concept; it does **not** mean domain gets
its own nested folder level. `input_domain` and `input_tribe` remain independent template inputs — no
tribe→domain lookup/validation is enforced (tracked as a possible future enhancement, not required now).

**Open decisions (remaining).** (1) Reuse the `consumption` catalog vs a dedicated `..._ml_<stage>` catalog?
(2) Who signs off on promoting a feature up a tier?

---

## ADR-11 — Enforce the monorepo structure (placement + identity)

**Decision.** Generate every project **into** the monorepo at `domains/<tribe>/<squad>/<tribe>_<squad>/`. Added
first-class inputs `input_tribe`, `input_squad`, `input_domain` (generic example defaults —
`example_tribe`/`example_squad`/`example_domain`, **not** a real team). From them the template derives and locks
(no prompt): `input_project_name = <tribe>_<squad>`, `input_root_dir = domains/<tribe>/<squad>`,
`input_schema_name = <tribe>_<squad>`, plus the `Tribe`/`Squad`/`Domain` tags. The **internal** project layout
(`training/`, `deployment/`, `validation/`, `monitoring/`, `resources/`) is kept as-is.

**Reasoning.** The platform uses one monorepo organised by team→squad; standalone per-project repos would recreate
the fragmentation the monorepo strategy exists to prevent. Driving the identity from `tribe`/`squad` makes the
repo⇄UC⇄tags alignment (ADR-10) **generated, not remembered**. We chose *placement + identity* over also
restructuring internals to `src/{...}` because the latter rewrites ~30 notebook paths and diverges from the layout
data scientists know from upstream — high risk, low marginal benefit.

**Consequences / known limitation.** GitHub only runs workflows in the **repo-root** `.github/workflows`. Running
full `CICD_and_Project` inside the monorepo would place `.github` under the squad path where GitHub won't execute
it — hence ADR-12 enforces `Project_Only`.

**Update — separate deployment repo (see ADR-16).** The monorepo referenced here (`domains/<tribe>/<squad>/`) is
a **separate GitHub repository** (`data-science-projects`), not this template repo. Squads scaffold projects by
calling this template *from a notebook running inside that repo*; CI/CD for the whole monorepo is the shared
`deployment-repo/` kit (ADR-15), not a per-project `CICD_Only` bootstrap at this repo's root. `CICD_Only` remains
available as an optional escape hatch (ADR-02 update) for a squad wanting fully independent workflows, but it is
no longer the primary/expected path.

---

## ADR-12 — Enforce `Project_Only` as a constant

**Decision.** `input_setup_cicd_and_project` defaults to `Project_Only` and **never prompts**
(`skip_prompt_if: {}`), making it a constant for interactive use. The enum still lists all three modes so
`--config-file` can override it; the description documents all three.

**Reasoning.** Inside the monorepo the template's job is **squad creation** (code), not standalone repos. Enforcing
`Project_Only` prevents the CICD_and_Project foot-gun from ADR-11. We keep the enum multi-valued rather than a true
single-value constant because a one-value enum would **reject** any config passing another mode — which would
break the test suite (it drives `CICD_and_Project`) and the legitimate root `CICD_Only` bootstrap. Default +
never-prompt gives the same practical guarantee without removing the escape hatches.

**Consequences.** Accepting defaults produces squad code only (no `.github`, single `dev` target on dev_qa).
CI/CD is generated separately at the root via `CICD_Only`.

---

## ADR-13 — Narrow the test suite to AWS/GitHub

**Decision.** Parametrise the pytest suite over `cloud=["aws"]` and `cicd_platform=["github_actions"]` only;
delete `tests/test_gitlab.py`; keep `tests/example-project-configs/aws/aws-github.json` as the single example
config. The `databricks_cli` fixture now prefers a CLI already on `PATH`.

**Reasoning.** Tests should exercise the only supported stack. Narrowing (rather than deleting tests) preserves
coverage while dropping unsupported permutations.

**Result.** `pytest tests -q` → **42 passed, 9 skipped** (skips are the `--large` tests needing real Databricks
auth / `act`).

---

## ADR-14 — Environment ↔ branch mapping

**Decision.** Map bundle targets to environments and Git branches as:

| Branch | Bundle target | Workspace | Host | Catalog |
|--------|---------------|-----------|------|---------|
| `dev` | `dev` | dev_qa | `dbc-26cf5e15-d40d.cloud.databricks.com` | `dev_qa_data_analytics_consumption_dev` |
| `main` | `staging` | UAT | `dbc-9f6e09b3-ca38.cloud.databricks.com` | `uat_data_analytics_consumption_uat` |
| `release` | `prod` | prod | `dbc-cd0b5c83-b24b.cloud.databricks.com` | `prod_data_analytics_consumption_prod` |

**Update — three separate workspaces (corrected).** dev_qa, UAT, and prod are **three distinct Databricks
workspaces**, each with its own host and (per ADR-03) its own GitHub OIDC service principal —
`vars.DEV_CLIENT_ID`, `vars.STAGING_CLIENT_ID`, `vars.PROD_CLIENT_ID` respectively. An earlier version of this
ADR incorrectly assumed dev_qa and UAT shared one workspace; that has been corrected everywhere (schema,
`databricks.yml.tmpl`, the deployment-repo kit).

The `dev` target deploys to a **shared** workspace folder (`workspace.root_path`), not per-user homes —
personal iteration happens in the Databricks console, and the `dev` bundle deploy is the shared, git-sourced
dev. Note `mode: development` is deliberately **not** set on the `dev` target: that preset requires a
user-scoped `root_path` and is incompatible with a shared, CI-deployed target (caught by `scripts/smoke-test.sh`
during implementation).

**Reasoning.** Reflects how the team actually works: three isolated workspaces, promotion through UAT then
prod. Tying each target to a branch makes deployment scope a function of *where you merge*, which the scoped
CI/CD (ADR-15) keys off.

---

## ADR-15 — Central deployment-scope registry + matrix

**Decision.** Govern monorepo deployments with a **repo-root registry** (`bundles.yml`) listing each
project's `name`, `path`, and opted-in `targets`, plus two shared workflows and a scope script (shipped as
the `deployment-repo/` starter kit in `ml-delivery-framework`, to be copied to the root of the separate
`data-science-projects` repo — see ADR-16). A project deploys automatically only when it is **registered**,
its files **changed**, and its tests **pass**. `monorepo_scope.py` maps the branch → target and emits a matrix
of just the in-scope projects; `monorepo-ci.yml` (PR) tests + validates them; `monorepo-deploy.yml` (push)
re-tests then deploys them.

**Reasoning.** Because `Project_Only` is enforced (ADR-12), squad scaffolds carry no CI/CD; a single shared
root pipeline must test and deploy them **without** touching unrelated squads. A registry + changed-path
matrix gives exactly that scoping, is the single source of truth for "what is deployable," and scales to many
squads without a workflow file per project. Registering a project is a reviewed PR — an explicit gate before
anything deploys.

**Alternatives considered.** Per-project path-filtered workflows (MLOps Stacks native) — rejected as the
primary mechanism: N workflow files as squads grow, and no central view of deployable scope.

**Consequences.** The kit lives under `deployment-repo/` in `ml-delivery-framework` and is copied to the root
of the separate **`data-science-projects`** repo, then deleted from here (it is the concrete implementation of
open issue N-01 — see ADR-16 for the two-repo mechanics). It ships a guided
`notebooks/create-a-project.ipynb` so non-technical users can scaffold and validate their own project before
pushing. Auth is OIDC; per ADR-14, dev_qa/UAT/prod are three separate workspaces, so there are three client-ID
variables (`vars.DEV_CLIENT_ID`, `vars.STAGING_CLIENT_ID`, `vars.PROD_CLIENT_ID`), not two.

---

## ADR-16 — Split template and deployment repos; pin template invocation to a tag

**Decision.** `ml-delivery-framework` (this repo) stays **template-only**: it needs no Databricks access and no
OIDC setup — its own CI renders the template offline (`scripts/smoke-test.sh`, pytest). A separate,
user-created repo, **`data-science-projects`**, is the deployment repo: it owns squad code
(`domains/<tribe>/<squad>/`), the deployment registry (`bundles.yml`), the scoped CI/CD (ADR-15), and a guided
notebook (`notebooks/create-a-project.ipynb`) that scaffolds new projects by calling out to this template repo:

```
databricks bundle init https://github.com/Dis-Chem/ml-delivery-framework --tag <TEMPLATE_REF> \
  --config-file <config> --output-dir .
```

`--tag` (confirmed via `databricks bundle init --help`, alongside `--branch`) pins the scaffold to a specific
**released version** of the template, not the mutable default branch.

**Reasoning.** Separates a versioned, reviewable template from live deployment history. Keeps OIDC federation
scoped to least privilege — the template repo never holds a Databricks credential, only the deployment repo
does. Pinning to a tag makes every squad's scaffold reproducible and auditable: two projects created months
apart, both on the same tag, produce identical output, instead of silently drifting with whatever `main`
happens to look like on a given day.

**Alternatives considered.** One combined repo (rejected — conflates template versioning with live deploys, and
would require Databricks credentials in the template repo's own CI). A generate-on-demand bootstrap script
(rejected — unnecessary complexity for what is a one-time copy into a fresh repo).

**Consequences.** A lightweight release process is needed on `ml-delivery-framework` going forward: cut a git
tag after any change that affects scaffolded output. Bumping a squad to a newer template version is a
deliberate `TEMPLATE_REF` edit in the notebook, not automatic. The `deployment-repo/` directory in this repo is
temporary staging content — copy it into `data-science-projects` once that repo exists, then delete it here.

**Reference.** `databricks bundle init --help` (confirms native `--tag`/`--branch` flags for git-URL templates);
<https://docs.databricks.com/en/dev-tools/bundles/templates.html>.

---

## ADR-17 — Add a Kedro project skeleton as an alternate flavor

**Decision.** Add `input_project_skeleton` (`mlops_stacks_native` default, `kedro`) so a squad can
scaffold either the existing training/deployment/validation/monitoring layout, or a Kedro project
(`src/<project>/pipelines/{data_processing,model_training,model_inference}`, `conf/{base,dev,
staging}`, `pyproject.toml`) — never both. Both flavors share the **same** DAB deploy layer:
`databricks.yml`, `resources/ml-artifacts-resource.yml` (MLflow experiment/model, ADR-06/07), and
the same GitHub Actions workflows (ADR-02/03/14). Only the job **task type** changes —
`notebook_task` for native, `python_wheel_task` calling `kedro run --pipeline <name> --env
${bundle.target}` for kedro — via a conditional in `model-workflow-resource.yml.tmpl` and
`batch-inference-workflow-resource.yml.tmpl`, the same pattern already used there for the feature
store toggle. `kedro package` builds the wheel as a step in `run-tests.yml`/`bundle-cd-staging.yml`/
`bundle-cd-prod.yml.tmpl` before validate/deploy; `environments.spec.dependencies` points at the
built wheel (`../dist/<project>-*.whl`) instead of `-r ../requirements.txt`.

**Reasoning.** The team already uses Kedro (see the earlier drawbacks/alternatives discussion).
Rather than depend on the community `kedro-databricks` plugin for the *entire* deploy mechanism —
which would fragment governance tags, UC naming, and the deploy-scope registry (ADR-15) across two
divergent code paths — this keeps the DAB layer as the **single deploy mechanism for every squad**,
regardless of pipeline-authoring framework. Kedro's own scaffolding (`kedro new`) is not used; the
skeleton is hand-rolled to match this template's existing conventions exactly (governance tags, UC
schema naming, serverless-by-default), avoiding two competing "create a project" tools.

**Alternatives considered.** Depend on `kedro-databricks` to generate its own bundle resources per
node (rejected — one job task per node is much finer-grained than this template's existing jobs,
and the plugin's generated resources wouldn't carry this org's tags/naming without a translation
layer). A fully separate Kedro-only template (rejected — doubles the schema/CI/CD/test surface to
maintain for something meant to be one alternate flavor, not a fork).

**Consequences.** Feature Store scaffolding (ADR-04's `input_include_feature_store`) is wired up
for **both** flavors: kedro gets a `feature_engineering` Kedro pipeline (`src/<project>/pipelines/
feature_engineering`) plus matching `catalog.yml`/`parameters.yml` entries, in place of native's
`feature_engineering/` notebook tree. Both flavors share the same
`resources/feature-engineering-workflow-resource.yml` job resource — its own internal skeleton
conditional picks `python_wheel_task` (`kedro run --pipeline feature_engineering`) vs.
`notebook_task`, the same pattern used for `model-workflow-resource.yml`/
`batch-inference-workflow-resource.yml`; the resource file itself is only present when
`input_include_feature_store` is `yes`, regardless of skeleton. The kedro flavor's
`model_training_job` has only a single `Train` task (calling `kedro run --pipeline
model_training`); it does not reproduce the native flavor's separate `ModelValidation`/
`ModelDeployment` tasks — those would need their own Kedro pipelines to be modeled the same way,
deferred as a follow-up. `conf/base/databricks.yml` (kedro-databricks cluster overrides) ships
with everything commented out — serverless is the default (ADR-05) and no classic-compute
override is needed unless a specific dependency requires one (see ADR-05's N-09).

**Verification.** `tests/test_create_project.py::test_generate_project_skeleton_flavor` asserts each
flavor's tree exists and the other's is entirely absent;
`test_generate_project_check_feature_store_output` is parametrized across both skeletons to assert
the feature-engineering scaffolding (notebook for native, Kedro pipeline module for kedro) is
present iff `input_include_feature_store` is `yes`. `scripts/smoke-test.sh` renders and
`bundle validate`s native/kedro combinations across both Feature Store settings.

---

## Local testing

`scripts/smoke-test.sh [tribe] [squad] [domain]` renders the template **offline** (no workspace/auth):
it generates both the `Project_Only` and `CICD_and_Project` flows, fails on un-rendered Go-template leaks,
parses every generated YAML, runs `databricks bundle validate` up to the auth boundary, and lists remaining
`TODO_` placeholders. Output is kept under `tmp/` (git-ignored) for inspection.

`notebooks/local-testing.ipynb` collects every check (unit tests, the smoke test, workflow linting, the
monorepo deploy-scope logic, the full `--large` suite, and an authenticated `bundle validate`) in one place.
Notebook outputs are stripped on commit via `nbstripout` (`.gitattributes` filter + a CI `--verify` step), so
committing notebooks never leaks run output.

---

## Register of open issues & next steps

Consequences of the decisions above that still need action. Ordered roughly by priority.

| # | Issue | Why it matters | Proposed next step | Owner |
|---|-------|----------------|--------------------|-------|
| N-01 | **CI/CD bootstrap for user-created projects.** `Project_Only` is enforced (ADR-12), so squad scaffolds ship with **no** GitHub Actions pipelines. | Without it, a newly-created project can't validate PRs or deploy — it's just code in the monorepo. | **Addressed by ADR-15/ADR-16** — `data-science-projects` (separate repo, created by the platform team) hosts the registry, scoped CI/CD, and guided notebook; the notebook scaffolds new projects by calling `ml-delivery-framework` pinned to `TEMPLATE_REF`. Remaining action: create `data-science-projects`, copy `deployment-repo/` into it, set up OIDC federation policies + `DEV_CLIENT_ID`/`STAGING_CLIENT_ID`/`PROD_CLIENT_ID` Actions variables scoped to the new repo, register the first project(s) in `bundles.yml`, then delete `deployment-repo/` from `ml-delivery-framework`. | MLE / platform |
| N-02 | **Validate the `deploy-cicd.yml` bootstrap workflow.** It is the mechanism behind N-01 and carries a pre-existing suspicious line — `>> "$(PROJECT_NAME_ALPHA)\databricks.yml"` uses `$( )` and a backslash path. | If broken, the CICD_Only bootstrap (N-01) fails. | Dry-run the workflow end-to-end; fix the path expression (`${PROJECT_NAME_ALPHA}/databricks.yml`) if confirmed. | Platform |
| N-03 | **Prod enablement.** Prod is dormant (ADR-04). | Needed before any production deploy. | Create the prod SP + GitHub OIDC federation policy; set `vars.PROD_CLIENT_ID`; replace the `TODO_prod_data_analytics_consumption_prod` catalog with the real prod consumption catalog. | Platform |
| N-04 | **Branch-model remap (ADR-09).** Stack default (`main`→staging) is inverted vs the platform doc (`main`=PROD, `release/*`=UAT). | Wrong branch could deploy to the wrong environment once prod is live. | Decide whether to remap workflow triggers before prod deploys begin. | Platform + squads |
| N-05 | **Discovery design open decisions (ADR-10).** tribe == domain? dedicated `..._ml_<stage>` catalog vs reuse `consumption`? feature-promotion sign-off owner? | These shape the UC namespace and how features are reused/discovered. | Resolve the three open questions in the [discovery design note](https://claude.ai/code/artifact/be7b711a-9bdf-423c-a9c1-68c9ff77b493), then reflect in template defaults. | Data/platform leads |
| N-06 | **Feature tiers not yet enforced.** squad → tribe → platform feature schemas are documented (ADR-10) but not generated. | Cross-squad feature reuse/discovery depends on the tiered schemas existing. | Add feature-schema variables/conventions to the template once N-05 lands. | Platform |
| N-07 | **Fill governance-tag placeholders.** `OwnerTeam`, `CostCenter`, `DataClass` default to `TODO_` (ADR-07). | Cost allocation and data-classification governance depend on real values. | Decide whether these become template inputs or are set per squad in `databricks.yml`. | Governance |
| N-08 | **Dead Azure DevOps / GitLab template blocks.** The generated `mlops-setup.md` retains never-rendered CI-platform branches (locked to GitHub Actions). | Harmless (never rendered) but clutters the template for maintainers. | Optional cleanup pass to delete the dead conditional blocks. | Maintainer |
| N-09 | **Kedro on serverless not fully confirmed (ADR-05).** Kedro adoption is confirmed moving forward; serverless is assumed compatible but no workload has been run yet to prove it. | If a Kedro/Spark task needs classic compute (a specific cluster library, GPU, custom init script), the "serverless by default" assumption needs a per-task exception. | Run a representative Kedro pipeline on serverless; if it fails, scope the exception to that task only rather than changing the default. | Platform / Kedro adopters |

## Reference documentation

### Databricks — authentication & CI/CD
- Enable workload identity federation for GitHub Actions — <https://docs.databricks.com/aws/en/dev-tools/auth/provider-github>
- Enable workload identity federation in CI/CD (overview) — <https://docs.databricks.com/aws/en/dev-tools/auth/oauth-federation-provider>
- Configure a service principal federation policy — <https://docs.databricks.com/aws/dev-tools/auth/oauth-federation-policy>
- GitHub Actions with Databricks — <https://docs.databricks.com/aws/en/dev-tools/ci-cd/github>
- Databricks CLI unified authentication — <https://docs.databricks.com/aws/en/dev-tools/cli/authentication>

### Databricks — bundles (DAB) & MLOps Stacks
- MLOps Stacks overview — <https://docs.databricks.com/aws/en/dev-tools/bundles/mlops-stacks>
- Databricks Asset Bundles — <https://docs.databricks.com/aws/en/dev-tools/bundles/>
- Bundle configuration reference (targets, variables) — <https://docs.databricks.com/aws/en/dev-tools/bundles/settings>
- Bundle deployment presets (`presets`) — <https://docs.databricks.com/aws/en/dev-tools/bundles/deployment-modes>
- Bundle templates — <https://docs.databricks.com/aws/en/dev-tools/bundles/templates>
- Run jobs on serverless compute — <https://docs.databricks.com/aws/en/jobs/run-serverless-jobs>

### Databricks — Unity Catalog, features, models, discovery
- Unity Catalog best practices — <https://docs.databricks.com/aws/en/data-governance/unity-catalog/best-practices>
- Feature Engineering / feature tables in Unity Catalog — <https://docs.databricks.com/aws/en/machine-learning/feature-store/uc/feature-tables-uc>
- Models in Unity Catalog (MLflow registry) — <https://docs.databricks.com/aws/en/machine-learning/manage-model-lifecycle/>
- What's new in Unity Catalog (Data+AI Summit 2025 — discovery, Metrics, marketplace) — <https://www.databricks.com/blog/whats-new-databricks-unity-catalog-data-ai-summit-2025>

### Internal — X Bigly Labs platform standards (Confluence, space `XBLB`)
- Databricks assets naming guide — <https://dischem-it.atlassian.net/wiki/spaces/XBLB/pages/535887886>
- Unity Catalog Guide — <https://dischem-it.atlassian.net/wiki/spaces/XBLB/pages/730726417>
- Platform Medallion Layers — <https://dischem-it.atlassian.net/wiki/spaces/XBLB/pages/608337933>
- AI, Data Science & Analytics Platform Monorepo Structure — <https://dischem-it.atlassian.net/wiki/spaces/XBLB/pages/920223755>
- Tags Definition for Workspaces and Clusters — <https://dischem-it.atlassian.net/wiki/spaces/XBLB/pages/673841161>
- Cluster types per workspace — <https://dischem-it.atlassian.net/wiki/spaces/XBLB/pages/618299429>
- Platform Architecture Guide — <https://dischem-it.atlassian.net/wiki/spaces/XBLB/pages/595197953>

### Companion design note (this work)
- Monorepo & Unity Catalog discovery design — <https://claude.ai/code/artifact/be7b711a-9bdf-423c-a9c1-68c9ff77b493>
