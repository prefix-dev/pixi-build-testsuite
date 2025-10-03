#!/usr/bin/env python3
"""
Script to manage and build git repositories for PIXI_REPO and BUILD_BACKENDS_REPO.

This script:
1. Loads environment variables from .env file
2. Verifies that PIXI_REPO and BUILD_BACKENDS_REPO point to git repositories
3. Checks if repositories are on main branch and pulls latest changes
4. Runs `pixi run build-release` on each repository
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv


class GitRepositoryError(Exception):
    """Raised when a path is not a valid git repository."""

    pass


class GitPullError(Exception):
    """Raised when git pull fails."""

    pass


class PixiBuildError(Exception):
    """Raised when pixi build fails."""

    pass


def run_command(
    cmd: list[str],
    cwd: Path | None = None,
    capture_output: bool = True,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, and stderr."""
    result = subprocess.run(cmd, cwd=cwd, capture_output=capture_output, text=True, env=env)
    return result.returncode, result.stdout, result.stderr


def executable_name(base: str) -> str:
    """Return the platform specific executable name."""
    return f"{base}.exe" if sys.platform.startswith("win") else base


def is_git_worktree(path: Path) -> bool:
    """Check if the given path is inside a git work tree (repo or worktree)."""
    if not path.exists() or not path.is_dir():
        return False

    returncode, stdout, _ = run_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=path)
    return returncode == 0 and stdout.strip().lower() == "true"


def get_current_branch(repo_path: Path) -> str | None:
    """Get the current branch name of the git repository."""
    returncode, stdout, stderr = run_command(["git", "branch", "--show-current"], cwd=repo_path)
    if returncode == 0:
        return stdout.strip()
    return None


def git_pull(repo_path: Path) -> None:
    """Pull latest changes from the remote repository."""
    print(f"📥 Pulling latest changes in {repo_path}")
    returncode, stdout, stderr = run_command(["git", "pull"], cwd=repo_path)

    if returncode == 0:
        print("✅ Successfully pulled changes")
        if stdout.strip():
            print(f"   {stdout.strip()}")
    else:
        raise GitPullError(f"Failed to pull changes: {stderr}")


def build_executables(repo_path: Path) -> None:
    """Run pixi run build-release in the repository."""
    print(f"🔨 Building release in {repo_path}")
    returncode, stdout, stderr = run_command(["pixi", "run", "build-release"], cwd=repo_path)

    if returncode == 0:
        print("✅ Successfully built release")
    else:
        error_msg = "Failed to build release"
        if stderr:
            error_msg += f": {stderr}"
        if stdout:
            error_msg += f" (Output: {stdout})"
        raise PixiBuildError(error_msg)


def build_ros_backend(repo_path: Path) -> None:
    """Build the pixi-build-ros backend located in backends/pixi-build-ros."""
    ros_backend_dir = repo_path / "backends" / "pixi-build-ros"
    if not ros_backend_dir.is_dir():
        print("⚠️ pixi-build-ros backend directory not found, skipping")
        return

    print(f"🔨 Building pixi-build-ros backend in {ros_backend_dir}")
    returncode, stdout, stderr = run_command(
        [
            "pixi",
            "install",
            "--manifest-path",
            str(ros_backend_dir.joinpath("pixi.toml")),
        ],
        cwd=ros_backend_dir,
    )

    if returncode != 0:
        error_msg = "Failed to build pixi-build-ros backend"
        if stderr:
            error_msg += f": {stderr}"
        if stdout:
            error_msg += f" (Output: {stdout})"
        raise PixiBuildError(error_msg)

    ros_executable = executable_name("pixi-build-ros")
    source_binary = ros_backend_dir.joinpath(".pixi", "envs", "default", "bin", ros_executable)

    if not source_binary.exists():
        raise PixiBuildError(
            f"pixi-build-ros binary not found at '{source_binary}'."
            " Ensure pixi install completed successfully."
        )

    target_dir = repo_path / "target" / "pixi" / "release"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_binary = target_dir / ros_executable

    if target_binary.exists():
        target_binary.unlink()

    shutil.copy2(source_binary, target_binary)
    print("✅ Successfully built pixi-build-ros backend")


def process_repository(repo_path: Path, repo_name: str) -> None:
    """Process a single repository: verify, pull if on main, and build."""
    print(f"\n{'=' * 60}")
    print(f"Processing {repo_name}: {repo_path}")
    print(f"{'=' * 60}")

    if not is_git_worktree(repo_path):
        raise GitRepositoryError(f"{repo_path} is not a valid git worktree")

    print("✅ Verified git worktree")

    # Check current branch
    if current_branch := get_current_branch(repo_path):
        print(f"📋 Current branch: {current_branch}")

        # Pull if on main/master branch
        if current_branch == "main":
            git_pull(repo_path)
        else:
            print("⚠️  Not on main/master branch, skipping git pull")
    else:
        print("⚠️  Could not determine current branch")

    # Run pixi build
    build_executables(repo_path)


def main() -> None:
    """Main function to process repositories."""
    # Load environment variables from .env file
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=True)
        print(f"✅ Loaded environment variables from {env_file}")
    else:
        print(f"⚠️  No .env file found at {env_file}")

    # Get repository paths from environment variables
    pixi_repo = os.getenv("PIXI_REPO")
    build_backends_repo = os.getenv("BUILD_BACKENDS_REPO")

    if not pixi_repo:
        print("❌ PIXI_REPO environment variable not set")
        sys.exit(1)

    if not build_backends_repo:
        print("❌ BUILD_BACKENDS_REPO environment variable not set")
        sys.exit(1)

    pixi_repo_path = Path(pixi_repo)
    build_backends_repo_path = Path(build_backends_repo)

    print("🎯 Target repositories:")
    print(f"   PIXI_REPO: {pixi_repo_path}")
    print(f"   BUILD_BACKENDS_REPO: {build_backends_repo_path}")

    # Process both repositories
    success = True

    try:
        process_repository(pixi_repo_path, "PIXI_REPO")
    except Exception as e:
        print(f"❌ Error processing PIXI_REPO: {e}")
        success = False

    try:
        process_repository(build_backends_repo_path, "BUILD_BACKENDS_REPO")
        build_ros_backend(build_backends_repo_path)
    except Exception as e:
        print(f"❌ Error processing BUILD_BACKENDS_REPO: {e}")
        success = False

    print(f"\n{'=' * 60}")
    if success:
        print("🎉 All repositories processed successfully!")
    else:
        print("❌ Some repositories failed to process")
        sys.exit(1)


if __name__ == "__main__":
    main()
