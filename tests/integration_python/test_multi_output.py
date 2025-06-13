import shutil
from pathlib import Path

from .common import verify_cli_command


def test_build(pixi: Path, build_data: Path, tmp_pixi_workspace: Path) -> None:
    project = "multi-output"
    test_data = build_data.joinpath(project)
    test_data.joinpath("pixi.lock").unlink(missing_ok=True)
    target_dir = tmp_pixi_workspace.joinpath(project)
    shutil.copytree(test_data, target_dir)

    verify_cli_command(
        [pixi, "build", "--manifest-path", target_dir, "--output-dir", target_dir],
    )

    # Ensure that exactly one conda package has been built
    built_packages = list(target_dir.glob("*.conda"))
    assert len(built_packages) == 3


def test_install(pixi: Path, build_data: Path, tmp_pixi_workspace: Path) -> None:
    project = "multi-output"
    test_data = build_data.joinpath(project)
    test_data.joinpath("pixi.lock").unlink(missing_ok=True)
    target_dir = tmp_pixi_workspace.joinpath(project)
    shutil.copytree(test_data, target_dir)

    verify_cli_command(
        [pixi, "install", "--manifest-path", target_dir],
    )
