import os
import shutil
import subprocess
from pathlib import Path

from ok.constants import OK_STATE_BASE_DIR


def run_command(command: list[str], cwd: Path | None = None, env=None):
    print(f"Running command: {' '.join(command)}")
    try:
        result = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, check=True, env={**os.environ, **(env or {})}
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}")
        print(e.stderr)
        raise RuntimeError(f"Command {' '.join(command)} failed with exit code {e.returncode}") from e


def main():
    opencode_repo_dir = OK_STATE_BASE_DIR / "opencode"
    opencode_bin_dir = OK_STATE_BASE_DIR / "bin"

    bun_bin = shutil.which("bun")
    go_bin = shutil.which("go")

    if not bun_bin:
        print("Error: bun not found in PATH.")
        exit(1)
    if not go_bin:
        print("Error: go not found in PATH.")
        exit(1)

    COMMIT = "a60697ce1fd0d1e0f2c4f930a456b8fe73ccbeda"
    version = "custom"

    os.makedirs(OK_STATE_BASE_DIR, exist_ok=True)
    os.chdir(OK_STATE_BASE_DIR)

    if opencode_repo_dir.exists():
        shutil.rmtree(opencode_repo_dir)

    run_command(
        [
            "git",
            "-c",
            "advice.detachedHead=false",
            "clone",
            "--quiet",
            "https://github.com/sst/opencode.git",
            "--depth",
            "1",
            "--revision",
            COMMIT,
        ]
    )

    tui_dir = opencode_repo_dir / "packages" / "tui"
    opencode_package_dir = opencode_repo_dir / "packages" / "opencode"

    # Build tui
    (tui_dir / "dist" / "bin").mkdir(parents=True, exist_ok=True)
    run_command(
        [
            go_bin,
            "build",
            "-ldflags=-s -w -X main.Version={}".format(version),
            "-o",
            str(opencode_package_dir / "dist" / "bin" / "tui"),
            str(tui_dir / "cmd" / "opencode" / "main.go"),
        ],
        cwd=tui_dir,
        env={"CGO_ENABLED": "0"},
    )

    # Build opencode
    run_command([bun_bin, "install"], cwd=opencode_package_dir)
    run_command(
        [
            bun_bin,
            "build",
            "--define",
            "OPENCODE_VERSION='{}'".format(version),
            "--compile",
            "--minify",
            "--outfile={}".format(opencode_package_dir / "dist" / "bin" / "opencode"),
            str(opencode_package_dir / "src" / "index.ts"),
            str(opencode_package_dir / "dist" / "bin" / "tui"),
        ],
        cwd=opencode_package_dir,
    )

    tui_binary_in_opencode_dist = opencode_package_dir / "dist" / "bin" / "tui"
    if tui_binary_in_opencode_dist.exists():
        tui_binary_in_opencode_dist.unlink()

    # Copy to ~/.agent/bin
    opencode_bin_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(opencode_package_dir / "dist" / "bin" / "opencode", opencode_bin_dir)
    (opencode_bin_dir / "opencode").chmod(0o755)

    # Clean up
    if os.path.exists(opencode_repo_dir):  # This was opencode- in the original, assuming it's a typo
        shutil.rmtree(opencode_repo_dir)

    print(f"Opencode built and installed to {opencode_bin_dir}")


if __name__ == "__main__":
    main()
