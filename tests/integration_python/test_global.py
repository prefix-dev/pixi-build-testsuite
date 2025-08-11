from pathlib import Path

import pytest
import tomllib

from .common import ExitCode, exec_extension, git_test_repo, verify_cli_command


@pytest.mark.slow
@pytest.mark.xfail(reason="This isn't implemented yet")
def test_install_multi_output(
    pixi: Path,
    tmp_path: Path,
    build_data: Path,
) -> None:
    """Test installing a pixi project from a git repository."""
    # Make it one level deeper so that we do no pollute git with the global
    pixi_home = tmp_path / "pixi_home"
    env = {"PIXI_HOME": str(pixi_home)}

    # Specify the project
    source_project = build_data.joinpath("multi-output")

    # Test install without any specs mentioned
    # It should tell you which outputs are available
    verify_cli_command(
        [pixi, "global", "install", "--path", source_project],
        ExitCode.FAILURE,
        env=env,
        stderr_contains=["multiple outputs", "foobar", "bizbar", "foobar-desktop"],
    )

    # Test install and explicitly requesting `foobar-desktop`
    verify_cli_command(
        [pixi, "global", "install", "--path", source_project, "foobar-desktop"], env=env
    )

    # Check that the package was installed
    foobar_desktop = pixi_home / "bin" / exec_extension("foobar-desktop")
    verify_cli_command([foobar_desktop], env=env, stdout_contains="Hello from foobar-desktop")


# TODO: run without spec as soon as it's implemented
# @pytest.mark.parametrize("package_name", [None, "simple-package"])
@pytest.mark.parametrize("package_name", ["simple-package"])
def test_install_path_dependency(
    pixi: Path,
    tmp_path: Path,
    build_data: Path,
    package_name: str | None,
) -> None:
    """Test installing a pixi project from a git repository."""
    # Make it one level deeper so that we do no pollute git with the global
    pixi_home = tmp_path / "pixi_home"
    env = {"PIXI_HOME": str(pixi_home)}

    # Specify the project
    source_project = build_data.joinpath("simple-package")

    # Build command based on whether package name is provided
    cmd: list[str | Path] = [pixi, "global", "install", "--path", source_project]
    if package_name:
        cmd.append(package_name)

    # Test install
    verify_cli_command(cmd, env=env)

    # Ensure that path is relative to the manifest directory
    manifest_path = pixi_home.joinpath("manifests", "pixi-global.toml")
    manifest = tomllib.loads(manifest_path.read_text())
    source_from_manifest = Path(
        manifest["envs"]["simple-package"]["dependencies"]["simple-package"]["path"]
    )
    assert source_from_manifest.relative_to(manifest_path.parent) == source_project

    # Check that the package was installed
    simple_package = pixi_home / "bin" / exec_extension("simple-package")
    verify_cli_command([simple_package], env=env, stdout_contains="hello from simple-package")


# TODO: run without spec as soon as it's implemented
# @pytest.mark.parametrize("package_name", [None, "simple-package"])
@pytest.mark.parametrize("package_name", ["simple-package"])
def test_install_git_repository(
    pixi: Path,
    tmp_path: Path,
    build_data: Path,
    package_name: str | None,
) -> None:
    """Test installing a pixi project from a git repository."""
    # Make it one level deeper so that we do no pollute git with the global
    pixi_home = tmp_path / "pixi_home"
    env = {"PIXI_HOME": str(pixi_home)}

    # Specify the project
    source_project = build_data.joinpath("simple-package")

    # Create git repository
    git_url = git_test_repo(source_project, "test-project", tmp_path)

    # Build command based on whether package name is provided
    cmd: list[str | Path] = [pixi, "global", "install", "--git", git_url]
    if package_name:
        cmd.append(package_name)

    # Test git install
    verify_cli_command(cmd, env=env)

    # Check that the package was installed
    simple_package = pixi_home / "bin" / exec_extension("simple-package")
    verify_cli_command([simple_package], env=env, stdout_contains="hello from simple-package")


@pytest.mark.slow
def test_add_git_repository_to_existing_environment(
    pixi: Path,
    tmp_path: Path,
    build_data: Path,
) -> None:
    """Test adding a git-based source package to an existing global environment."""
    # Make it one level deeper so that we do no pollute git with the global
    pixi_home = tmp_path / "pixi_home"
    env = {"PIXI_HOME": str(pixi_home)}

    # First create a basic environment with a regular package
    verify_cli_command(
        [pixi, "global", "install", "--environment", "test_env", "python"],
        env=env,
    )

    # Specify the source
    source_project = build_data.joinpath("simple-package")

    # Create git repository
    git_url = git_test_repo(source_project, "test-project", tmp_path)

    # Test adding git package to existing environment
    verify_cli_command(
        [
            pixi,
            "global",
            "add",
            "--environment",
            "test_env",
            "--git",
            git_url,
            "simple-package",
            "--expose",
            "simple-package=simple-package",
        ],
        env=env,
    )

    # Check that the package was added to the existing environment
    simple_package = pixi_home / "bin" / exec_extension("simple-package")
    verify_cli_command([simple_package], env=env, stdout_contains="hello from simple-package")
