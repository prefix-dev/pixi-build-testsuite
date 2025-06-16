import shutil
from pathlib import Path

from .common import ExitCode, verify_cli_command


def test_build(pixi: Path, build_data: Path, tmp_pixi_workspace: Path) -> None:
    project = "multi-output"
    test_data = build_data.joinpath(project)
    test_data.joinpath("pixi.lock").unlink(missing_ok=True)
    shutil.copytree(test_data, tmp_pixi_workspace, dirs_exist_ok=True)
    package_manifest = tmp_pixi_workspace.joinpath("recipe", "pixi.toml")

    env = {
        "PIXI_CACHE_DIR": str(tmp_pixi_workspace.joinpath("pixi_cache")),
    }
    verify_cli_command(
        [pixi, "build", "--manifest-path", package_manifest, "--output-dir", tmp_pixi_workspace],
        env=env,
    )

    # Ensure that exactly three conda packages have been built
    built_packages = list(tmp_pixi_workspace.glob("*.conda"))
    assert len(built_packages) == 3


def test_install(pixi: Path, build_data: Path, tmp_pixi_workspace: Path) -> None:
    project = "multi-output"
    test_data = build_data.joinpath(project)
    test_data.joinpath("pixi.lock").unlink(missing_ok=True)
    shutil.copytree(test_data, tmp_pixi_workspace, dirs_exist_ok=True)

    env = {
        "PIXI_CACHE_DIR": str(tmp_pixi_workspace.joinpath("pixi_cache")),
    }
    verify_cli_command([pixi, "install", "--manifest-path", tmp_pixi_workspace], env=env)

    verify_cli_command(
        [pixi, "install", "--locked", "--manifest-path", tmp_pixi_workspace], env=env
    )


def test_available_packages(pixi: Path, build_data: Path, tmp_pixi_workspace: Path) -> None:
    project = "multi-output"
    test_data = build_data.joinpath(project)
    test_data.joinpath("pixi.lock").unlink(missing_ok=True)
    shutil.copytree(test_data, tmp_pixi_workspace, dirs_exist_ok=True)

    env = {
        "PIXI_CACHE_DIR": str(tmp_pixi_workspace.joinpath("pixi_cache")),
    }

    # foobar-desktop is a direct dependency, so it should be properly installed
    verify_cli_command(
        [pixi, "run", "--manifest-path", tmp_pixi_workspace, "foobar-desktop"],
        env=env,
        stdout_contains="Hello from foobar-desktop",
    )
    # foobar is a dependency of foobar-desktop, so it should be there as well
    verify_cli_command(
        [pixi, "run", "--manifest-path", tmp_pixi_workspace, "foobar"],
        env=env,
        stdout_contains="Hello from foobar",
    )
    # bizbar is a output of the recipe, but we don't request it
    # So it shouldn't be part of the environment
    verify_cli_command(
        [pixi, "run", "--manifest-path", tmp_pixi_workspace, "bizbar"],
        env=env,
        expected_exit_code=ExitCode.COMMAND_NOT_FOUND,
    )
