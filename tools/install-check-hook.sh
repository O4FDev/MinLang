#!/bin/sh
set -eu
project_root=$(git rev-parse --show-toplevel)
configured=$(git config --get core.hooksPath || :)
if [ -n "$configured" ] && [ "$configured" != .githooks ]; then
    printf 'Existing core.hooksPath is %s; preserve it and invoke tools/check-commit.sh from its pre-commit hook.\n' "$configured" >&2
    exit 1
fi
hooks_dir=$(git rev-parse --git-path hooks)
if [ -z "$configured" ] && [ -e "$hooks_dir/pre-commit" ]; then
    printf 'Existing pre-commit hook at %s; preserve it and invoke tools/check-commit.sh from that hook.\n' "$hooks_dir/pre-commit" >&2
    exit 1
fi
if [ -z "$configured" ]; then
    for existing_hook in "$hooks_dir"/*; do
        case $existing_hook in *.sample) continue ;; esac
        if [ -f "$existing_hook" ] && [ -x "$existing_hook" ]; then
            printf 'Active hook at %s; preserve this hooks directory and invoke tools/check-commit.sh from its pre-commit hook.\n' "$existing_hook" >&2
            exit 1
        fi
    done
fi
test -f "$project_root/.githooks/pre-commit"
chmod +x "$project_root/.githooks/pre-commit"
git config --local core.hooksPath .githooks
printf 'Local commits now run core checks plus checks for affected modules against the staged tree.\n'
