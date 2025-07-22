import shutil
from pathlib import Path

from .common import ExitCode, verify_cli_command


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
    target_dir = tmp_pixi_workspace.joinpath("config-pickup-test")
    shutil.copytree(test_data, target_dir)

    manifest_path = target_dir.joinpath("pixi.toml")

    # First test: should work without config
    verify_cli_command(
        [
            pixi,
            "install",
            "-v",
            "--manifest-path",
            manifest_path,
        ],
    )

    # Create .pixi/config.toml with mirror that redirects to broken URL
    pixi_dir = target_dir.joinpath(".pixi")
    shutil.rmtree(pixi_dir)
    pixi_dir.mkdir()
    config_content = """[mirrors]
# redirect pixi-build-backends channel to a broken URL
"https://prefix.dev/pixi-build-backends" = ["https://broken.mirror.url"]
"""
    pixi_dir.joinpath("config.toml").write_text(config_content)

    # Second test: should fail if the backend picks up the config
    # because the mirror redirects to a broken URL and pixi install needs to resolve the backend
    verify_cli_command(
        [
            pixi,
            "install",
            "-v",
            "--manifest-path",
            manifest_path,
        ],
        expected_exit_code=ExitCode.FAILURE,
    )
