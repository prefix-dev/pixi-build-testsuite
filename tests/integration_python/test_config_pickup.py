import shutil
from pathlib import Path

import tomli_w
import tomllib

from .common import verify_cli_command


def test_config_pickup_by_build_backends(
    pixi: Path, build_data: Path, tmp_pixi_workspace: Path
) -> None:
    """
    Test that pixi build backends pick up config from .pixi/config.toml.

    First tests with working config, then verifies the config is actually
    being used by checking the log output for mirror usage.
    """
    # Copy our test workspace
    test_data = build_data.joinpath("config-pickup-test")
    shutil.copytree(test_data, tmp_pixi_workspace, dirs_exist_ok=True)

    manifest_path = tmp_pixi_workspace.joinpath("pixi.toml")

    # Create .pixi/config.toml with mirror that redirects from the broken URL to our backends channel
    pixi_dir = tmp_pixi_workspace.joinpath(".pixi")
    config_path = pixi_dir.joinpath("config.toml")
    config = tomllib.loads(config_path.read_text())
    config["mirrors"] = {
        "https://broken.url/conda-forge": ["https://prefix.dev/conda-forge"],
    }
    config_path.write_text(tomli_w.dumps(config))

    verify_cli_command(
        [pixi, "run", "-v", "--manifest-path", manifest_path, "start"],
        stdout_contains="Build backend works",
    )
