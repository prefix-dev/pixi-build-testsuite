import shutil
from pathlib import Path

from .common import ExitCode, verify_cli_command


def test_log_working_default(pixi: Path, build_data: Path, tmp_pixi_workspace: Path) -> None:
    test_data = build_data.joinpath("log-example", "working")

    shutil.copytree(test_data, tmp_pixi_workspace, dirs_exist_ok=True)

    verify_cli_command(
        [
            pixi,
            "install",
            "--manifest-path",
            tmp_pixi_workspace,
        ],
        stderr_excludes="Building package simple-app",
    )


def test_log_working_verbose(pixi: Path, build_data: Path, tmp_pixi_workspace: Path) -> None:
    test_data = build_data.joinpath("log-example", "working")

    shutil.copytree(test_data, tmp_pixi_workspace, dirs_exist_ok=True)

    verify_cli_command(
        [
            pixi,
            "install",
            "--verbose",
            "--manifest-path",
            tmp_pixi_workspace,
        ],
        stderr_contains="Building package simple-app",
    )


def test_log_failing(pixi: Path, build_data: Path, tmp_pixi_workspace: Path) -> None:
    test_data = build_data.joinpath("log-example", "failing")

    shutil.copytree(test_data, tmp_pixi_workspace, dirs_exist_ok=True)

    verify_cli_command(
        [
            pixi,
            "install",
            "--manifest-path",
            tmp_pixi_workspace,
        ],
        ExitCode.FAILURE,
        stderr_contains="Building package simple-app",
    )
