#!/bin/sh
# sync-projects.sh DEST [HOST] -- copy the read-only upstream projects used by
# run.py to DEST (locally, or over ssh to HOST), record each commit in
# .rw-commit, and apply the adoption patches.
#
#   sh benchmarks/realworld/sync-projects.sh /home/agent/swarm/realworld agent@box
#
# SOURCES defaults to $HOME/Projects; override with RW_PROJECT_SOURCES.
set -eu

dest=${1:?usage: sync-projects.sh DEST [HOST]}
host=${2-}
sources=${RW_PROJECT_SOURCES:-$HOME/Projects}
here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
projects="neo-db minyar-query minyar-js minyar-terminal minyar-sandbox minyar-sim"

excludes='--exclude .git --exclude target --exclude build --exclude artifacts --exclude results
 --exclude reports --exclude docs --exclude node_modules --exclude data --exclude correctness
 --exclude third_party --exclude *.pdf'

if [ -n "$host" ]; then
    remote="$host:$dest"
    ssh -o BatchMode=yes "$host" "mkdir -p '$dest'"
    rsync_ssh="ssh -o BatchMode=yes"
else
    remote=$dest
    mkdir -p "$dest"
    rsync_ssh=""
fi

for project in $projects; do
    # shellcheck disable=SC2086
    rsync -a --delete $excludes ${rsync_ssh:+-e "$rsync_ssh"} "$sources/$project/" "$remote/$project/"
    commit=$(git -C "$sources/$project" rev-parse HEAD)
    printf '%s\n' "$commit" > "/tmp/rw-commit-$project"
    patch="$here/adoption/$project.patch"
    if [ -n "$host" ]; then
        scp -q -o BatchMode=yes "/tmp/rw-commit-$project" "$host:$dest/$project/.rw-commit"
        if [ -f "$patch" ]; then
            scp -q -o BatchMode=yes "$patch" "$host:/tmp/rw-$project.patch"
            ssh -o BatchMode=yes "$host" "cd '$dest/$project' && patch -p1 --forward --silent < '/tmp/rw-$project.patch'"
        fi
    else
        cp "/tmp/rw-commit-$project" "$dest/$project/.rw-commit"
        if [ -f "$patch" ]; then
            (cd "$dest/$project" && patch -p1 --forward --silent < "$patch")
        fi
    fi
    rm -f "/tmp/rw-commit-$project"
    echo "$project $commit"
done
