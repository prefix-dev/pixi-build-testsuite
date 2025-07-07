import json
import shutil
from pathlib import Path

import pytest

from .common import ExitCode, Workspace, verify_cli_command


def test_build_conda_package(
    pixi: Path,
    simple_workspace: Workspace,
) -> None:
    simple_workspace.write_files()
    verify_cli_command(
        [
            pixi,
            "build",
            "-v",
            "--manifest-path",
            simple_workspace.package_dir,
            "--output-dir",
            simple_workspace.workspace_dir,
        ],
    )

    # Ensure that exactly one conda package has been built
    built_packages = list(simple_workspace.workspace_dir.glob("*.conda"))
    assert len(built_packages) == 1


def test_build_conda_package_variants(
    pixi: Path, simple_workspace: Workspace, multiple_versions_channel_1: str
) -> None:
    # Add package3 to build dependencies of recipe
    simple_workspace.recipe.setdefault("requirements", {}).setdefault("build", []).append(
        "package3"
    )

    # Add package3 to build-variants
    variants = ["0.1.0", "0.2.0"]
    simple_workspace.workspace_manifest["workspace"].setdefault("channels", []).insert(
        0, multiple_versions_channel_1
    )
    simple_workspace.workspace_manifest["workspace"].setdefault("build-variants", {})[
        "package3"
    ] = variants

    # Write files
    simple_workspace.write_files()

    # Build packages
    verify_cli_command(
        [
            pixi,
            "build",
            "-v",
            "--manifest-path",
            simple_workspace.package_dir,
            "--output-dir",
            simple_workspace.workspace_dir,
        ],
    )

    # Ensure that the correct variants are requested
    conda_build_params_file = simple_workspace.debug_dir.joinpath("conda_build_params.json")
    conda_build_params = json.loads(conda_build_params_file.read_text())
    assert conda_build_params["variantConfiguration"]["package3"] == variants

    # Ensure that exactly two conda packages have been built
    built_packages = list(simple_workspace.workspace_dir.glob("*.conda"))
    assert len(built_packages) == 2
    for package in built_packages:
        assert package.exists()


def test_no_change_should_be_fully_cached(pixi: Path, simple_workspace: Workspace) -> None:
    simple_workspace.write_files()
    verify_cli_command(
        [
            pixi,
            "install",
            "-v",
            "--manifest-path",
            simple_workspace.workspace_dir,
        ]
    )

    conda_metadata_params = simple_workspace.debug_dir.joinpath("conda_metadata_params.json")
    conda_build_params = simple_workspace.debug_dir.joinpath("conda_build_params.json")

    assert conda_metadata_params.is_file()
    assert conda_build_params.is_file()

    # Remove the files to get a clean state
    conda_metadata_params.unlink()
    conda_build_params.unlink()

    verify_cli_command(
        [
            pixi,
            "install",
            "-v",
            "--manifest-path",
            simple_workspace.workspace_dir,
        ]
    )

    # Everything should be cached, so no getMetadata or build call
    assert not conda_metadata_params.is_file()
    assert not conda_build_params.is_file()


def test_source_change_trigger_rebuild(pixi: Path, simple_workspace: Workspace) -> None:
    simple_workspace.write_files()
    verify_cli_command(
        [
            pixi,
            "install",
            "-v",
            "--manifest-path",
            simple_workspace.workspace_dir,
        ],
    )

    conda_build_params = simple_workspace.debug_dir.joinpath("conda_build_params.json")

    assert conda_build_params.is_file()

    # Remove the conda build params to get a clean state
    conda_build_params.unlink()

    # Touch the recipe
    simple_workspace.recipe_path.touch()

    verify_cli_command(
        [
            pixi,
            "install",
            "-v",
            "--manifest-path",
            simple_workspace.workspace_dir,
        ],
    )

    # Touching the recipe should trigger a rebuild and therefore create the file
    assert conda_build_params.is_file()


def test_project_model_change_trigger_rebuild(
    pixi: Path, simple_workspace: Workspace, dummy_channel_1: Path
) -> None:
    simple_workspace.write_files()
    verify_cli_command(
        [
            pixi,
            "install",
            "-v",
            "--manifest-path",
            simple_workspace.workspace_dir,
        ],
    )

    conda_build_params = simple_workspace.debug_dir.joinpath("conda_build_params.json")

    assert conda_build_params.is_file()

    # Remove the conda build params to get a clean state
    conda_build_params.unlink()

    # modify extra-input-globs
    simple_workspace.package_manifest["package"]["build"]["configuration"].setdefault(
        "extra-input-globs", ["*.md"]
    )
    simple_workspace.write_files()
    verify_cli_command(
        [
            pixi,
            "install",
            "-v",
            "--manifest-path",
            simple_workspace.workspace_dir,
        ],
    )

    # modifying the project model should trigger a rebuild and therefore create a file
    assert conda_build_params.is_file()


@pytest.mark.slow
def test_editable_pyproject(pixi: Path, build_data: Path, tmp_pixi_workspace: Path) -> None:
    """
    This one tries to run the Python based rich example project,
    installed as a normal package by overriding with an environment variable.
    """
    project = "editable-pyproject"
    test_data = build_data.joinpath(project)

    target_dir = tmp_pixi_workspace.joinpath(project)
    shutil.copytree(test_data, target_dir)
    manifest_path = target_dir.joinpath("pyproject.toml")

    verify_cli_command(
        [
            pixi,
            "install",
            "-v",
            "--manifest-path",
            manifest_path,
        ],
    )

    # Verify that package is installed as editable
    verify_cli_command(
        [
            pixi,
            "run",
            "-v",
            "--manifest-path",
            manifest_path,
            "check-editable",
        ],
        stdout_contains="The package is installed as editable.",
    )


@pytest.mark.slow
def test_non_editable_pyproject(pixi: Path, build_data: Path, tmp_pixi_workspace: Path) -> None:
    """
    This one tries to run the Python based rich example project,
    installed as a normal package by overriding with an environment variable.
    """
    project = "editable-pyproject"
    test_data = build_data.joinpath(project)

    target_dir = tmp_pixi_workspace.joinpath(project)
    shutil.copytree(test_data, target_dir)
    manifest_path = target_dir.joinpath("pyproject.toml")

    env = {
        "BUILD_EDITABLE_PYTHON": "false",
    }

    verify_cli_command(
        [
            pixi,
            "install",
            "-v",
            "--manifest-path",
            manifest_path,
        ],
        env=env,
    )

    # Verify that package is installed as editable
    verify_cli_command(
        [
            pixi,
            "run",
            "-v",
            "--manifest-path",
            manifest_path,
            "check-editable",
        ],
        ExitCode.FAILURE,
        env=env,
        stdout_contains="The package is not installed as editable.",
    )


@pytest.mark.slow
def test_build_using_rattler_build_backend(
    pixi: Path,
    tmp_pixi_workspace: Path,
    build_data: Path,
) -> None:
    test_data = build_data.joinpath("rattler-build-backend")
    shutil.copytree(test_data / "array-api-extra", tmp_pixi_workspace, dirs_exist_ok=True)

    manifest_path = tmp_pixi_workspace / "pixi.toml"

    # Running pixi build should build the recipe.yaml
    verify_cli_command(
        [pixi, "build", "-v", "--manifest-path", manifest_path, "--output-dir", tmp_pixi_workspace],
    )

    # really make sure that conda package was built
    package_to_be_built = next(manifest_path.parent.glob("*.conda"))

    assert "array-api-extra" in package_to_be_built.name
    assert package_to_be_built.exists()


def test_error_manifest_deps(pixi: Path, build_data: Path, tmp_pixi_workspace: Path) -> None:
    test_data = build_data.joinpath("rattler-build-backend")
    # copy the whole smokey project to the tmp_pixi_workspace
    shutil.copytree(test_data / "smokey", tmp_pixi_workspace / "smokey")
    manifest_path = tmp_pixi_workspace / "smokey" / "pixi.toml"

    verify_cli_command(
        [
            pixi,
            "install",
            "-v",
            "--manifest-path",
            manifest_path,
        ],
        expected_exit_code=ExitCode.FAILURE,
        stderr_contains="Specifying dependencies",
    )


def test_error_manifest_deps_no_default(
    pixi: Path, build_data: Path, tmp_pixi_workspace: Path
) -> None:
    test_data = build_data.joinpath("rattler-build-backend")
    # copy the whole smokey2 project to the tmp_pixi_workspace
    shutil.copytree(test_data / "smokey2", tmp_pixi_workspace / "smokey2")
    manifest_path = tmp_pixi_workspace / "smokey2" / "pixi.toml"

    verify_cli_command(
        [
            pixi,
            "install",
            "-v",
            "--manifest-path",
            manifest_path,
        ],
        expected_exit_code=ExitCode.FAILURE,
        stderr_contains="Specifying dependencies",
    )


@pytest.mark.slow
def test_recursive_source_run_dependencies(
    pixi: Path, build_data: Path, tmp_pixi_workspace: Path
) -> None:
    """
    Test whether recursive source dependencies work properly if
    they are specified in the `run-dependencies` section
    """
    project = "recursive_source_run_dep"
    test_data = build_data.joinpath(project)

    shutil.copytree(test_data, tmp_pixi_workspace, dirs_exist_ok=True)
    manifest_path = tmp_pixi_workspace.joinpath("pixi.toml")

    verify_cli_command(
        [
            pixi,
            "install",
            "-v",
            "--manifest-path",
            manifest_path,
        ],
    )

    # Package B is a dependency of Package A
    # Check that it is properly installed
    verify_cli_command(
        [
            pixi,
            "run",
            "-v",
            "--manifest-path",
            manifest_path,
            "package-b",
        ],
        stdout_contains="hello from package-b",
    )


@pytest.mark.slow
def test_maturin(pixi: Path, build_data: Path, tmp_pixi_workspace: Path) -> None:
    project = "maturin"
    test_data = build_data.joinpath(project)

    shutil.copytree(test_data, tmp_pixi_workspace, dirs_exist_ok=True)
    manifest_path = tmp_pixi_workspace.joinpath("pixi.toml")

    verify_cli_command(
        [
            pixi,
            "run",
            "--manifest-path",
            manifest_path,
            "start",
        ],
        stdout_contains="3 + 5 = 8",
    )
