#!/usr/bin/env python3
"""Build the tmux and reptyr Slackware packages in a mapped-UID sandbox and verify them inside exact Unraid roots.

Adapted from andrebrait/NUT-unRAID build/nut_build.py. Reuses NerdTools' pinned bootstrap/sandbox modules (same
commit as the unraid-build-root action); set NERDTOOLS to that checkout. Requires a disposable Linux x86_64 runner
and root.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

REPO = Path(__file__).resolve().parent.parent
LOCK = json.loads((REPO / "build/ttm.json").read_text())
NERDTOOLS = Path(os.environ["NERDTOOLS"])
sys.path[:0] = [str(NERDTOOLS / "build/unraid-build-root"), str(NERDTOOLS / "build")]
from bootstrap import clone_root, fetch, prepare_image, run  # noqa: E402
from sandbox import mapped_root, run_sandbox  # noqa: E402

ENV = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
       "HOME": "/root", "LC_ALL": "C", "TZ": "UTC", "TERM": "xterm"}


def package_file(package):
    return f"{package['name']}-{package['version']}-x86_64-{package['build']}{package['tag']}.txz"


def build(args):
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for package in LOCK["packages"]:
        source = fetch(package["input"], work / "inputs")
        environment = {**ENV, "TMP": f"/tmp/{package['name']}-build", "OUTPUT": "/out", "VERSION": package["version"],
                       "BUILD": package["build"], "TAG": package["tag"]}
        with tempfile.TemporaryDirectory(prefix=f"{package['name']}-build-", dir=work) as temporary:
            temporary = Path(temporary)
            temporary.chmod(0o711)
            root = temporary / "root"
            clone_root(Path(args.development_root), root)
            recipe = root / "work/recipe"
            shutil.copytree(REPO / package["recipe"], recipe)
            shutil.copyfile(source, recipe / package["input"]["file"])
            (root / "out").mkdir()
            with mapped_root(root):
                run_sandbox(root, ["/bin/bash", package["script"]], environment, cwd="/work/recipe", timeout=3600)
            results = [path.name for path in (root / "out").glob("*.txz")]
            if results != [package_file(package)]:
                raise ValueError(f"Expected exactly {package_file(package)}, found {results}")
            shutil.copyfile(root / "out" / results[0], out / results[0])
        print(f"built {out / results[0]}")


def elf_members(archive, root):
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            path = root / member.name.lstrip("./")
            if member.isfile() and not path.is_symlink() and path.is_file():
                with path.open("rb") as stream:
                    if stream.read(4) == b"\x7fELF":
                        yield "/" + member.name.lstrip("./")


def check(root, command, read_only=True):
    """Run inside the target root; return (ok, combined output)."""
    try:
        result = run_sandbox(root, command, ENV, timeout=60, capture=True, read_only=read_only)
    except subprocess.CalledProcessError as error:
        return False, f"{error.stdout or ''}{error.stderr or ''}exit status {error.returncode}\n"
    return True, result.stdout + result.stderr


def verify(args):
    target = LOCK["targets"][args.target]
    packages = {package["name"]: package for package in LOCK["packages"]}
    archives = []
    for package in LOCK["packages"]:
        path = Path(args.package_dir).resolve() / package_file(package)
        if not path.is_file():
            raise ValueError(f"Missing package {path}")
        archives.append(path)
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ttm-verify-", dir=work) as temporary:
        temporary = Path(temporary)
        temporary.chmod(0o711)
        root = temporary / "root"
        root.mkdir()
        image = {"url": target["url"], "sha256": target["sha256"], "file": f"unRAIDServer-{args.target}-x86_64.zip"}
        prepare_image(image, args.target, temporary / "inputs", root, target["bzroot_sha256"])
        staged = root / "tmp/ttm-packages"
        staged.mkdir(parents=True)
        for archive in archives:
            shutil.copyfile(archive, staged / archive.name)
        failures = []
        with mapped_root(root):
            # Same command the plugin runs on the box, including package install scripts.
            run_sandbox(root, ["/sbin/upgradepkg", "--install-new", *(f"/tmp/ttm-packages/{a.name}" for a in archives)],
                        ENV, timeout=600)
            # ld.so resolves the transitive closure and symbol versions against the target's own libraries.
            for archive in archives:
                for path in elf_members(archive, root):
                    ok, output = check(root, ["/lib64/ld-linux-x86-64.so.2", "--list", path])
                    print(f"== {path}\n{output}", end="")
                    if not ok or "not found" in output:
                        failures.append(path)
            for package in packages.values():
                for command in package["smoke"]:
                    ok, output = check(root, command)
                    print(f"== {' '.join(command)}\n{output}", end="")
                    if not ok or package["expect"] not in output:
                        failures.append(" ".join(command))
            # Root starts a detached session and lists it, as ttmd does; the root is a disposable copy, so it is writable.
            ok, output = check(root, ["/bin/bash", "-c", LOCK["session"]["command"]], read_only=False)
            print(f"== detached tmux session\n{output}", end="")
            if not ok:
                failures.append("detached tmux session")
        if failures:
            raise ValueError(f"Unraid {args.target} verification failed: {failures}")
    print(f"Verified {', '.join(a.name for a in archives)} on Unraid {args.target}: "
          "ELF closure resolved, smoke commands and detached session passed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    # Work dirs must be traversable by the mapped sandbox UIDs; the runner's home is not.
    b = sub.add_parser("build")
    b.add_argument("--development-root", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--work", default="/tmp")
    v = sub.add_parser("verify")
    v.add_argument("--target", required=True, choices=sorted(LOCK["targets"]))
    v.add_argument("--package-dir", required=True)
    v.add_argument("--work", default="/tmp")
    args = parser.parse_args()
    if sys.platform != "linux" or os.uname().machine != "x86_64" or os.geteuid() != 0:
        raise SystemExit("Requires a disposable Linux x86_64 runner and root")
    build(args) if args.command == "build" else verify(args)


if __name__ == "__main__":
    main()
