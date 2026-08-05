import os
import pathlib
import pytest
import json
import shutil
import subprocess
from functools import wraps

RESOURCE_TEMPLATE_ROOT_DIRECTORY = str(pathlib.Path(__file__).parent.parent)

# This template fork is locked to a single stack: Databricks on AWS with
# GitHub Actions. All test parametrization is scoped to that single stack.
AWS_DEFAULT_PARAMS = {
    "input_setup_cicd_and_project": "CICD_and_Project",
    "input_root_dir": "my-mlops-project",
    "input_project_name": "my-mlops-project",
    "input_cloud": "aws",
    "input_cicd_platform": "github_actions",
    "input_databricks_staging_workspace_host": "https://your-staging-workspace.cloud.databricks.com",
    "input_databricks_prod_workspace_host": "https://your-prod-workspace.cloud.databricks.com",
    "input_default_branch": "main",
    "input_release_branch": "release",
    "input_read_user_group": "users",
    "input_include_feature_store": "yes",
    "input_schema_name": "schema_name",
    "input_unity_catalog_read_user_group": "account users",
    "input_inference_table_name": "dummy.schema.table",
}


def parametrize_by_cloud(fn):
    @wraps(fn)
    @pytest.mark.parametrize("cloud", ["aws"])
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)

    return wrapper


def parametrize_by_project_generation_params(fn):
    @pytest.mark.parametrize("cloud", ["aws"])
    @pytest.mark.parametrize(
        "cicd_platform",
        [
            "github_actions",
        ],
    )
    @pytest.mark.parametrize(
        "setup_cicd_and_project,include_feature_store",
        [
            ("CICD_and_Project", "no"),
            ("CICD_and_Project", "yes"),
            ("Project_Only", "no"),
            ("Project_Only", "yes"),
            ("CICD_Only", "no"),
        ],
    )
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)

    return wrapper


@pytest.fixture
def generated_project_dir(
    tmpdir,
    databricks_cli,
    cloud,
    cicd_platform,
    setup_cicd_and_project,
    include_feature_store,
):
    params = {
        "input_setup_cicd_and_project": setup_cicd_and_project,
        "input_root_dir": "my-mlops-project",
        "input_cloud": cloud,
    }
    if setup_cicd_and_project != "Project_Only":
        params.update(
            {
                "input_cicd_platform": cicd_platform,
                "input_databricks_staging_workspace_host": "https://dbc-3214-67.cloud.databricks.com",
                "input_databricks_prod_workspace_host": "https://dbc-345-89.cloud.databricks.com",
                "input_default_branch": "main",
                "input_release_branch": "release",
            }
        )
    if setup_cicd_and_project != "CICD_Only":
        params.update(
            {
                "input_project_name": "my-mlops-project",
                "input_include_feature_store": include_feature_store,
                "input_read_user_group": "users",
                "input_schema_name": "schema_name",
                "input_unity_catalog_read_user_group": "account users",
                "input_inference_table_name": "dummy.schema.table",
            }
        )
    generate(tmpdir, databricks_cli, params)
    return tmpdir


def read_workflow(tmpdir):
    return (tmpdir / "my-mlops-project" / ".github/workflows/run-tests.yml").read_text(
        "utf-8"
    )


def markdown_checker_configs(tmpdir):
    markdown_checker_config_dict = {
        "ignorePatterns": [
            {"pattern": "http://127.0.0.1:5000"},
            {"pattern": "https://dbc-3214-67.cloud.databricks.com*"},
            {"pattern": "https://dbc-345-89.cloud.databricks.com*"},
        ],
        "httpHeaders": [
            {
                "urls": ["https://docs.github.com/"],
                "headers": {"Accept-Encoding": "zstd, br, gzip, deflate"},
            },
        ],
    }

    file_name = "checker-config.json"

    with open(tmpdir / "my-mlops-project" / file_name, "w") as outfile:
        json.dump(markdown_checker_config_dict, outfile)


def generate(directory, databricks_cli, context):
    # This template is locked to AWS + GitHub Actions, so there is a single
    # set of default params.
    params = {
        **AWS_DEFAULT_PARAMS,
        **context,
    }
    json_string = json.dumps(params)
    config_file = directory / "config.json"
    config_file.write(json_string)
    subprocess.run(
        f"echo dapi123 | {databricks_cli} configure --host https://123",
        shell=True,
        check=True,
    )
    subprocess.run(
        f"{databricks_cli} bundle init {RESOURCE_TEMPLATE_ROOT_DIRECTORY} --config-file {config_file} --output-dir {directory}",
        shell=True,
        check=True,
    )


@pytest.fixture(scope="session")
def databricks_cli(tmp_path_factory):
    # Prefer a Databricks CLI that is already installed on PATH. This avoids a
    # network download at test time and works in offline/CI environments where
    # the CLI is provisioned ahead of time.
    existing_cli = shutil.which("databricks")
    if existing_cli:
        yield existing_cli
        return

    # Fall back to downloading a pinned CLI release via install.sh.
    # create tools dir
    tool_dir = tmp_path_factory.mktemp("tools")
    # copy script and make it executable
    install_script_path = os.path.join(os.path.dirname(__file__), "install.sh")
    # download databricks cli
    databricks_cli_dir = tool_dir / "databricks_cli"
    databricks_cli_dir.mkdir()
    subprocess.run(
        ["bash", install_script_path, databricks_cli_dir],
        capture_output=True,
        text=True,
    )

    yield f"{databricks_cli_dir}/databricks"
    # no need to remove the files as they are in test temp dir


def paths(directory):
    paths = list(pathlib.Path(directory).glob("**/*"))
    paths = [r.relative_to(directory) for r in paths]
    return {str(f) for f in paths if str(f) != "."}
