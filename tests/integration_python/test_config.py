import shutil
from pathlib import Path

import pytest

from .common import get_manifest, verify_cli_command


@pytest.mark.slow
def test_pixi_build_cmake_env_config_without_target(
    pixi: Path, tmp_pixi_workspace: Path, test_data: Path
) -> None:
    """Test that env configuration without target specific configuration works correctly with pixi-build-cmake backend."""

    # Copy the cmake env config test workspace
    cmake_env_test_project = test_data.joinpath("pixi_build", "env-config-cmake-test")

    # Remove existing .pixi folders
    shutil.rmtree(cmake_env_test_project.joinpath(".pixi"), ignore_errors=True)

    # Copy to workspace
    shutil.copytree(cmake_env_test_project, tmp_pixi_workspace, dirs_exist_ok=True)

    # Get manifest
    manifest = get_manifest(tmp_pixi_workspace)

    # Install the package - this should show env vars in the build output
    verify_cli_command(
        [pixi, "install", "-v", "--manifest-path", manifest],
        stderr_contains=[
            "CUSTOM_BUILD_VAR=test_value",
            "PIXI_TEST_ENV=pixi_cmake_test",
            "BUILD_MESSAGE=hello_from_env",
        ],
    )


@pytest.mark.slow
def test_pixi_build_cmake_env_config_with_target(
    pixi: Path, tmp_pixi_workspace: Path, test_data: Path
) -> None:
    """Test that target-specific env configuration works correctly with pixi-build-cmake backend."""

    # Copy the target cmake env config test workspace
    cmake_target_env_test_project = test_data.joinpath("pixi_build", "env-config-target-cmake-test")

    # Remove existing .pixi folders
    shutil.rmtree(cmake_target_env_test_project.joinpath(".pixi"), ignore_errors=True)

    # Copy to workspace
    shutil.copytree(cmake_target_env_test_project, tmp_pixi_workspace, dirs_exist_ok=True)

    # Get manifest
    manifest = get_manifest(tmp_pixi_workspace)

    # Install the package - this should show env vars in the build output
    verify_cli_command(
        [pixi, "install", "-v", "--manifest-path", manifest],
        stderr_contains=[
            "GLOBAL_ENV_VAR=global_value",
            "UNIX_SPECIFIC_VAR=unix_value",
            "PLATFORM_TYPE=unix",
        ],
    )
