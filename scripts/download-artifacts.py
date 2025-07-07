import argparse
import os
import platform
import sys
import tempfile
import zipfile
from pathlib import Path

import httpx
from dotenv import load_dotenv
from github import Github
from github.Artifact import Artifact
from rich.console import Console
from rich.progress import track

console = Console()


def get_current_platform() -> str:
    """Get the current platform string for pixi artifact naming."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "linux":
        if machine in ["x86_64", "amd64"]:
            return "linux-x86_64"
        elif machine in ["aarch64", "arm64"]:
            return "linux-aarch64"
    elif system == "darwin":
        if machine in ["arm64", "aarch64"]:
            return "macos-aarch64"
        elif machine in ["x86_64", "amd64"]:
            return "macos-x86_64"
    elif system == "windows":
        if machine in ["x86_64", "amd64"]:
            return "windows-x86_64"

    raise ValueError(f"Unsupported platform: {system}-{machine}")


def download_and_extract_artifact(
    target_artifact: Artifact, github_token: str | None, output_dir: Path, repo: str
) -> None:
    """Download and extract artifact, return path to extracted binary."""
    # Download the artifact
    console.print("[blue]Downloading artifact...")
    download_url = target_artifact.archive_download_url

    # Use httpx to download with authentication and follow redirects
    headers = {}
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    with httpx.stream(
        "GET", download_url, headers=headers, follow_redirects=True, timeout=30.0
    ) as response:
        response.raise_for_status()

        # Save to temporary file and extract
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temp_file:
            total_size = int(response.headers.get("content-length", 0))

            if total_size > 0:
                for chunk in track(
                    response.iter_bytes(chunk_size=8192),
                    total=total_size // 8192,
                    description="Downloading...",
                ):
                    temp_file.write(chunk)
            else:
                for chunk in response.iter_bytes(chunk_size=8192):
                    temp_file.write(chunk)

            temp_zip_path = temp_file.name

    console.print("[blue]Extracting artifact...")

    # Extract the zip file
    with zipfile.ZipFile(temp_zip_path, "r") as zip_ref:
        # List contents
        file_list = zip_ref.namelist()
        console.print(f"[blue]Archive contents: {file_list}")

        if repo == "prefix-dev/pixi":
            # Find the pixi binary
            pixi_binary = None
            for file_name in file_list:
                if (
                    file_name == "pixi"
                    or file_name.endswith("/pixi")
                    or file_name.endswith("pixi.exe")
                ):
                    pixi_binary = file_name
                    break

            if not pixi_binary:
                console.print("[red]Could not find pixi binary in archive")
                raise FileNotFoundError(
                    f"Could not find pixi binary in archive. Archive contents: {file_list}"
                )

            # Extract the binary
            zip_ref.extract(pixi_binary, output_dir)

            # Move to correct location if it was in a subdirectory
            extracted_path = output_dir / pixi_binary
            final_path = output_dir / Path(pixi_binary).name

            if extracted_path != final_path:
                extracted_path.rename(final_path)

            # Make executable on Unix systems
            if not sys.platform.startswith("win"):
                final_path.chmod(0o755)

            console.print(f"[green]Successfully downloaded pixi binary to: {final_path}")

        elif repo == "prefix-dev/pixi-build-backends":
            # Extract all pixi-build-* executables
            backend_executables = []
            is_windows = sys.platform.startswith("win")

            for file_name in file_list:
                base_name = Path(file_name).name
                if base_name.startswith("pixi-build-"):
                    # On Windows, expect .exe extension; on others, no extension
                    if is_windows and base_name.endswith(".exe"):
                        backend_executables.append(file_name)
                    elif not is_windows and not base_name.endswith(".exe") and "." not in base_name:
                        backend_executables.append(file_name)

            if not backend_executables:
                console.print("[red]Could not find any pixi-build-* executables in archive")
                raise FileNotFoundError(
                    f"Could not find any pixi-build-* executables in archive. Archive contents: {file_list}"
                )

            console.print(f"[blue]Found {len(backend_executables)} backend executable(s)")

            # Extract all executables
            for executable in backend_executables:
                zip_ref.extract(executable, output_dir)
                extracted_path = output_dir / executable
                final_path = output_dir / Path(executable).name

                if extracted_path != final_path:
                    extracted_path.rename(final_path)

                # Make executable on Unix systems
                if not sys.platform.startswith("win"):
                    final_path.chmod(0o755)

                console.print(f"[green]Extracted executable: {final_path}")

        else:
            raise ValueError(f"Unsupported repository: {repo}")

    # Clean up temporary file
    os.unlink(temp_zip_path)


def download_github_artifact(
    github_token: str | None,
    output_dir: Path,
    repo: str,
    workflow: str,
    run_id: int | None = None,
) -> None:
    # Get current platform
    if repo == "prefix-dev/pixi":
        current_platform = get_current_platform()
        console.print(f"[blue]Detected platform: {current_platform}")
    elif repo == "prefix-dev/pixi-build-backends":
        current_platform = get_current_platform()
        console.print(f"[blue]Detected platform: {current_platform}")
    else:
        raise ValueError(f"Unsupported repository: {repo}")

    # Initialize GitHub client
    gh = Github(github_token)

    # Get the repository
    repository = gh.get_repo(repo)
    console.print(f"[green]Connected to repository: {repository.full_name}")

    # Get the workflow run
    if run_id:
        # Use specific run ID - no need to find workflow first
        console.print(f"[blue]Using specified run ID: {run_id}")
        selected_run = repository.get_workflow_run(run_id)

    else:
        # Get the latest workflow run for the specified workflow
        workflows = repository.get_workflows()
        target_workflow = None
        for wf in workflows:
            if wf.name == workflow:
                target_workflow = wf
                break

        if not target_workflow:
            console.print(f"[red]Could not find workflow: {workflow}")
            raise ValueError(f"Could not find workflow: {workflow}")

        console.print(f"[blue]Found workflow: {target_workflow.name}")

        # Get latest workflow run from main branch
        console.print("[blue]Finding latest workflow run from main branch")
        runs = target_workflow.get_runs(branch="main")
        selected_run = runs[0]

    assert selected_run is not None
    console.print(f"[blue]Selected run: {selected_run.id} from {selected_run.created_at}")

    # Get artifacts for this run
    artifacts = selected_run.get_artifacts()

    # Find the artifact for our platform
    target_artifact = None
    if repo == "prefix-dev/pixi":
        artifact_name_pattern = f"pixi-{current_platform}"
    elif repo == "prefix-dev/pixi-build-backends":
        artifact_name_pattern = f"pixi-build-backends-{current_platform}"
    else:
        raise ValueError(f"Unsupported repository: {repo}")

    for artifact in artifacts:
        if artifact_name_pattern in artifact.name:
            target_artifact = artifact
            break

    if not target_artifact:
        console.print(f"[red]Could not find artifact matching pattern '{artifact_name_pattern}'")
        console.print("[yellow]Available artifacts:")
        available_artifacts = [artifact.name for artifact in artifacts]
        for artifact in artifacts:
            console.print(f"  - {artifact.name}")
        raise FileNotFoundError(
            f"Could not find artifact matching pattern '{artifact_name_pattern}'. "
            f"Available artifacts: {available_artifacts}"
        )

    console.print(f"[green]Found artifact: {target_artifact.name}")

    # Set up output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[blue]Output directory: {output_dir}")

    # Download and extract the artifact
    download_and_extract_artifact(target_artifact, github_token, output_dir, repo)


def main() -> None:
    # Load environment variables from .env file
    load_dotenv()

    parser = argparse.ArgumentParser(description="Download artifacts from GitHub Actions")
    parser.add_argument(
        "--token",
        help="GitHub token for authentication (can also use GITHUB_TOKEN env var or .env file)",
    )
    parser.add_argument(
        "--run-id",
        type=int,
        help="Specific workflow run ID to download from (optional)",
    )
    parser.add_argument(
        "repo",
        choices=["pixi", "pixi-build-backends"],
        help="Repository to download from: 'pixi' for pixi binaries or 'pixi-build-backends' for build backend executables",
    )

    args = parser.parse_args()

    # Set repo and workflow based on repository choice
    if args.repo == "pixi":
        repo = "prefix-dev/pixi"
        workflow = "CI"
    elif args.repo == "pixi-build-backends":
        repo = "prefix-dev/pixi-build-backends"
        workflow = "Testsuite"

    # Hardcode output directory to "artifacts"
    output_dir = Path("artifacts")

    # Get GitHub token from argument or environment
    github_token = args.token or os.getenv("GITHUB_TOKEN")
    if not github_token:
        console.print("[red][ERROR] No GitHub token provided")
        console.print(
            "[red]  Set GITHUB_TOKEN environment variable, use --token argument, or create a .env file"
        )
        sys.exit()

    try:
        download_github_artifact(github_token, output_dir, repo, workflow, args.run_id)
        console.print("[green][SUCCESS] Download completed successfully!")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red][ERROR] Download failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
