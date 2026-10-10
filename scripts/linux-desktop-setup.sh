#!/usr/bin/env bash
# Prepare the Fedora development guest, not the macOS host.
set -euo pipefail

if [[ "$(uname -s)" != Linux ]]; then
    echo 'Run this script inside the Fedora Linux development guest.' >&2
    exit 1
fi
source /etc/os-release
if [[ "$ID" != fedora || "$VERSION_ID" != 44 ]]; then
    echo 'This dependency recipe is for Fedora 44.' >&2
    exit 1
fi

sudo dnf install -y clang lld gcc gcc-c++ cmake ninja-build make git zsh \
    python3 python3-devel python3-pyyaml rsync pkgconf-pkg-config \
    gtk4-devel libadwaita-devel gobject-introspection-devel \
    libicu-devel libcurl-devel libxml2-devel libuuid-devel libedit-devel \
    ncurses-devel sqlite-devel zlib-devel openssl-devel libstdc++-devel \
    libatomic libasan file tar unzip patch

# Bootstrap the pinned 6.2 compiler with the Fedora release's 6.2 package.
# The Minyar build produces its own matching target runtime and modules.
sudo dnf install -y --repo=fedora swift-lang-6.2-8.fc44

clang --version
swiftc --version
pkg-config --modversion gtk4 libadwaita-1
df -h .
