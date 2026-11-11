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
tar -C source --owner=0 --group=0 --sort=name --transform='s,^\./\(.\),\1,' -cJf "$out/${pkg}.txz" .
tar -tJf "$out/${pkg}.txz" | grep -qx 'install/doinst.sh'
echo "$pkg"
