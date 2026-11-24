#!/bin/bash
# Pack source/ into the plugin's Slackware package: build/package-plugin.sh VERSION OUTDIR (prints the package name).
# Shared by .github/workflows/package.yml and build/ttm_build.py verify so CI installs exactly what gets released.
set -eu
version=$1
out=$(realpath "$2")
[[ "$version" =~ ^[0-9]{4}\.[0-9]{2}\.[0-9]{2}(\.[0-9]+)?$ ]] || { echo "invalid version: $version" >&2; exit 1; }
pkg="dwttm-${version}-x86_64-1"
cd "$(dirname "$0")/.."
# installpkg only runs install/doinst.sh when members are named like makepkg's ("install/...", not "./install/...").
# --mode keeps the build host's umask out of the package: installpkg applies the "./" entry's mode to / itself,
# and a 0700 / locks every non-root process out of the whole filesystem.
tar -C source --owner=0 --group=0 --mode='u=rwX,go=rX' --sort=name --transform='s,^\./\(.\),\1,' -cJf "$out/${pkg}.txz" .
tar -tJf "$out/${pkg}.txz" | grep -qx 'install/doinst.sh'
# Every directory member, "./" included, is applied to a live system path, so each must be 0755.
tar -tvJf "$out/${pkg}.txz" | awk '/^d/ && $1 != "drwxr-xr-x" {bad = 1} END {exit bad}'
echo "$pkg"
