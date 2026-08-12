import os
import pathlib
import pytest
import subprocess
from utils import (
    generate,
    databricks_cli,
    markdown_checker_configs,
    paths,
    generated_project_dir,
    parametrize_by_project_generation_params,
)
from unittest import mock

DEFAULT_PROJECT_NAME = "my-mlops-project"
DEFAULT_PROJECT_DIRECTORY = "projects"
# UUID that when set as project name, prevents the removal of files needed in testing
TEST_PROJECT_NAME = "27896cf3-bb3e-476e-8129-96df0406d5c7"
TEST_PROJECT_DIRECTORY = "27896cf3_bb3e_476e_8129_96df0406d5c7"
DEFAULT_PARAM_VALUES = {
    "input_include_feature_store": "no",
    "input_schema_name": "schema_name",
    "input_unity_catalog_read_user_group": "account users",
    "input_inference_table_name": "dummy.schema.table",
}


def assert_no_disallowed_strings_in_files(
    file_paths, disallowed_strings, exclude_path_matches=None
):
    """
    Assert that all files in file_paths, besides those with paths containing
    one of exclude_path_matches as a substring, do not contain any of the specified disallowed strings

    :param file_paths List of paths of files to check
    :param disallowed_strings: List of disallowed strings
    :param exclude_path_matches: List of substrings e.g. [".github", ".png"]. Any files whose paths
    contain one of these substrings will not be checked for disallowed strings
    """
    if exclude_path_matches is None:
        exclude_path_matches = []
    # Exclude binary files like pngs from being string-matched
    exclude_path_matches = exclude_path_matches + [".png", ".parquet", ".tar.gz"]
    for path in file_paths:
        assert os.path.exists(path), "Provided nonexistent path to test: %s" % path

    def assert_no_disallowed_strings(filepath):
        with open(filepath, "r") as f:
            data = f.read()
        for s in disallowed_strings:
            assert s not in data

    def should_check_file_for_disallowed_strings(path):
        return not any(
            substring in path for substring in exclude_path_matches
        ) and os.path.isfile(path)

    test_paths = list(filter(should_check_file_for_disallowed_strings, file_paths))
    for path in test_paths:
        assert_no_disallowed_strings(path)


# Helper function to dynamically calculate template directories before project creation
def get_source_template_dir(template_path_str):
    repo_root = pathlib.Path(__file__).parent.parent
    return repo_root / template_path_str / "template"


@parametrize_by_project_generation_params
def test_no_template_strings_after_param_substitution(generated_project_dir):
    assert_no_disallowed_strings_in_files(
        file_paths=[
            os.path.join(generated_project_dir, path)
            for path in paths(generated_project_dir)
        ],
        disallowed_strings=["{{", "{%", "%}"],
        exclude_path_matches=[".github", ".yml", ".yaml"],
    )


def test_no_databricks_workspace_urls(template_path):
    template_dir = get_source_template_dir(template_path)
    test_paths = [os.path.join(template_dir, path) for path in paths(template_dir)]
    assert_no_disallowed_strings_in_files(
        file_paths=test_paths,
        disallowed_strings=["://databricks.com"],
    )


def test_no_databricks_doc_strings_before_project_generation(template_path):
    template_dir = get_source_template_dir(template_path)
    test_paths = [os.path.join(template_dir, path) for path in paths(template_dir)]
    assert_no_disallowed_strings_in_files(
        file_paths=test_paths,
        disallowed_strings=[
            "https://docs.databricks.com/",
        ],
    )


@pytest.mark.large
@parametrize_by_project_generation_params
def test_markdown_links(generated_project_dir):
    markdown_checker_configs(generated_project_dir)

    commands = (
        "npm install -g markdown-link-check@3.10.3 && "
        "find . -name '*.md' -print0 | "
        "xargs -0 -n1 markdown-link-check -c ./checker-config.json"
    )

    subprocess.run(
        commands,
        shell=True,
        check=True,
        executable="/bin/bash",
        cwd=(generated_project_dir / "my-mlops-project"),
    )


@pytest.mark.parametrize(
    "invalid_params",
    [
        {"input_project_name": "a"},
        {"input_project_name": "a-"},
        {"input_project_name": "Name with spaces"},
        {"input_project_name": "name/with/slashes"},
        {"input_project_name": "name\\with\\backslashes"},
        {"input_project_name": "name.with.periods"},
    ],
)
def test_generate_fails_with_invalid_params(
    tmpdir, databricks_cli, invalid_params, template_path
):
    with pytest.raises(Exception):
        generate(tmpdir, databricks_cli, invalid_params, template_path)


@pytest.mark.parametrize("valid_params", [{}])
def test_generate_succeeds_with_valid_params(
    tmpdir, databricks_cli, valid_params, template_path
):
    generate(tmpdir, databricks_cli, valid_params, template_path)


@parametrize_by_project_generation_params
def test_generate_project_with_default_values(
    tmpdir,
    databricks_cli,
    include_feature_store,
    template_path,
):
    """
    Asserts the default parameter values. The project name and experiment
    parent directory are excluded from this test as they covered in other tests. If this test fails
    due to an update of the default values, please do the following checks:
    - The default param value constants in this test are up to date.
    - The default param values in the substitution logic in the pre_gen_project.py hook are up to date.
    - The default param values in the help strings in databricks_template_schema.json are up to date.
    """
    context = {
        "input_project_name": TEST_PROJECT_NAME,
        "input_root_dir": TEST_PROJECT_NAME,
    }
    generate(tmpdir, databricks_cli, context=context, template_path=template_path)
    test_file_contents = (
        tmpdir / TEST_PROJECT_NAME / "_params_testing_only.txt"
    ).read_text("utf-8")
    params = {**DEFAULT_PARAM_VALUES}
    for param, value in params.items():
        assert f"{param}={value}" in test_file_contents


def prepareContext(
    include_feature_store,
):
    context = {
        "input_project_name": TEST_PROJECT_NAME,
        "input_root_dir": TEST_PROJECT_NAME,
    }
    if include_feature_store != "":
        context["input_include_feature_store"] = include_feature_store
    return context


@parametrize_by_project_generation_params
def test_generate_project_check_delta_output(
    tmpdir,
    databricks_cli,
    include_feature_store,
    template_path,
):
    """
    Asserts the behavior of Delta Table-related artifacts when generating MLOps Stacks.
    """
    context = prepareContext(
        include_feature_store,
    )
    generate(tmpdir, databricks_cli, context=context, template_path=template_path)
    delta_notebook_path = (
        tmpdir / TEST_PROJECT_DIRECTORY / TEST_PROJECT_NAME / "training" / "Train.py"
    )
    assert not os.path.isfile(delta_notebook_path)


@parametrize_by_project_generation_params
def test_generate_project_check_feature_store_output(
    tmpdir,
    databricks_cli,
    include_feature_store,
    template_path,
):
    """
    Asserts the behavior of feature store-related artifacts when generating MLOps Stacks.
    """
    context = prepareContext(
        include_feature_store,
    )
    generate(tmpdir, databricks_cli, context=context, template_path=template_path)
    fs_notebook_path = (
        tmpdir
        / TEST_PROJECT_DIRECTORY
        / TEST_PROJECT_NAME
        / "feature_engineering"
        / "GenerateAndWriteFeatures.py"
    )
    assert not os.path.isfile(fs_notebook_path)
