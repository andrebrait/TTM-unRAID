#!/bin/bash
# Install bubblewrap and uidmap on the runner and make sure the image-extraction tools exist.
# The Ubuntu archive mirrors are sometimes unresolvable from GitHub-hosted runners, so when apt fails
# fall back to the same pinned .deb from a kernel.org mirror.
set -euo pipefail
DEB=bubblewrap_0.9.0-1ubuntu0.3_amd64.deb
SHA256=2461f1beee9cb04c8942739fe1a2b37e7b7c2a3d518f0779dc75f9245baa3094
sudo timeout 60 apt-get update || true
sudo timeout 90 apt-get install --no-install-recommends --yes bubblewrap uidmap || true
if ! command -v bwrap >/dev/null; then
  curl --fail --location --retry 3 --output "$RUNNER_TEMP/$DEB" "https://mirrors.kernel.org/ubuntu/pool/main/b/bubblewrap/$DEB"
  echo "$SHA256  $RUNNER_TEMP/$DEB" | sha256sum --check
  sudo dpkg --install "$RUNNER_TEMP/$DEB"
fi
command -v newuidmap bwrap
for tool in cpio zstd xz unsquashfs; do
  command -v "$tool" >/dev/null || sudo apt-get install --no-install-recommends --yes cpio zstd xz-utils squashfs-tools
done
sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 root
