import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import dotenv
import pytest
import tomli_w
import yaml

from .common import CURRENT_PLATFORM, exec_extension


@pytest.fixture
def build_data(test_data: Path) -> Path:
    """
    Returns the pixi build test data
    """
    return test_data.joinpath("pixi_build")


@pytest.fixture
def examples_dir() -> Path:
    """
    Returns the path to the examples directory in the root of the repository
    """
    return Path(__file__).parents[3].joinpath("examples").resolve()


@dataclass
class Workspace:
    recipe: dict[str, Any]
    workspace_manifest: dict[str, Any]
    workspace_dir: Path
    package_manifest: dict[str, Any]
    package_dir: Path
    recipe_path: Path
    debug_dir: Path

    def write_files(self) -> None:
        self.recipe_path.write_text(yaml.dump(self.recipe))
        workspace_manifest_path = self.workspace_dir.joinpath("pixi.toml")
        workspace_manifest_path.write_text(tomli_w.dumps(self.workspace_manifest))
        package_manifest_path = self.package_dir.joinpath("pixi.toml")
        package_manifest_path.write_text(tomli_w.dumps(self.package_manifest))


@pytest.fixture
def simple_workspace(tmp_pixi_workspace: Path, request: pytest.FixtureRequest) -> Workspace:
    name = request.node.name

    workspace_dir = tmp_pixi_workspace.joinpath("workspace")
    workspace_dir.mkdir()
    shutil.move(tmp_pixi_workspace.joinpath(".pixi"), workspace_dir.joinpath(".pixi"))

    debug_dir = tmp_pixi_workspace.joinpath("debug_dir")
    debug_dir.mkdir()

    recipe = {"package": {"name": name, "version": "1.0.0"}}

    package_rel_dir = "package"

    workspace_manifest = {
        "workspace": {
            "channels": [
                "https://prefix.dev/pixi-build-backends",
                "https://prefix.dev/conda-forge",
            ],
            "preview": ["pixi-build"],
            "platforms": [CURRENT_PLATFORM],
            "name": name,
            "version": "1.0.0",
        },
        "dependencies": {name: {"path": package_rel_dir}},
    }

    package_manifest = {
        "package": {
            "build": {
                "backend": {"name": "pixi-build-rattler-build", "version": "0.1.*"},
                "configuration": {"debug-dir": str(debug_dir)},
            }
        },
    }

    package_dir = workspace_dir.joinpath(package_rel_dir)
    package_dir.mkdir(exist_ok=True)
    recipe_path = package_dir.joinpath("recipe.yaml")

    return Workspace(
        recipe,
        workspace_manifest,
        workspace_dir,
        package_manifest,
        package_dir,
        recipe_path,
        debug_dir,
    )


@pytest.fixture(scope="session", autouse=True)
def load_dotenv() -> None:
    dotenv.load_dotenv()


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--pixi-build",
        action="store",
        default="release",
        help="Specify the pixi build type (e.g., release or debug)",
    )


@pytest.fixture
def pixi() -> Path:
    """
    Returns the path to the Pixi executable.

    Uses the PIXI_BIN_DIR environment variable to locate the Pixi directory.
    Locally, this is typically done via the .env file.
    """
    pixi_bin_dir = os.getenv("PIXI_BIN_DIR")
    if not pixi_bin_dir:
        raise ValueError(
            "PIXI_BIN_DIR environment variable is not set. "
            "Please set it to the directory containing the Pixi executable."
        )

    pixi_bin_path = Path(pixi_bin_dir)
    if not pixi_bin_path.is_dir():
        raise ValueError(
            f"PIXI_BIN_DIR points to '{pixi_bin_dir}' which is not a valid directory. "
            "Please set it to a directory that exists and contains the Pixi executable."
        )

    pixi_executable = pixi_bin_path / exec_extension("pixi")

    if not pixi_executable.is_file():
        raise FileNotFoundError(f"Pixi executable not found at '{pixi_executable}'.")

    return pixi_executable


@pytest.fixture(scope="session", autouse=True)
def build_backends(load_dotenv: None) -> None:
    """
    Sets up build backend environment variables for testing.

    Configures PIXI_BUILD_BACKEND_OVERRIDE environment variable with paths
    to the build backends.

    Requires the BUILD_BACKENDS_BIN_DIR environment variable to be set.
    Locally, this is typically done via the .env file.
    """
    build_backends_dir = os.getenv("BUILD_BACKENDS_BIN_DIR")

    if not build_backends_dir:
        raise ValueError(
            "BUILD_BACKENDS_BIN_DIR environment variable is not set. "
            "Please set it to a directory that contains build backend definitions."
        )

    build_backends_path = Path(build_backends_dir)
    if not build_backends_path.is_dir():
        raise ValueError(
            f"BUILD_BACKENDS_BIN_DIR points to '{build_backends_dir}' which is not a valid directory. "
            "Please set it to a directory that exists and contains build backend definitions."
        )

    # Define the build backends
    backends = [
        "pixi-build-cmake",
        "pixi-build-python",
        "pixi-build-rattler-build",
        "pixi-build-rust",
    ]

    # Build the override string in the format: tool_name=/path/to/executable::tool_name2=...
    override_parts = []
    for backend in backends:
        backend_path = build_backends_path / exec_extension(backend)
        if not backend_path.is_file():
            raise FileNotFoundError(f"'{backend}' not found at '{backend_path}'.")

        override_parts.append(f"{backend}={backend_path}")

    override_value = ",".join(override_parts)
    os.environ["PIXI_BUILD_BACKEND_OVERRIDE"] = override_value


@pytest.fixture
def tmp_pixi_workspace(tmp_path_factory: pytest.TempPathFactory) -> Path:
    # Create a short temporary directory name to avoid long path issues on windows.
    tmp_path = tmp_path_factory.mktemp("px")

    pixi_config = """
# Reset to defaults
default-channels = ["conda-forge"]
shell.change-ps1 = true
tls-no-verify = false
detached-environments = false
pinning-strategy = "semver"

[concurrency]
downloads = 50

[experimental]
use-environment-activation-cache = false

# Enable sharded repodata
[repodata-config."https://prefix.dev/"]
disable-sharded = false
"""
    dot_pixi = tmp_path.joinpath(".pixi")
    dot_pixi.mkdir()
    dot_pixi.joinpath("config.toml").write_text(pixi_config)
    return tmp_path


@pytest.fixture
def test_data() -> Path:
    return Path(__file__).parents[1].joinpath("data").resolve()


@pytest.fixture
def channels(test_data: Path) -> Path:
    return test_data.joinpath("channels", "channels")


@pytest.fixture
def dummy_channel_1(channels: Path) -> str:
    return channels.joinpath("dummy_channel_1").as_uri()


@pytest.fixture
def multiple_versions_channel_1(channels: Path) -> str:
    return channels.joinpath("multiple_versions_channel_1").as_uri()
