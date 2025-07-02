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
    env = {
        "PIXI_CACHE_DIR": str(tmp_pixi_workspace.joinpath("pixi_cache")),
    }
    # Remove existing .pixi folders
    shutil.rmtree(pixi_project.joinpath(".pixi"), ignore_errors=True)

    # Copy to workspace
    shutil.copytree(pixi_project, tmp_pixi_workspace, dirs_exist_ok=True)

    # Get manifest
    manifest = get_manifest(tmp_pixi_workspace)

    # Install the environment
    verify_cli_command(
        [pixi, "run", "--locked", "--manifest-path", manifest, "start"],
        env=env,
        stdout_contains="Build backend works",
    )
