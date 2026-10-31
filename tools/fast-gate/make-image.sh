#!/bin/zsh
# make-image.sh BASE-TREE [FILECHECK]: build a new shard snapshot image and record it in tools/fast-gate/image.txt.
# Creates a small builder droplet (shard-image-*, tagged test-shard, so the guard reaps it if this script dies),
# provisions it with image-provision.sh (+ FileCheck and fgcc), copies BASE-TREE's files to /home/agent/base as the
# delta basis for gate syncs, snapshots it and deletes the builder. Old shard-image-* snapshots are listed for
# deletion (keep one current).
set -eu
here=${0:A:h}
base=${1:?usage: make-image.sh BASE-TREE [FILECHECK]}
filecheck=${2:-$HOME/Projects/minyar-fast-tests/toolchain/FileCheck}
key=$HOME/.ssh/brief_crawl_do
ssh=(ssh -i $key -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=5)
name=shard-image-$(date -u +%Y%m%d%H%M)
id=$(doctl compute droplet create $name --size s-2vcpu-4gb-amd --image ubuntu-24-04-x64 --region lon1 --ssh-keys 59947268 \
  --tag-names test-shard --wait --format ID --no-header)
trap 'doctl compute droplet delete -f $id >/dev/null 2>&1 || true' EXIT
ip=$(doctl compute droplet get $id --format PublicIPv4 --no-header)
until $ssh root@$ip true 2>/dev/null; do sleep 2; done
scp -q -i $key -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null $here/image-provision.sh $filecheck root@$ip:/root/
scp -q -i $key -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null $here/fgcc/fgcc.c root@$ip:/root/fgcc.c
$ssh root@$ip 'bash /root/image-provision.sh > /root/provision.log 2>&1; tail -3 /root/provision.log' | tee /tmp/$name.log
grep -q IMAGE-PROVISION-OK /tmp/$name.log
$ssh agent@$ip 'mkdir -p /home/agent/base'
commit=$(git -C $base rev-parse --short HEAD)
(cd $base && git ls-files -z | rsync -a --from0 --files-from=- -e "${ssh[*]}" ./ agent@$ip:/home/agent/base/)
$ssh root@$ip 'cloud-init clean --logs >/dev/null 2>&1; rm -f /root/fgcc /root/fgcc.c /root/FileCheck; sync'
doctl compute droplet-action power-off $id --wait >/dev/null
doctl compute droplet-action snapshot $id --snapshot-name $name --wait >/dev/null
image=$(doctl compute image list-user --format ID,Name --no-header | awk -v n=$name '$2 == n {print $1}')
echo "$image $name (Ubuntu 24.04, LLVM 23.1.3 + FileCheck, fgcc at /opt/fgcc, Rust, base tree $commit)" > $here/image.txt
echo "image $image ($name), base $commit; recorded in $here/image.txt"
echo "older shard images (delete with doctl compute image delete ID):"
doctl compute image list-user --format ID,Name --no-header | awk -v n=$name '$2 ~ /^shard-image-/ && $2 != n'
