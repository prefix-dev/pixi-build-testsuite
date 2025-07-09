#!/usr/bin/env python3
"""
Script to update pixi.lock files in test directories.

This script:
1. Recursively searches for pixi.lock files in tests/data/pixi_build (or specified directory)
2. Runs `pixi install` in each directory containing a pixi.lock file
3. Stops execution on the first error encountered
4. Accepts optional command-line argument to specify a specific subdirectory to process
"""

import argparse
import subprocess
import sys
from pathlib import Path


class PixiInstallError(Exception):
    """Raised when pixi install fails."""
    pass


def run_command(
    cmd: list[str], cwd: Path | None = None, capture_output: bool = True
) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, and stderr."""
    result = subprocess.run(cmd, cwd=cwd, capture_output=capture_output, text=True)
    return result.returncode, result.stdout, result.stderr


def pixi_install(directory: Path) -> None:
    """Run pixi install in the specified directory."""
    print(f"🔄 Running pixi install in {directory}")
    returncode, stdout, stderr = run_command(["pixi", "install"], cwd=directory)
    
    if returncode == 0:
        print(f"✅ Successfully updated lockfile in {directory}")
        if stdout.strip():
            print(f"   {stdout.strip()}")
    else:
        error_msg = f"Failed to run pixi install in {directory}"
        if stderr:
            error_msg += f": {stderr}"
        if stdout:
            error_msg += f" (Output: {stdout})"
        raise PixiInstallError(error_msg)


def find_and_process_lockfiles(base_path: Path) -> None:
    """Recursively find directories with pixi.lock files and run pixi install."""
    if not base_path.exists():
        print(f"❌ Directory {base_path} does not exist")
        sys.exit(1)
    
    if not base_path.is_dir():
        print(f"❌ Path {base_path} is not a directory")
        sys.exit(1)
    
    print(f"🔍 Searching for pixi.lock files in {base_path}")
    
    # Find all pixi.lock files recursively
    lockfiles = list(base_path.rglob("pixi.lock"))
    
    if not lockfiles:
        print(f"⚠️  No pixi.lock files found in {base_path}")
        return
    
    print(f"📋 Found {len(lockfiles)} pixi.lock file(s)")
    
    # Process each directory containing a pixi.lock file
    for lockfile in lockfiles:
        directory = lockfile.parent
        print(f"\n{'=' * 60}")
        print(f"Processing: {directory}")
        print(f"{'=' * 60}")
        
        try:
            pixi_install(directory)
        except PixiInstallError as e:
            print(f"❌ {e}")
            sys.exit(1)


def main() -> None:
    """Main function to process lockfiles."""
    parser = argparse.ArgumentParser(
        description="Update pixi.lock files by running pixi install",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Process all directories in tests/data/pixi_build
  %(prog)s rich_example       # Process only the rich_example subdirectory
  %(prog)s maturin            # Process only the maturin subdirectory
        """
    )
    parser.add_argument(
        "folder",
        nargs="?",
        help="Specific folder to process (relative to tests/data/pixi_build). If not specified, processes all directories."
    )
    
    args = parser.parse_args()
    
    # Determine base path
    script_dir = Path(__file__).parent
    base_data_dir = script_dir.parent / "tests" / "data" / "pixi_build"
    
    if args.folder:
        target_path = base_data_dir / args.folder
        print(f"🎯 Target directory: {target_path}")
    else:
        target_path = base_data_dir
        print(f"🎯 Target directory: {target_path} (all subdirectories)")
    
    try:
        find_and_process_lockfiles(target_path)
        print(f"\n{'=' * 60}")
        print("🎉 All lockfiles processed successfully!")
    except KeyboardInterrupt:
        print(f"\n❌ Operation cancelled by user")
        sys.exit(1)


if __name__ == "__main__":
    main()