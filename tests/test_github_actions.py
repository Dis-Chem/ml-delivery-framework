import hashlib
import os
import platform
import shutil
import subprocess
import tarfile
import urllib.request
import pytest
from utils import (
    databricks_cli,
    generated_project_dir,
)

# Pinned actionlint release. The binary is verified against the known-good
# SHA256 published in the release's checksums.txt before it is executed, so a
# compromised/retagged upstream cannot inject code into CI.
ACTIONLINT_VERSION = "1.7.12"
ACTIONLINT_SHA256 = {
    "darwin_amd64": "5b44c3bc2255115c9b69e30efc0fecdf498fdb63c5d58e17084fd5f16324c644",
    "darwin_arm64": "aba9ced2dee8d27fecca3dc7feb1a7f9a52caefa1eb46f3271ea66b6e0e6953f",
    "linux_amd64": "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8",
    "linux_arm64": "325e971b6ba9bfa504672e29be93c24981eeb1c07576d730e9f7c8805afff0c6",
}


def _actionlint_platform():
    system = platform.system().lower()  # "linux" / "darwin"
    machine = platform.machine().lower()
    arch = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }.get(machine)
    if system not in ("linux", "darwin") or arch is None:
        raise RuntimeError(f"Unsupported platform for actionlint: {system}/{machine}")
    return f"{system}_{arch}"


def _install_actionlint(dest_dir):
    """Download the pinned actionlint release and verify its SHA256 before use."""
    dest_dir = str(dest_dir)
    key = _actionlint_platform()
    expected = ACTIONLINT_SHA256[key]
    tarball = f"actionlint_{ACTIONLINT_VERSION}_{key}.tar.gz"
    url = (
        f"https://github.com/rhysd/actionlint/releases/download/"
        f"v{ACTIONLINT_VERSION}/{tarball}"
    )
    archive_path = os.path.join(dest_dir, tarball)
    urllib.request.urlretrieve(url, archive_path)
    with open(archive_path, "rb") as f:
        actual = hashlib.sha256(f.read()).hexdigest()
    if actual != expected:
        raise RuntimeError(
            f"actionlint checksum mismatch for {tarball}: "
            f"expected {expected}, got {actual}"
        )
    with tarfile.open(archive_path) as tf:
        tf.extract("actionlint", path=dest_dir)
    binary = os.path.join(dest_dir, "actionlint")
    os.chmod(binary, 0o755)
    return binary


@pytest.mark.parametrize("cicd_platform", ["github_actions"])
@pytest.mark.parametrize(
    "setup_cicd_and_project,include_feature_store",
    [
        ("CICD_and_Project", "no"),
        ("CICD_and_Project", "yes"),
        ("CICD_Only", "no"),
    ],
)
# Explicitly added template_path to unlock the conftest matrix loop mapping
def test_generated_yaml_format(generated_project_dir, template_path):
    # Note: actionlint only works when the directory is a git project. Thus we begin by initializing
    # the generated mlops project with git.
    project_dir = generated_project_dir / "my-mlops-project"
    
    # Install a pinned, checksum-verified actionlint
    actionlint = _install_actionlint(generated_project_dir)
    subprocess.run("git init", shell=True, check=True, cwd=project_dir)
    subprocess.run(
        [str(actionlint), "-color"],
        check=True,
        cwd=project_dir,
    )


@pytest.mark.large
@pytest.mark.skipif(
    shutil.which("act") is None and not os.environ.get("CI"),
    reason="`act` is not installed. CI installs it, so this only skips locally.",
)
@pytest.mark.parametrize("cicd_platform", ["github_actions"])
@pytest.mark.parametrize(
    "setup_cicd_and_project,include_feature_store",
    [
        ("CICD_and_Project", "no"),
        ("CICD_and_Project", "yes"),
    ],
)
# Explicitly added template_path to unlock the conftest matrix loop mapping
def test_run_unit_tests_workflow(generated_project_dir, template_path):
    """Test that the GitHub workflow for running unit tests in the materialized project passes"""
    project_dir = generated_project_dir / "my-mlops-project"
    
    # Dynamic wildcard search for the generated test workflow file.
    # This prevents failures if template variants name their workflows differently.
    workflows_dir = project_dir / ".github" / "workflows"
    workflow_files = list(workflows_dir.glob("*-run-tests.yml"))
    
    if not workflow_files:
        pytest.fail(f"No run-tests workflow found in {workflows_dir} for template {template_path}")
    
    target_workflow = workflow_files[0].name

    subprocess.run(
        f"git init && act -s GITHUB_TOKEN workflow_dispatch --workflows .github/workflows/{target_workflow} -j 'unit_tests'",
        shell=True,
        check=True,
        executable="/bin/bash",
        cwd=project_dir,
    )
