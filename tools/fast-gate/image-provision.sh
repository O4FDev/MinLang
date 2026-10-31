#!/bin/bash
# image-provision.sh: run as root on a fresh Ubuntu 24.04 droplet to make the shard snapshot image.
# It installs exactly what the single-box gate boxes have (the goal loop's provision-swarm.sh: the same apt packages,
# LLVM 23.1.3 checksum-pinned, Rust stable, the profile.d toolchain file) plus their FileCheck (uploaded next to this
# script as FileCheck, sha256 below), an `agent` user, and no apt timers, so a shard boots ready to run checks.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
here=$(cd "$(dirname "$0")" && pwd)
systemctl stop unattended-upgrades apt-daily.timer apt-daily-upgrade.timer 2>/dev/null || true
apt-get -o DPkg::Lock::Timeout=900 update -q
apt-get -o DPkg::Lock::Timeout=900 install -y -q build-essential make zsh curl ca-certificates zstd libxml2 libtinfo6 \
  valgrind rsync git cmake ninja-build python3-venv golang-go redis-server linux-tools-common "linux-tools-$(uname -r)" \
  time jq hyperfine libicu-dev pkg-config
systemctl disable --now redis-server 2>/dev/null || true
v=23.1.3; d=14d2f701eb68fb799001bdea6231048f3990690fa2f406d563555ff8f744daba
if [[ ! -x /opt/llvm-$v/bin/clang ]]; then
  t=$(mktemp -d /opt/.llvm.XXXX)
  curl -fL --retry 3 "https://github.com/llvm/llvm-project/releases/download/llvmorg-$v/LLVM-$v-Linux-X64.tar.zst" -o "$t/a.tar.zst"
  echo "$d  $t/a.tar.zst" | sha256sum --check
  mkdir "$t/x"; tar --use-compress-program='zstd --long=30' -xf "$t/a.tar.zst" -C "$t/x" --strip-components=1
  mv -T "$t/x" /opt/llvm-$v; rm -rf "$t"
fi
/opt/llvm-$v/bin/clang --version | head -1
if [[ ! -x /opt/rust/cargo/bin/rustc ]]; then
  export RUSTUP_HOME=/opt/rust/rustup CARGO_HOME=/opt/rust/cargo
  curl -fsSL https://sh.rustup.rs | sh -s -- -y --no-modify-path --profile minimal --default-toolchain stable
  chmod -R a+rX /opt/rust
fi
cat > /etc/profile.d/goal-toolchains.sh <<'P'
export RUSTUP_HOME=/opt/rust/rustup CARGO_HOME_SYSTEM=/opt/rust/cargo
export PATH="/opt/llvm-23.1.3/bin:/opt/rust/cargo/bin:$PATH"
P
echo 'kernel.perf_event_paranoid=1' > /etc/sysctl.d/90-perf.conf
sysctl -q kernel.perf_event_paranoid=1
apt-get -o DPkg::Lock::Timeout=900 install -y -q libssl-dev liblz4-dev libzstd-dev zlib1g-dev strace
echo "fefc3fd7753e63ee9329e93eb2ef4e79aaa9c7545e9c5ebf0606cf2e4909d2e0  $here/FileCheck" | sha256sum --check
install -m 755 "$here/FileCheck" /opt/llvm-$v/bin/FileCheck
# The fast gate's compile cache (tools/fast-gate/fgcc) stands in for the clang driver; with no
# /home/agent/fgcc/config it only execs clang-23. It is part of the image so every box made from it
# has the same toolchain identity (build/.toolchain.json records the compiler's inode and ctime).
if [[ -f $here/fgcc ]]; then
  [[ -L /opt/llvm-$v/bin/clang && $(readlink /opt/llvm-$v/bin/clang) == clang-23 ]] && rm /opt/llvm-$v/bin/clang
  install -m 755 "$here/fgcc" /opt/llvm-$v/bin/clang
  /opt/llvm-$v/bin/clang --version | head -1
fi
id agent >/dev/null 2>&1 || useradd -m -s /bin/bash agent
getent group kvm >/dev/null && usermod -aG kvm agent
install -d -m 700 -o agent -g agent /home/agent/.ssh
install -m 600 -o agent -g agent /root/.ssh/authorized_keys /home/agent/.ssh/authorized_keys
touch /home/agent/bench.lock /home/agent/gate.lock; chown agent:agent /home/agent/bench.lock /home/agent/gate.lock; chmod 666 /home/agent/bench.lock
install -d -o agent -g agent /home/agent/swarm
# A shard lives for one gate: no background apt work competing with checks, and sshd ready as soon as it boots.
systemctl disable --now apt-daily.timer apt-daily-upgrade.timer unattended-upgrades motd-news.timer 2>/dev/null || true
apt-get -y -q purge snapd 2>/dev/null || true
apt-get clean
echo IMAGE-PROVISION-OK
