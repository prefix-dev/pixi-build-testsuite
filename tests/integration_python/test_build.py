import json
import shutil
from typing import Any, Iterator
from pathlib import Path

import pytest
import tomli_w
import tomllib
import yaml

from .common import (
    CURRENT_PLATFORM,
    ExitCode,
    Workspace,
    copy_manifest,
    copytree_with_local_backend,
    verify_cli_command,
)
from .conftest import LocalGitRepo


def test_build_conda_package(
    pixi: Path,
    simple_workspace: Workspace,
) -> None:
    simple_workspace.write_files()
    verify_cli_command(
        [
            pixi,
            "build",
            "--manifest-path",
            simple_workspace.package_dir,
            "--output-dir",
            simple_workspace.workspace_dir,
        ],
    )

    # Ensure that we don't create directories we don't need
    assert not simple_workspace.workspace_dir.joinpath("noarch").exists()
    assert not simple_workspace.workspace_dir.joinpath(CURRENT_PLATFORM).exists()

    # Ensure that exactly one conda package has been built
    built_packages = list(simple_workspace.workspace_dir.glob("*.conda"))
    assert len(built_packages) == 1


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

    conda_metadata_params = simple_workspace.debug_dir.joinpath("conda_outputs_params.json")
    conda_build_params = simple_workspace.debug_dir.joinpath("conda_build_v1_params.json")

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

    conda_build_params = simple_workspace.debug_dir.joinpath("conda_outputs_params.json")

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

    conda_build_params = simple_workspace.debug_dir.joinpath("conda_build_v1_params.json")

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
    copytree_with_local_backend(test_data, target_dir)
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
    copytree_with_local_backend(test_data, target_dir)
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
    copytree_with_local_backend(
        test_data / "array-api-extra", tmp_pixi_workspace, dirs_exist_ok=True
    )

    manifest_path = tmp_pixi_workspace / "pixi.toml"

    # Running pixi build should build the recipe.yaml
    verify_cli_command(
        [pixi, "build", "-v", "--manifest-path", manifest_path, "--output-dir", tmp_pixi_workspace],
    )

    # really make sure that conda package was built
    package_to_be_built = next(manifest_path.parent.glob("*.conda"))

    assert "array-api-extra" in package_to_be_built.name
    assert package_to_be_built.exists()

    # check that immediately repeating the build also works (prefix-dev/pixi-build-backends#287)
    verify_cli_command(
        [pixi, "build", "-v", "--manifest-path", manifest_path, "--output-dir", tmp_pixi_workspace],
    )


@pytest.mark.parametrize(
    ("backend", "non_incremental_evidence"),
    [("pixi-build-rust", "Compiling simple-app"), ("pixi-build-cmake", "Configuring done")],
)
def test_incremental_builds(
    pixi: Path,
    tmp_pixi_workspace: Path,
    build_data: Path,
    backend: str,
    non_incremental_evidence: str,
) -> None:
    test_workspace = build_data / "minimal-backend-workspaces" / backend
    copytree_with_local_backend(test_workspace, tmp_pixi_workspace, dirs_exist_ok=True)
    manifest_path = tmp_pixi_workspace / "pixi.toml"

    verify_cli_command(
        [pixi, "build", "-v", "--manifest-path", manifest_path, "--output-dir", tmp_pixi_workspace],
        stderr_contains=non_incremental_evidence,
        strip_ansi=True,
    )

    # immediately repeating the build should give evidence of incremental compilation
    verify_cli_command(
        [pixi, "build", "-v", "--manifest-path", manifest_path, "--output-dir", tmp_pixi_workspace],
        stderr_excludes=non_incremental_evidence,
        strip_ansi=True,
    )


def test_error_manifest_deps(pixi: Path, build_data: Path, tmp_pixi_workspace: Path) -> None:
    test_data = build_data.joinpath("rattler-build-backend")
    # copy the whole smokey project to the tmp_pixi_workspace
    copytree_with_local_backend(test_data / "smokey", tmp_pixi_workspace / "smokey")
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
        stderr_contains="Please specify all binary dependencies in the recipe",
    )


def test_error_manifest_deps_no_default(
    pixi: Path, build_data: Path, tmp_pixi_workspace: Path
) -> None:
    test_data = build_data.joinpath("rattler-build-backend")
    # copy the whole smokey2 project to the tmp_pixi_workspace
    copytree_with_local_backend(test_data / "smokey2", tmp_pixi_workspace / "smokey2")
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
        stderr_contains="Please specify all binary dependencies in the recipe",
    )


def test_rattler_build_source_dependency(
    pixi: Path, build_data: Path, tmp_pixi_workspace: Path
) -> None:
    test_data = build_data.joinpath("rattler-build-backend")
    # copy the whole smokey2 project to the tmp_pixi_workspace
    copytree_with_local_backend(
        test_data / "source-dependency", tmp_pixi_workspace / "source-dependency"
    )
    manifest_path = tmp_pixi_workspace / "source-dependency" / "b" / "pixi.toml"

    verify_cli_command(
        [
            pixi,
            "install",
            "-v",
            "--manifest-path",
            manifest_path,
        ],
        expected_exit_code=ExitCode.SUCCESS,
        stderr_contains="hello from package a!",
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

    copytree_with_local_backend(test_data, tmp_pixi_workspace, dirs_exist_ok=True)
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

    copytree_with_local_backend(test_data, tmp_pixi_workspace, dirs_exist_ok=True)
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


@pytest.mark.slow
def test_recursive_source_build_dependencies(
    pixi: Path, build_data: Path, tmp_pixi_workspace: Path
) -> None:
    """
    Test whether recursive source dependencies work properly if
    they are specified in the `host-dependencies` section
    """
    project = "recursive_source_build_dep"
    test_data = build_data.joinpath(project)

    copytree_with_local_backend(test_data, tmp_pixi_workspace, dirs_exist_ok=True)
    manifest_path = tmp_pixi_workspace.joinpath("pixi.toml")

    verify_cli_command(
        [
            pixi,
            "lock",
            "--manifest-path",
            manifest_path,
        ],
    )

    # Package B is a dependency of Package A
    # Check that Package A works properly and that the output is valid
    verify_cli_command(
        [
            pixi,
            "run",
            "--frozen",
            "--manifest-path",
            manifest_path,
            "start",
        ],
        stdout_contains=["Package A application starting", "5 + 3 = 8"],
    )


@pytest.mark.slow
def test_source_path(pixi: Path, build_data: Path, tmp_pixi_workspace: Path) -> None:
    """
    Test path in `[package.build.source]`
    """
    project = "cpp-with-path-to-source"
    test_data = build_data.joinpath(project)

    copytree_with_local_backend(
        test_data, tmp_pixi_workspace, dirs_exist_ok=True, copy_function=copy_manifest
    )

    verify_cli_command(
        [
            pixi,
            "build",
            "--manifest-path",
            tmp_pixi_workspace,
            "--output-dir",
            tmp_pixi_workspace,
        ],
    )

    # Ensure that exactly one conda package has been built
    built_packages = list(tmp_pixi_workspace.glob("*.conda"))
    assert len(built_packages) == 1


@pytest.mark.slow
def test_extra_args(pixi: Path, build_data: Path, tmp_pixi_workspace: Path) -> None:
    """
    Check that `package.build.config.extra-args` are picked up,
    and can be used to alter the build directory for meson-python.
    """
    project = "python-builddir"
    test_data = build_data.joinpath(project)

    target_dir = tmp_pixi_workspace.joinpath(project)
    copytree_with_local_backend(test_data, target_dir)
    manifest_path = target_dir.joinpath("pixi.toml")

    verify_cli_command(
        [
            pixi,
            "install",
            "-v",
            "--manifest-path",
            manifest_path,
        ],
    )
    assert target_dir.joinpath("src", "mybuilddir", "build.ninja").is_file()


def _git_source_entries(lock_file: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(lock_file.read_text())

    def iter_entries() -> Any:
        yield from data.get("packages", [])

        for env_cfg in data.get("environments", {}).values():
            for platform_packages in env_cfg.get("packages", {}).values():
                yield from platform_packages

    serialized_sources: list[dict[str, Any]] = []
    for entry in iter_entries():
        if isinstance(entry, dict) and entry.get("conda") == ".":
            package_build_source = entry.get("package_build_source")
            if package_build_source is not None:
                serialized_sources.append(package_build_source)

    assert serialized_sources, (
        "expected at least one git package with package_build_source in pixi.lock"
    )
    return serialized_sources


def extract_git_sources(lock_file: Path) -> list[str]:
    return sorted(json.dumps(source, sort_keys=True) for source in _git_source_entries(lock_file))


def configure_local_git_source(
    workspace_dir: Path,
    repo: LocalGitRepo,
    *,
    rev: str | None = None,
    branch: str | None = None,
    tag: str | None = None,
    subdirectory: str = "project",
) -> None:
    manifest_path = workspace_dir / "pixi.toml"
    manifest = tomllib.loads(manifest_path.read_text())
    source = manifest.setdefault("package", {}).setdefault("build", {}).setdefault("source", {})
    for key in ("branch", "tag", "rev"):
        source.pop(key, None)
    source["git"] = "file://" + str(repo.path.as_posix())
    source["subdirectory"] = subdirectory
    if rev is not None:
        source["rev"] = rev
    if branch is not None:
        source["branch"] = branch
    if tag is not None:
        source["tag"] = tag
    manifest_path.write_text(tomli_w.dumps(manifest))


def prepare_cpp_git_workspace(
    workspace_dir: Path,
    build_data: Path,
    repo: LocalGitRepo,
    **source_kwargs: Any,
) -> None:
    project = build_data.joinpath("cpp-with-git-source")

    # Remove existing .pixi folders
    shutil.rmtree(project.joinpath(".pixi"), ignore_errors=True)

    # Copy to workspace
    shutil.copytree(project, workspace_dir, dirs_exist_ok=True)

    configure_local_git_source(workspace_dir, repo, **source_kwargs)


def test_target_specific_dependency(
    pixi: Path, build_data: Path, tmp_pixi_workspace: Path, target_specific_channel_1: str
) -> None:
    """
    Check that target-specific dependencies are not solved for on other targets.
    """
    project = "target-specific"
    test_data = build_data.joinpath(project)

    target_dir = tmp_pixi_workspace.joinpath(project)
    copytree_with_local_backend(test_data, target_dir)
    manifest_path = target_dir.joinpath("pixi.toml")

    manifest = tomllib.loads(manifest_path.read_text())
    manifest["workspace"]["channels"] += [target_specific_channel_1]
    manifest_path.write_text(tomli_w.dumps(manifest))

    verify_cli_command(
        [pixi, "build", "--manifest-path", manifest_path, "--output-dir", tmp_pixi_workspace],
    )


@pytest.mark.slow
def test_git_path_build(
    pixi: Path,
    build_data: Path,
    tmp_pixi_workspace: Path,
    local_cpp_git_repo: LocalGitRepo,
) -> None:
    """
    Test git path in `[package.build.source]` using a local repository.
    """
    prepare_cpp_git_workspace(
        tmp_pixi_workspace, build_data, local_cpp_git_repo, rev=local_cpp_git_repo.main_rev
    )

    verify_cli_command(
        [pixi, "lock", "-v", "--manifest-path", tmp_pixi_workspace],
    )

    verify_cli_command(
        [
            pixi,
            "build",
            "-v",
            "--manifest-path",
            tmp_pixi_workspace,
            "--output-dir",
            tmp_pixi_workspace,
        ],
    )

    built_packages = list(tmp_pixi_workspace.glob("*.conda"))
    assert len(built_packages) == 1


@pytest.mark.slow
def test_git_path_lock_behaviour(
    pixi: Path,
    build_data: Path,
    tmp_pixi_workspace: Path,
    local_cpp_git_repo: LocalGitRepo,
) -> None:
    """Exercise git source locking behaviour when switching manifest branches."""

    prepare_cpp_git_workspace(
        tmp_pixi_workspace, build_data, local_cpp_git_repo, rev=local_cpp_git_repo.main_rev
    )

    verify_cli_command(
        [pixi, "lock", "-v", "--manifest-path", tmp_pixi_workspace],
    )

    lock_path = tmp_pixi_workspace / "pixi.lock"
    initial_sources = extract_git_sources(lock_path)

    verify_cli_command(
        [pixi, "install", "-v", "--manifest-path", tmp_pixi_workspace, "--locked"],
    )
    assert extract_git_sources(lock_path) == initial_sources

    configure_local_git_source(tmp_pixi_workspace, local_cpp_git_repo, branch="other-feature")

    verify_cli_command(
        [pixi, "install", "-v", "--manifest-path", tmp_pixi_workspace, "--locked"],
        expected_exit_code=ExitCode.FAILURE,
    )
    assert extract_git_sources(lock_path) == initial_sources

    verify_cli_command(
        [pixi, "lock", "-v", "--manifest-path", tmp_pixi_workspace],
    )
    new_sources = extract_git_sources(lock_path)
    assert new_sources != initial_sources

    verify_cli_command(
        [pixi, "install", "-v", "--manifest-path", tmp_pixi_workspace, "--locked"],
    )
    assert extract_git_sources(lock_path) == new_sources


@pytest.mark.slow
def test_git_path_lock_update_preserves_git_source(
    pixi: Path,
    build_data: Path,
    tmp_pixi_workspace: Path,
    local_cpp_git_repo: LocalGitRepo,
) -> None:
    """Ensure updating another dependency leaves git package_build_source untouched."""

    prepare_cpp_git_workspace(
        tmp_pixi_workspace, build_data, local_cpp_git_repo, rev=local_cpp_git_repo.main_rev
    )

    lock_path = tmp_pixi_workspace / "pixi.lock"
    verify_cli_command(
        [pixi, "lock", "-v", "--manifest-path", tmp_pixi_workspace],
    )
    initial_sources = extract_git_sources(lock_path)

    verify_cli_command(
        [
            pixi,
            "update",
            "-v",
            "--manifest-path",
            tmp_pixi_workspace,
            "sdl2",
        ],
    )

    assert extract_git_sources(lock_path) == initial_sources


@pytest.mark.slow
def test_git_path_lock_branch_records_branch_metadata(
    pixi: Path,
    build_data: Path,
    tmp_pixi_workspace: Path,
    local_cpp_git_repo: LocalGitRepo,
) -> None:
    prepare_cpp_git_workspace(
        tmp_pixi_workspace, build_data, local_cpp_git_repo, branch="other-feature"
    )

    lock_path = tmp_pixi_workspace / "pixi.lock"
    verify_cli_command(
        [pixi, "lock", "-v", "--manifest-path", tmp_pixi_workspace],
    )

    entries = _git_source_entries(lock_path)
    assert {entry.get("branch") for entry in entries} == {"other-feature"}
    assert {entry.get("rev") for entry in entries} == {local_cpp_git_repo.other_feature_rev}
    assert all("tag" not in entry for entry in entries)
    assert {entry.get("subdir") for entry in entries} == {"project"}

    verify_cli_command(
        [pixi, "install", "-v", "--manifest-path", tmp_pixi_workspace, "--locked"],
    )


@pytest.mark.slow
def test_git_path_build_have_absolutely_no_respect_to_lock_file(
    pixi: Path,
    build_data: Path,
    tmp_pixi_workspace: Path,
    local_cpp_git_repo: LocalGitRepo,
) -> None:
    prepare_cpp_git_workspace(
        tmp_pixi_workspace, build_data, local_cpp_git_repo, branch="other-feature"
    )

    lock_path = tmp_pixi_workspace / "pixi.lock"
    verify_cli_command(
        [pixi, "lock", "-v", "--manifest-path", tmp_pixi_workspace],
    )

    initial_sources = extract_git_sources(lock_path)
    assert any(local_cpp_git_repo.other_feature_rev in entry for entry in initial_sources)

    repo_path = local_cpp_git_repo.path
    main_path = repo_path.joinpath("project", "src", "main.cc")
    verify_cli_command([pixi, "run", "git", "checkout", "other-feature"], cwd=repo_path)
    main_path.write_text(
        main_path.read_text(encoding="utf-8").replace(
            "Usage: sdl-example [options]", "Usage: sdl-example v2 [options]"
        ),
        encoding="utf-8",
    )
    verify_cli_command(
        [pixi, "run", "git", "add", main_path.relative_to(repo_path).as_posix()],
        cwd=repo_path,
    )
    verify_cli_command(
        [pixi, "run", "git", "commit", "-m", "Update branch for pixi build test"],
        cwd=repo_path,
    )
    new_branch_rev = verify_cli_command(
        [pixi, "run", "git", "rev-parse", "HEAD"], cwd=repo_path
    ).stdout.strip()
    assert new_branch_rev != local_cpp_git_repo.other_feature_rev

    verify_cli_command(
        [
            pixi,
            "build",
            "-v",
            "--manifest-path",
            tmp_pixi_workspace,
            "--output-dir",
            tmp_pixi_workspace,
        ],
    )

    built_packages = list(tmp_pixi_workspace.glob("*.conda"))
    assert built_packages

    # lock file should remain untouched when running `pixi build`
    assert extract_git_sources(lock_path) == initial_sources

    work_dir = tmp_pixi_workspace / ".pixi" / "build" / "work"
    assert work_dir.exists()

    target_phrase = b"Usage: sdl-example v2 [options]"
    legacy_phrase = b"Usage: sdl-example [options]"

    def iter_candidate_files() -> Iterator[Path]:
        for path in work_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix in {".o", ".bin", ".txt", ".json"} or "sdl_example" in path.name:
                yield path

    found = []
    for candidate in iter_candidate_files():
        try:
            data = candidate.read_bytes()
        except OSError:
            continue
        if target_phrase in data:
            found.append(candidate)
        assert legacy_phrase not in data, f"found legacy string in {candidate}"

    assert found, "expected build artifacts to include updated branch contents"


@pytest.mark.slow
def test_git_path_lock_tag_records_tag_metadata(
    pixi: Path,
    build_data: Path,
    tmp_pixi_workspace: Path,
    local_cpp_git_repo: LocalGitRepo,
) -> None:
    prepare_cpp_git_workspace(
        tmp_pixi_workspace, build_data, local_cpp_git_repo, tag=local_cpp_git_repo.tag
    )

    lock_path = tmp_pixi_workspace / "pixi.lock"
    verify_cli_command(
        [pixi, "lock", "-v", "--manifest-path", tmp_pixi_workspace],
    )

    entries = _git_source_entries(lock_path)
    assert {entry.get("tag") for entry in entries} == {local_cpp_git_repo.tag}
    assert {entry.get("rev") for entry in entries} == {local_cpp_git_repo.main_rev}
    assert all("branch" not in entry for entry in entries)
    assert {entry.get("subdir") for entry in entries} == {"project"}

    verify_cli_command(
        [pixi, "install", "-v", "--manifest-path", tmp_pixi_workspace, "--locked"],
    )


@pytest.mark.slow
def test_git_path_lock_rev_marks_explicit_rev(
    pixi: Path,
    build_data: Path,
    tmp_pixi_workspace: Path,
    local_cpp_git_repo: LocalGitRepo,
) -> None:
    prepare_cpp_git_workspace(
        tmp_pixi_workspace, build_data, local_cpp_git_repo, rev=local_cpp_git_repo.main_rev
    )

    lock_path = tmp_pixi_workspace / "pixi.lock"
    verify_cli_command(
        [pixi, "lock", "-v", "--manifest-path", tmp_pixi_workspace],
    )

    entries = _git_source_entries(lock_path)
    assert {entry.get("rev") for entry in entries} == {local_cpp_git_repo.main_rev}
    assert {entry.get("explicit_rev") for entry in entries} == {True}


@pytest.mark.slow
def test_git_path_lock_consistent_across_platforms(
    pixi: Path,
    build_data: Path,
    tmp_pixi_workspace: Path,
    local_cpp_git_repo: LocalGitRepo,
) -> None:
    prepare_cpp_git_workspace(
        tmp_pixi_workspace, build_data, local_cpp_git_repo, rev=local_cpp_git_repo.main_rev
    )

    lock_path = tmp_pixi_workspace / "pixi.lock"
    verify_cli_command(
        [pixi, "lock", "-v", "--manifest-path", tmp_pixi_workspace],
    )

    serialized = extract_git_sources(lock_path)
    assert len(set(serialized)) == 1


@pytest.mark.slow
def test_git_path_lock_detects_manual_rev_change(
    pixi: Path,
    build_data: Path,
    tmp_pixi_workspace: Path,
    local_cpp_git_repo: LocalGitRepo,
) -> None:
    prepare_cpp_git_workspace(
        tmp_pixi_workspace, build_data, local_cpp_git_repo, rev=local_cpp_git_repo.main_rev
    )

    lock_path = tmp_pixi_workspace / "pixi.lock"
    verify_cli_command(
        [pixi, "lock", "-v", "--manifest-path", tmp_pixi_workspace],
    )

    lock_data = yaml.safe_load(lock_path.read_text())

    def mutate(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("conda") == "." and "package_build_source" in node:
                node["package_build_source"]["rev"] = local_cpp_git_repo.other_feature_rev
            for value in node.values():
                mutate(value)
        elif isinstance(node, list):
            for item in node:
                mutate(item)

    mutate(lock_data)
    lock_path.write_text(yaml.safe_dump(lock_data))

    verify_cli_command(
        [pixi, "install", "-v", "--manifest-path", tmp_pixi_workspace, "--locked"],
        expected_exit_code=ExitCode.FAILURE,
    )
