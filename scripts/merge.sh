#!/usr/bin/env bash
# INFO: Squash-merges a published pull request through the REST API and reports the merge commit verification.
# REQUIRES: bash 4 or newer and GNU tools, as in the cloud session.
# STEPS:
#   <pr>
#     1. Require a positive PR number and at least one required CI check in REQUIRED_STATUS.
#     2. Read the PR: require it open, not merged, based on main.
#     3. Wait for GitHub to compute mergeability and require it mergeable.
#     4. Wait until every required CI check run (REQUIRED_STATUS) has run on the head commit and
#        succeeded (timeout 15 minutes). Any failing check run or failing commit status stops the merge.
#        Only the required check runs are waited for: a pending commit status, such as a deploy status,
#        never holds the merge. Print each check run and commit status with its result.
#     5. Squash-merge with "<PR title> (#<pr>)" as the commit title, pinned to the checked head commit.
#     6. Read the merge commit through the REST commits endpoint.
#     7. Print the merge commit SHA, title, verified and reason.

set -euo pipefail

# Names of the CI check runs that must succeed before merging, one per element.
# PENDING: the names are set when the CI workflow is added. While the list is empty, nothing merges.
readonly -a REQUIRED_STATUS=()
readonly BASE="main"
readonly REPO_API="repos/{owner}/{repo}"
readonly CHECKS_INTERVAL=15  # seconds between polls
readonly CHECKS_TIMEOUT=900  # seconds before giving up on pending or missing checks

die() {
  printf 'merge: %s\n' "$*" >&2
  exit 1
}

info() {
  printf 'merge: %s\n' "$*"
}

usage() {
  die "usage: scripts/merge.sh <pr>"
}

read_pr() {
  gh api "$REPO_API/pulls/$1" --jq \
    '[.state, (.merged | tostring), .base.ref, (.mergeable | tostring), .mergeable_state, .head.sha] | join("\t")' \
    || die "cannot read PR #$1"
}

# Prints "<kind>\t<name>\t<verdict>" per check run and commit status of a commit.
# The verdict is success, pending, or the failing conclusion or state.
read_checks() {
  local sha="$1"
  gh api "$REPO_API/commits/$sha/check-runs?per_page=100" --jq '
    (.check_runs[] | ["check run", .name,
      (if .status != "completed" then "pending"
       elif (.conclusion == "success" or .conclusion == "neutral" or .conclusion == "skipped") then "success"
       else (.conclusion // "unknown") end)] | join("\t")),
    (if .total_count > (.check_runs | length) then "check run\t(more than 100)\tunreadable" else empty end)' \
    || die "cannot read the check runs of $sha"
  gh api "$REPO_API/commits/$sha/status?per_page=100" --jq \
    '.statuses[] | ["status", .context, .state] | join("\t")' \
    || die "cannot read the commit statuses of $sha"
}

main() {
  [[ $# -eq 1 ]] || usage
  local pr="$1"
  cd "$(git rev-parse --show-toplevel)"

  # 1. PR number and required checks.
  [[ "$pr" =~ ^[1-9][0-9]*$ ]] || die "PR must be a positive number, got '$pr'"
  [[ ${#REQUIRED_STATUS[@]} -gt 0 ]] || die "no required CI checks configured in REQUIRED_STATUS; refusing to merge"

  # 2. State, merged flag and base.
  local fields state merged base mergeable mstate sha title
  fields="$(read_pr "$pr")"
  IFS=$'\t' read -r state merged base mergeable mstate sha <<<"$fields"
  title="$(gh api "$REPO_API/pulls/$pr" --jq '.title')" || die "cannot read the title of PR #$pr"
  [[ "$state" == open ]] || die "PR #$pr is not open (state: $state)"
  [[ "$merged" == false ]] || die "PR #$pr is already merged"
  [[ "$base" == "$BASE" ]] || die "PR #$pr is based on '$base', not '$BASE'"
  [[ -n "$sha" ]] || die "cannot read the head commit of PR #$pr"

  # 3. Mergeability: null while GitHub computes it.
  local attempt=1
  while [[ "$mergeable" == null && $attempt -lt 10 ]]; do
    sleep 3
    attempt=$((attempt + 1))
    fields="$(read_pr "$pr")"
    IFS=$'\t' read -r state merged base mergeable mstate sha <<<"$fields"
  done
  [[ "$mergeable" == true ]] || die "PR #$pr is not mergeable (mergeable: $mergeable, state: $mstate)"
  [[ "$state" == open && "$merged" == false && "$base" == "$BASE" ]] \
    || die "PR #$pr changed while waiting for mergeability"

  # 4. Wait until every required check run has succeeded; stop on any failing check run or status.
  local checks failing verdicts kind name verdict start=$SECONDS
  local -a missing pending
  while :; do
    checks="$(read_checks "$sha")"
    failing="$(awk -F'\t' '$3 != "success" && $3 != "pending"' <<<"$checks")"
    if [[ -n "$failing" ]]; then
      die "failing checks on $sha: $(cut -f1-3 --output-delimiter=' ' <<<"$failing" | paste -sd ';' -)"
    fi
    missing=()
    pending=()
    for name in "${REQUIRED_STATUS[@]}"; do
      verdicts="$(awk -F'\t' -v n="$name" '$1 == "check run" && $2 == n { print $3 }' <<<"$checks")"
      if [[ -z "$verdicts" ]]; then
        missing+=("$name")
      elif grep -qvx success <<<"$verdicts"; then
        pending+=("$name")
      fi
    done
    if [[ ${#missing[@]} -eq 0 && ${#pending[@]} -eq 0 ]]; then
      break
    fi
    if [[ $((SECONDS - start)) -ge $CHECKS_TIMEOUT ]]; then
      [[ ${#missing[@]} -eq 0 ]] \
        || die "timed out after ${CHECKS_TIMEOUT}s: required checks not reported on $sha: ${missing[*]}; refusing to merge"
      die "timed out after ${CHECKS_TIMEOUT}s waiting for required checks: ${pending[*]}"
    fi
    info "waiting on $sha: ${#missing[@]} required check(s) not reported, ${#pending[@]} pending"
    sleep "$CHECKS_INTERVAL"
  done
  while IFS=$'\t' read -r kind name verdict; do
    [[ -n "$kind" ]] || continue
    info "$kind '$name': $verdict"
  done <<<"$checks"

  # 5. Squash merge pinned to the checked head commit.
  local commit_title merge_sha
  commit_title="$title (#$pr)"
  merge_sha="$(gh api -X PUT "$REPO_API/pulls/$pr/merge" \
    -f merge_method=squash -f commit_title="$commit_title" -f sha="$sha" --jq '.sha')" \
    || die "GitHub refused to merge PR #$pr"
  [[ -n "$merge_sha" ]] || die "merge of PR #$pr returned no commit SHA"

  # 6. Merge commit verification.
  local verification
  verification="$(gh api "$REPO_API/commits/$merge_sha" --jq \
    '.commit.verification | "verified: \(.verified)\nreason: \(.reason)"')" \
    || die "PR #$pr is merged as $merge_sha but its verification cannot be read"

  # 7. Report.
  info "merge commit: $merge_sha"
  info "title: $commit_title"
  printf '%s\n' "$verification"
}

main "$@"
