#!/bin/zsh
# create-cache.sh: create the one persistent shard-cache box (s-4vcpu-8gb, lon1) from the current shard image and
# serve /home/agent/fgc to the shards over the VPC (cache-provision.sh). It is tagged test-shard-cache, not
# test-shard: the guard's 2-hour rule is for shards; this box's $1.71/day is reserved inside the $10/day by
# fast_gate.py's shard budget ($8.29). Recreate it after every new image: its toolchain identity must match the
# shards' (build/.toolchain.json records the compiler's inode and ctime).
set -eu
here=${0:A:h}
key=$HOME/.ssh/brief_crawl_do
ssh=(ssh -i $key -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=5)
image=$(cut -d' ' -f1 $here/image.txt)
old=$(doctl compute droplet list --format ID,Name --no-header | awk '$2 == "shard-cache" {print $1}')
[[ -n $old ]] && { echo "deleting the old shard-cache $old"; doctl compute droplet delete -f $old; }
id=$(doctl compute droplet create shard-cache --size s-4vcpu-8gb --image $image --region lon1 --ssh-keys 59947268 \
  --tag-names test-shard-cache --wait --format ID --no-header)
ip=$(doctl compute droplet get $id --format PublicIPv4 --no-header)
until $ssh root@$ip true 2>/dev/null; do sleep 2; done
scp -q -i $key -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null $here/cache-provision.sh root@$ip:/root/
$ssh root@$ip 'bash /root/cache-provision.sh'
echo "shard-cache $id $ip (image $image)"
