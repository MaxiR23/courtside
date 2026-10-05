#!/usr/bin/env bash
# INFO: Picks the loop path of a change and prints one word: short or full.
# REQUIRES: bash 4 or newer and GNU tools, as in the cloud session.
#
#   short   every changed file is a .md, and none is CLAUDE.md,
#           docs/architecture.md or docs/workflow.md,
#           or lives under .claude/ or .github/
#   full    anything else, including a change with no files
#
# The changed files are the paths given as arguments or, with none, what
# differs from origin/main: the branch's commits, the working tree and the
# untracked files. A rename counts as both of its paths, so renaming one
# of those files out of its place still forces the full loop.
# The files that force the full loop go to stderr.

set -euo pipefail

changed_files() {
  if [ "$#" -gt 0 ]; then
    printf '%s\n' "$@"
    return
  fi
  {
    git diff --name-only --no-renames origin/main...HEAD
    git diff --name-only --no-renames HEAD
    git ls-files --others --exclude-standard
  } | sort -u
}

path="short"
count=0
while IFS= read -r file; do
  [ -n "$file" ] || continue
  count=$((count + 1))
  case "$file" in
    CLAUDE.md | .claude/* | .github/*) reason="is loop configuration" ;;
    docs/architecture.md | docs/workflow.md) reason="is a rules document" ;;
    *.md) continue ;;
    *) reason="is not a .md file" ;;
  esac
  echo "loop-path: $file $reason" >&2
  path="full"
done < <(changed_files "$@")

[ "$count" -gt 0 ] || path="full"
echo "$path"
