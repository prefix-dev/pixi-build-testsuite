import shutil
from pathlib import Path

import pytest

from .common import get_manifest, repo_root, verify_cli_command


@pytest.mark.slow
@pytest.mark.parametrize(
    "pixi_project",
    [
        pytest.param(example_path, id=example_path.name)
        for example_path in repo_root()
        .joinpath("tests", "data", "pixi_build", "minimal-backend-workspaces")
        .iterdir()
        if example_path.is_dir()
    ],
)
def test_pixi_minimal_backend(pixi_project: Path, pixi: Path, tmp_pixi_workspace: Path) -> None:
    # Remove existing .pixi folders
    shutil.rmtree(pixi_project.joinpath(".pixi"), ignore_errors=True)

    # Copy to workspace
    shutil.copytree(pixi_project, tmp_pixi_workspace, dirs_exist_ok=True)

    # Get manifest
    manifest = get_manifest(tmp_pixi_workspace)

    # Install the environment
    verify_cli_command(
        [pixi, "run", "-v", "--locked", "--manifest-path", manifest, "start"],
        stdout_contains="Build backend works",
    )


# Enable after the backends have been released
# def test_nameless_versionless(pixi: Path, tmp_pixi_workspace: Path):
#     project_dir = repo_root().joinpath("tests", "data", "pixi_build", "name-and-version-less-package")
#
#     # Remove existing .pixi folders
#     shutil.rmtree(project_dir.joinpath(".pixi"), ignore_errors=True)
#
#     # Copy to workspace
#     shutil.copytree(project_dir, tmp_pixi_workspace, dirs_exist_ok=True)
#
#     # Get manifest
#     manifest = get_manifest(tmp_pixi_workspace)
#
#     # Install the environment
#     verify_cli_command(
#         [pixi, "list", "-v", "--locked", "--manifest-path", manifest],
#         stdout_contains=["rust-app", "1.2.3", "conda"]
#     )
