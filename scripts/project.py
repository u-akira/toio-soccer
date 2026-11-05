"""Cross-platform project tasks for upload preparation and tests."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
UTF8_BOM = b"\xef\xbb\xbf"


def _run(command, *, env=None):
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def _copy_python_without_bom(source, destination):
    contents = source.read_bytes()
    if contents.startswith(UTF8_BOM):
        contents = contents[len(UTF8_BOM):]

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(contents)
    if destination.read_bytes().startswith(UTF8_BOM):
        raise RuntimeError("UTF-8 BOM remains in upload file: " + str(destination))


def prepare_upload():
    upload_root = ROOT / "upload"
    debug_root = upload_root / "debug"
    debug_lib = debug_root / "lib"
    release_root = upload_root / "release"

    for stale_path in (upload_root / "code.py", upload_root / "lib"):
        if stale_path.is_dir() and not stale_path.is_symlink():
            shutil.rmtree(stale_path)
        elif stale_path.exists() or stale_path.is_symlink():
            stale_path.unlink()

    debug_lib.mkdir(parents=True, exist_ok=True)
    release_root.mkdir(parents=True, exist_ok=True)

    _copy_python_without_bom(ROOT / "code.py", debug_root / "code.py")
    for source in sorted((ROOT / "lib").glob("*.py")):
        _copy_python_without_bom(source, debug_lib / source.name)

    release_code = release_root / "code.py"
    _run([
        sys.executable,
        str(ROOT / "tools" / "build_release.py"),
        "--output",
        str(release_code),
    ])
    if release_code.read_bytes().startswith(UTF8_BOM):
        raise RuntimeError("UTF-8 BOM remains in upload file: " + str(release_code))

    print("Upload files prepared from current sources:")
    for path in sorted(upload_root.rglob("*")):
        if path.is_file():
            print(path)


def run_tests():
    prepare_upload()
    test_command = [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-v",
    ]

    for target in ("debug", "release"):
        print("Running tests against " + target + " sources...", flush=True)
        env = os.environ.copy()
        env["UV_CACHE_DIR"] = str(ROOT / ".uv-cache")
        env["TOIO_TEST_TARGET"] = target
        _run(test_command, env=env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare-upload", help="generate debug and release upload files")
    commands.add_parser("test", help="prepare uploads and test debug and release sources")
    arguments = parser.parse_args()

    if sys.version_info[:2] != (3, 13):
        parser.error(
            "Python 3.13 is required; run with: "
            "uv --cache-dir .uv-cache run --python 3.13 python scripts/project.py "
            + arguments.command
        )

    if arguments.command == "prepare-upload":
        prepare_upload()
    else:
        run_tests()


if __name__ == "__main__":
    main()
