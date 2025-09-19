import json
import os
import shutil
from pathlib import Path
from typing import Any, cast

import dotenv
import pytest

from .common import CURRENT_PLATFORM, Workspace, exec_extension, repo_root


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
        },
        "dependencies": {name: {"path": package_rel_dir}},
    }

    package_manifest = {
        "package": {
            "name": name,
            "version": "1.0.0",
            "build": {
                "backend": {"name": "pixi-build-rattler-build", "version": "*"},
                "configuration": {"debug-dir": str(debug_dir)},
            },
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


def _metadata_path() -> Path:
    return repo_root().joinpath("artifacts", "download-metadata.json")


def _load_artifact_metadata() -> dict[str, object]:
    metadata_file = _metadata_path()
    if not metadata_file.exists():
        return {}

    try:
        data: Any = json.loads(metadata_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive guard
        raise RuntimeError(
            f"Artifact metadata file at {metadata_file} is not valid JSON. Re-run 'pixi run download-artifacts'."
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError(
            f"Artifact metadata file at {metadata_file} must contain a JSON object. "
            "Re-run 'pixi run download-artifacts'."
        )

    return cast(dict[str, object], data)


def _validate_artifact_sources() -> None:
    metadata = _load_artifact_metadata()
    if not metadata:
        return

    checks = [
        ("prefix-dev/pixi", "PIXI_PR_NUMBER"),
        ("prefix-dev/pixi-build-backends", "BUILD_BACKENDS_PR_NUMBER"),
    ]

    for repo, env_var in checks:
        entry = metadata.get(repo)
        if not isinstance(entry, dict):
            continue

        source = entry.get("source")
        env_value = os.getenv(env_var, "").strip()

        if source == "pr":
            pr_number = str(entry.get("pr_number", "")).strip()
            if not pr_number:
                raise RuntimeError(
                    f"Artifact metadata for {repo} is missing a pull request number. Re-run 'pixi run download-artifacts'."
                )
            if not env_value:
                raise RuntimeError(
                    f"Artifacts for {repo} originate from PR #{pr_number}, but {env_var} is not set. "
                    "Set the environment variable or re-download the correct artifacts."
                )
            if env_value != pr_number:
                raise RuntimeError(
                    f"Artifacts for {repo} originate from PR #{pr_number}, but {env_var}={env_value!r}. "
                    "Update your environment or refresh the artifacts."
                )
        elif source == "branch":
            if env_value:
                branch = entry.get("branch", "main")
                raise RuntimeError(
                    f"Artifacts for {repo} originate from branch '{branch}', but {env_var}={env_value!r} is set. "
                    "Unset the environment variable or download the matching PR artifacts."
                )


@pytest.fixture(scope="session", autouse=True)
def load_dotenv() -> None:
    dotenv.load_dotenv(override=True)
    _validate_artifact_sources()


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
    Falls back to binaries downloaded into the artifacts directory.
    """
    pixi_bin_dir = os.getenv("PIXI_BIN_DIR")

    if pixi_bin_dir:
        pixi_bin_path = Path(pixi_bin_dir)
    else:
        project_root = repo_root()
        candidates = [
            project_root / "artifacts",
            project_root / "artifacts" / "pixi",
        ]
        pixi_bin_path = None
        for candidate in candidates:
            executable_candidate = candidate / exec_extension("pixi")
            if candidate.is_dir() and executable_candidate.is_file():
                pixi_bin_path = candidate
                break

        if pixi_bin_path is not None:
            os.environ["PIXI_BIN_DIR"] = str(pixi_bin_path)
            pixi_bin_dir = os.environ["PIXI_BIN_DIR"]

    if pixi_bin_dir is None and pixi_bin_path is None:
        raise ValueError(
            "Could not determine Pixi binary location. Set PIXI_BIN_DIR or run "
            "'pixi run download-artifacts --repo pixi'."
        )

    if pixi_bin_path is None or not pixi_bin_path.is_dir():
        raise ValueError(
            f"PIXI_BIN_DIR points to '{pixi_bin_dir}' which is not a valid directory. "
            "Please set it to a directory that exists and contains the Pixi executable."
        )

    pixi_executable = pixi_bin_path / exec_extension("pixi")

    if not pixi_executable.is_file():
        raise FileNotFoundError(
            f"Pixi executable not found at '{pixi_executable}'. Set PIXI_BIN_DIR or run "
            "'pixi run download-artifacts --repo pixi'."
        )

    return pixi_executable


@pytest.fixture(scope="session", autouse=True)
def build_backends(load_dotenv: None) -> None:
    """
    Sets up build backend environment variables for testing.

    Configures PIXI_BUILD_BACKEND_OVERRIDE environment variable with paths
    to the build backends.

    Requires the BUILD_BACKENDS_BIN_DIR environment variable to be set.
    Falls back to binaries downloaded into the artifacts directory.
    """
    build_backends_dir = os.getenv("BUILD_BACKENDS_BIN_DIR")

    backends = [
        "pixi-build-cmake",
        "pixi-build-python",
        "pixi-build-rattler-build",
        "pixi-build-rust",
    ]

    if build_backends_dir:
        build_backends_path = Path(build_backends_dir)
    else:
        project_root = repo_root()
        candidates = [
            project_root / "artifacts",
            project_root / "artifacts" / "pixi-build-backends",
        ]
        build_backends_path = None
        for candidate in candidates:
            if not candidate.is_dir():
                continue
            if all((candidate / exec_extension(backend)).is_file() for backend in backends):
                build_backends_path = candidate
                break

        if build_backends_path is not None:
            os.environ["BUILD_BACKENDS_BIN_DIR"] = str(build_backends_path)
            build_backends_dir = os.environ["BUILD_BACKENDS_BIN_DIR"]

    if build_backends_dir is None and build_backends_path is None:
        raise ValueError(
            "Could not determine build backend locations. Set BUILD_BACKENDS_BIN_DIR or run "
            "'pixi run download-artifacts --repo pixi-build-backends'."
        )

    if build_backends_path is None or not build_backends_path.is_dir():
        raise ValueError(
            f"BUILD_BACKENDS_BIN_DIR points to '{build_backends_dir}' which is not a valid directory. "
            "Please set it to a directory that exists and contains build backend definitions."
        )

    # Build the override string in the format: tool_name=/path/to/executable::tool_name2=...
    override_parts = []
    for backend in backends:
        backend_path = build_backends_path / exec_extension(backend)
        if not backend_path.is_file():
            raise FileNotFoundError(
                f"'{backend}' not found at '{backend_path}'. Set BUILD_BACKENDS_BIN_DIR "
                "or run 'pixi run download-artifacts --repo pixi-build-backends'."
            )

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
