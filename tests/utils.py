import os
import pathlib
import pytest
import json
import subprocess
from functools import wraps

AWS_DEFAULT_PARAMS = {
    "input_setup_cicd_and_project": "CICD_and_Project",
    "input_root_dir": "my-mlops-project",
    "input_project_name": "my-mlops-project",
    "input_cicd_platform": "github_actions",
    "input_databricks_staging_workspace_host": "https://your-staging-workspace.cloud.databricks.com",
    "input_databricks_prod_workspace_host": "https://your-prod-workspace.cloud.databricks.com",
    "input_default_branch": "main",
    "input_release_branch": "release",
    "input_read_user_group": "users",
    "input_include_feature_store": "no",
    "input_schema_name": "schema_name",
    "input_unity_catalog_read_user_group": "account users",
    "input_inference_table_name": "dummy.schema.table",
    "input_test_catalog_name": "test_catalog",
    "input_staging_catalog_name": "staging_catalog",
    "input_prod_catalog_name": "prod_catalog",
}


def parametrize_by_project_generation_params(fn):
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
def cicd_platform():
    return "github_actions"


@pytest.fixture
def generated_project_dir(
    tmpdir,
    databricks_cli,
    cicd_platform,
    setup_cicd_and_project,
    include_feature_store,
    template_path,
):
    params = {
        "input_setup_cicd_and_project": setup_cicd_and_project,
        "input_root_dir": "my-mlops-project",
    }
    if setup_cicd_and_project != "Project_Only":
        params.update(
            {
                "input_cicd_platform": cicd_platform,
                "input_databricks_staging_workspace_host": "https://your-staging-workspace.cloud.databricks.com",
                "input_databricks_prod_workspace_host": "https://your-prod-workspace.cloud.databricks.com",
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
    generate(tmpdir, databricks_cli, params, template_path)
    return tmpdir


def read_workflow(tmpdir):
    return (tmpdir / "my-mlops-project" / ".github/workflows/run-tests.yml").read_text(
        "utf-8"
    )


def markdown_checker_configs(tmpdir):
    markdown_checker_config_dict = {
        "ignorePatterns": [
            {"pattern": "http://127.0.0.1:5000"},
            # Placeholder workspace hosts substituted into the generated docs by
            # AWS_DEFAULT_PARAMS. They don't resolve, so exclude them from link checking.
            {"pattern": "https://your-staging-workspace.cloud.databricks.com*"},
            {"pattern": "https://your-prod-workspace.cloud.databricks.com*"},
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


def generate(directory, databricks_cli, context, template_path):
    """
    Generates a Databricks Asset Bundle project using the MLOps Stacks template.

    :param directory: Target output directory (pathlib.Path or str)
    :param databricks_cli: Path to the databricks CLI executable
    :param context: Dictionary of template variables to override defaults
    :param template_path: Optional relative path to a specific monorepo template folder
    """
    default_params = AWS_DEFAULT_PARAMS

    params = {
        **default_params,
        **context,
    }
    json_string = json.dumps(params)
    config_file = directory / "config.json"
    config_file.write(json_string)

    # 1. Capture the system's current environment variables
    custom_env = os.environ.copy()

    # 2. Inject modern Databricks authentication variables
    custom_env["DATABRICKS_HOST"] = "https://123"
    custom_env["DATABRICKS_TOKEN"] = "dapi123"

    # 3. Explicitly resolve the target template directory using the required parameter
    repo_root = pathlib.Path(__file__).parent.parent
    target_template_directory = repo_root / template_path

    # 4. Execute bundle init safely using a list structure
    command = [
        str(databricks_cli),
        "bundle",
        "init",
        str(target_template_directory),
        "--config-file",
        str(config_file),
        "--output-dir",
        str(directory),
    ]

    subprocess.run(
        command,
        shell=False,  # Securely handles arguments without standard shell parsing rules
        check=True,
        env=custom_env,  # Bypasses interactive prompts seamlessly
    )


@pytest.fixture(scope="session")
def databricks_cli(tmp_path_factory):
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

    yield str(databricks_cli_dir / "databricks")
    # no need to remove the files as they are in test temp dir


def paths(directory):
    paths = list(pathlib.Path(directory).glob("**/*"))
    paths = [r.relative_to(directory) for r in paths]
    return {str(f) for f in paths if str(f) != "."}
