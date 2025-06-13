import shutil
from pathlib import Path

import tomli_w
import tomllib

from .common import verify_cli_command


def test_build(pixi: Path, build_data: Path, tmp_pixi_workspace: Path) -> None:
    project = "multi-output"
    test_data = build_data.joinpath(project)
    test_data.joinpath("pixi.lock").unlink(missing_ok=True)
    shutil.copytree(test_data, tmp_pixi_workspace, dirs_exist_ok=True)

    env = {
        "PIXI_CACHE_DIR": str(tmp_pixi_workspace.joinpath("pixi_cache")),
    }
    verify_cli_command(
        [pixi, "build", "--manifest-path", tmp_pixi_workspace, "--output-dir", tmp_pixi_workspace],
        env=env,
    )

    # Ensure that exactly one conda package has been built
    built_packages = list(tmp_pixi_workspace.glob("*.conda"))
    assert len(built_packages) == 3


def test_install(pixi: Path, build_data: Path, tmp_pixi_workspace: Path) -> None:
    project = "multi-output"
    test_data = build_data.joinpath(project)
    test_data.joinpath("pixi.lock").unlink(missing_ok=True)
    shutil.copytree(test_data, tmp_pixi_workspace, dirs_exist_ok=True)

    package_manifest_path = tmp_pixi_workspace.joinpath("recipe", "pixi.toml")
    package_manifest = tomllib.loads(package_manifest_path.read_text())
    package_manifest["package"]["build"]["configuration"] = {"debug-dir": str(tmp_pixi_workspace)}
    package_manifest_path.write_text(tomli_w.dumps(package_manifest))

    env = {
        "PIXI_CACHE_DIR": str(tmp_pixi_workspace.joinpath("pixi_cache")),
    }
    verify_cli_command([pixi, "install", "--manifest-path", tmp_pixi_workspace], env=env)

    conda_metadata_params = tmp_pixi_workspace.joinpath("conda_metadata_params.json")
    conda_build_params = tmp_pixi_workspace.joinpath("conda_build_params.json")

    assert conda_metadata_params.is_file()
    assert conda_build_params.is_file()

    conda_metadata_params.unlink()
    conda_build_params.unlink()

    verify_cli_command(
        [pixi, "install", "--locked", "--manifest-path", tmp_pixi_workspace], env=env
    )

    assert not conda_metadata_params.is_file()
    assert not conda_build_params.is_file()
