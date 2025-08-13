import shutil
from pathlib import Path

import pytest
import tomli_w
import tomllib

from .common import ExitCode, exec_extension, git_test_repo, verify_cli_command


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


@pytest.mark.parametrize(
    "package_name",
    [
        "simple-package",
        pytest.param(
            None, marks=pytest.mark.xfail(reason="Inferring specs is not yet implemented")
        ),
    ],
)
@pytest.mark.parametrize(
    "relative",
    [True, False],
)
def test_install_path_dependency(
    pixi: Path, tmp_path: Path, build_data: Path, package_name: str | None, relative: bool
) -> None:
    """Test installing a pixi project from a git repository."""
    # Make it one level deeper so that we do no pollute git with the global
    pixi_home = tmp_path / "pixi_home"
    env = {"PIXI_HOME": str(pixi_home)}

    # Specify the project
    source_project = build_data.joinpath("simple-package")
    if relative:
        source_project = source_project.relative_to(Path.cwd())

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
    assert not source_from_manifest.is_absolute()
    assert manifest_path.parent.joinpath(source_from_manifest).resolve() == source_project.resolve()

    # Check that the package was installed
    simple_package = pixi_home / "bin" / exec_extension("simple-package")
    verify_cli_command([simple_package], env=env, stdout_contains="hello from simple-package")


@pytest.mark.parametrize(
    "relative",
    [True, False],
)
def test_sync(pixi: Path, tmp_path: Path, build_data: Path, relative: bool) -> None:
    """Test that global sync works when manifest contains a path dependency."""
    pixi_home = tmp_path / "pixi_home"
    env = {"PIXI_HOME": str(pixi_home)}

    # Prepare manifest path
    manifest_path = pixi_home.joinpath("manifests", "pixi-global.toml")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    # Set up source project path (absolute or relative to manifest dir)
    source_project = build_data.joinpath("simple-package")
    if relative:
        # Make path relative to manifest directory
        source_project_str = str(source_project.relative_to(manifest_path.parent, walk_up=True))
    else:
        source_project_str = str(source_project.resolve())

    manifest_content = {
        "envs": {
            "simple-package": {
                "channels": ["conda-forge"],
                "dependencies": {"simple-package": {"path": source_project_str}},
                "exposed": {"simple-package": "simple-package"},
            }
        }
    }
    manifest_path.write_text(tomli_w.dumps(manifest_content))

    # Run global sync
    verify_cli_command([pixi, "global", "sync"], env=env)

    # Check that the package was installed
    simple_package = pixi_home / "bin" / exec_extension("simple-package")
    verify_cli_command([simple_package], env=env, stdout_contains="hello from simple-package")


@pytest.mark.parametrize(
    "package_name",
    [
        "simple-package",
        pytest.param(
            None, marks=pytest.mark.xfail(reason="Inferring specs is not yet implemented")
        ),
    ],
)
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


def test_add_git_repository_to_existing_environment(
    pixi: Path, tmp_path: Path, build_data: Path, dummy_channel_1: Path
) -> None:
    """Test adding a git-based source package to an existing global environment."""
    # Make it one level deeper so that we do no pollute git with the global
    pixi_home = tmp_path / "pixi_home"
    env = {"PIXI_HOME": str(pixi_home)}

    # First create a basic environment with a regular package
    verify_cli_command(
        [
            pixi,
            "global",
            "install",
            "--channel",
            dummy_channel_1,
            "--environment",
            "test_env",
            "dummy-f",
        ],
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


def test_update(pixi: Path, tmp_path: Path, build_data: Path) -> None:
    """Test that pixi global update works with path dependencies."""
    # Make it one level deeper so that we do no pollute git with the global
    pixi_home = tmp_path / "pixi_home"
    env = {"PIXI_HOME": str(pixi_home)}

    # Create a modifiable copy of simple-package
    source_project = tmp_path / "simple-package-copy"

    # by using shutil.copy, we change the metadata and therefore get a higher timestamp
    # that way we make sure that we don't use old caches
    shutil.copytree(
        build_data.joinpath("simple-package"), source_project, copy_function=shutil.copy
    )

    # Install the package from the path
    verify_cli_command(
        [pixi, "global", "install", "--path", source_project, "simple-package"],
        env=env,
    )

    # Check that the package was installed with original message
    simple_package = pixi_home / "bin" / exec_extension("simple-package")
    verify_cli_command([simple_package], env=env, stdout_contains="hello from simple-package")

    # Modify the package to output a different message
    recipe_path = source_project / "recipe.yaml"
    recipe_content = recipe_path.read_text()
    updated_recipe = recipe_content.replace(
        "echo hello from simple-package", "echo goodbye from simple-package"
    )
    recipe_path.write_text(updated_recipe)

    # Run global sync - this should NOT pick up the changes
    verify_cli_command([pixi, "global", "sync"], env=env)

    # Verify the old message is still there (sync doesn't update)
    verify_cli_command([simple_package], env=env, stdout_contains="hello from simple-package")

    # Run global update - this SHOULD pick up the changes
    verify_cli_command([pixi, "global", "update"], env=env)

    # Verify the new message is now there
    verify_cli_command([simple_package], env=env, stdout_contains="goodbye from simple-package")
