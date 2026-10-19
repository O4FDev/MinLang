#!/bin/sh
set -eu

plan=0
case ${1-} in
    '') ;;
    --plan) plan=1; shift ;;
    *) printf 'usage: check-commit.sh [--plan]\n' >&2; exit 2 ;;
esac
[ "$#" -eq 0 ] || { printf 'usage: check-commit.sh [--plan]\n' >&2; exit 2; }

project_root=$(git rev-parse --show-toplevel)
git_local_variables=$(git rev-parse --local-env-vars)

clear_git_environment() {
    # Git supplies these variable names; splitting this list is intentional.
    unset $git_local_variables GIT_PREFIX
}
cd "$project_root"
# A commit is waiting on these checks. Keep resource limits and nice priority,
# but use the existing interactive mode instead of macOS background I/O policy.
export MINYAR_INTERACTIVE_BOOTSTRAP=${MINYAR_INTERACTIVE_BOOTSTRAP:-1}
cache_root=$(git rev-parse --git-path minyar-commit-check)
case $cache_root in /*) ;; *) cache_root=$project_root/$cache_root ;; esac
mkdir -p "$cache_root"
if ! mkdir "$cache_root/lock" 2>/dev/null; then
    printf 'Another commit check owns %s. Wait for it to finish before checking this index.\n' "$cache_root/lock" >&2
    exit 1
fi
trap 'rmdir "$cache_root/lock"' 0
trap 'exit 130' INT
trap 'exit 143' TERM HUP

# Respect Git's active index (including commit -a/--only temporary indexes).
staged_tree=$(git write-tree)
previous_tree=$(git rev-parse --verify HEAD 2>/dev/null || :)
if [ -z "$previous_tree" ]; then
    previous_tree=$(git hash-object -w -t tree --stdin </dev/null)
fi
git diff --name-only --no-renames -z "$previous_tree" "$staged_tree" > "$cache_root/changed-paths"

private_git() (
    private_root=$1
    shift
    clear_git_environment
    git -C "$private_root" "$@"
)

snapshot() {
    destination=$1
    tree=$2
    if [ ! -d "$destination/.git" ]; then
        (
            clear_git_environment
            git clone --quiet --shared --no-checkout -- "$project_root" "$destination"
        )
    fi
    # Git updates only changed tracked files, retaining cached build artifacts.
    # Both the index and worktree belong to this private clone.
    private_git "$destination" read-tree --reset -u "$tree"
}

snapshot "$cache_root/source" "$staged_tree"
snapshot "$cache_root/previous" "$previous_tree"

# Use the staged policy too, so unrelated unstaged compiler/selector edits
# cannot change selection or break a valid partial commit.
planner_root=$cache_root/source
if [ ! -f "$planner_root/tools/check-commit.min" ]; then
    planner_root=$cache_root/previous
    if [ ! -f "$planner_root/tools/check-commit.min" ]; then
        planner_root=$project_root
        printf 'Bootstrapping commit-check policy from the working tree; this staged revision predates it.\n' >&2
    fi
fi
(
    clear_git_environment
    unset MAKEFLAGS MFLAGS MAKELEVEL MAKEFILES GNUMAKEFLAGS
    cd "$planner_root"
    make --no-print-directory -s "build/tooling/tools/check-commit"
)
checker=$planner_root/build/tooling/tools/check-commit
rules=$cache_root/source/build-support/commit-checks.mk
if [ ! -f "$rules" ]; then rules=$project_root/build-support/commit-checks.mk; fi
clang_command=${LLVM_CC:-$(sh "$planner_root/tools/toolchain.sh" default-clang)}

(
    clear_git_environment
    unset MAKEFLAGS MFLAGS MAKELEVEL MAKEFILES GNUMAKEFLAGS
    unset MINYAR_TEST_COMPILER MINYAR_TEST_MODULE_COMPILER MINYAR_TEST_RUNTIME MINYAR_TEST_LINK_FLAGS
    export MINYAR_TEST_CLANG="$clang_command"
    if [ "$plan" -eq 1 ]; then
        "$checker" --root "$cache_root/source" --previous "$cache_root/previous" \
            --changes "$cache_root/changed-paths" --rules "$rules" --plan
    else
        "$checker" --root "$cache_root/source" --previous "$cache_root/previous" \
            --changes "$cache_root/changed-paths" --rules "$rules"
    fi
)

# Reject an index changed concurrently while checks were in flight.
current_tree=$(git write-tree)
if [ "$current_tree" != "$staged_tree" ]; then
    printf 'The staged tree changed during its checks; run the commit check again.\n' >&2
    exit 1
fi
