#!/usr/bin/env bash
# INFO: Deterministic issue creation flow that enforces the repository rules.
# REQUIRES: bash 4 or newer and GNU tools, as in the cloud session.
# STEPS:
#   create <type> "<description>" <body-file>
#     1. Require an allowed type.
#     2. Require a Conventional Commits description: lowercase, single line, no trailing period.
#     3. Build the title as "<type>: <description>".
#     4. Require an existing, non-empty body file.
#     5. Validate the body: no HTML template comments and no attribution.
#     6. Require the label <type> to exist in the repository.
#     7. Create the issue through the REST API with the label and the repository owner as assignee.
#     8. Print the issue number, title, labels, assignees and URL.
#     9. Print a reminder that the footer removal step from docs/workflow.md is required.

set -euo pipefail

readonly TYPES="feat fix docs chore refactor test style perf ci build"
readonly REPO_API="repos/{owner}/{repo}"

die() {
  printf 'issue: %s\n' "$*" >&2
  exit 1
}

info() {
  printf 'issue: %s\n' "$*"
}

usage() {
  die "usage: scripts/issue.sh create <type> \"<description>\" <body-file>"
}

validate_type() {
  local type="$1"
  [[ -n "$type" && " $TYPES " == *" $type "* ]] || die "type must be one of: $TYPES; got '$type'"
}

validate_description() {
  local description="$1"
  [[ -n "$description" ]] || die "description is empty"
  [[ "$description" != *$'\n'* && "$description" != *$'\r'* ]] || die "description must be a single line"
  [[ "$description" =~ ^[^[:space:]](.*[^[:space:]])?$ ]] \
    || die "description must not start or end with whitespace: '$description'"
  [[ "$description" == "${description,,}" ]] || die "description must be lowercase: '$description'"
  [[ "$description" != *. ]] || die "description must not end with a period: '$description'"
}

# Same checks as validate_body in scripts/ship.sh, without the "Closes #" line.
validate_body() {
  local body="$1"
  [[ -f "$body" ]] || die "body file not found: $body"
  [[ -s "$body" ]] || die "body file is empty: $body"
  if grep -qF '<!--' "$body"; then
    die "$body contains an HTML template comment"
  fi
  if grep -qw 'Claude' "$body"; then
    die "$body contains attribution: the word 'Claude'"
  fi
  if grep -qiE 'co-authored-by|generated with|claude code|anthropic' "$body"; then
    die "$body contains attribution"
  fi
}

cmd_create() {
  [[ $# -eq 3 ]] || usage
  local type="$1" description="$2" body="$3"

  # 1 to 3. Type, description and title.
  validate_type "$type"
  validate_description "$description"
  local title="$type: $description"

  # 4 and 5. Body.
  validate_body "$body"
  body="$(realpath -- "$body")" || die "cannot resolve $body"

  cd "$(git rev-parse --show-toplevel)" || die "not inside a git repository"

  # 6. Label exists.
  gh api "$REPO_API/labels/$type" --silent || die "label '$type' does not exist in the repository"

  # 7. Create, assigned to the repository owner.
  local owner number
  owner="$(gh api "$REPO_API" --jq '.owner.login')" || die "cannot read the repository owner"
  [[ -n "$owner" ]] || die "the repository owner is empty"
  number="$(gh api -X POST "$REPO_API/issues" -f title="$title" -F body=@"$body" \
    -f "labels[]=$type" -f "assignees[]=$owner" --jq '.number')" \
    || die "cannot create the issue"
  [[ "$number" =~ ^[1-9][0-9]*$ ]] || die "unexpected issue number: '$number'"

  # 8. Report.
  gh api "$REPO_API/issues/$number" --jq \
    '"Issue #\(.number)\nTitle: \(.title)\nLabels: \([.labels[].name] | join(", "))\nAssignees: \([.assignees[].login] | join(", "))\nURL: \(.html_url)"' \
    || die "cannot read issue #$number"

  # 9. Footer reminder.
  printf '\n'
  info "required: remove the issue footer as described in docs/workflow.md, section 7"
}

main() {
  [[ $# -ge 1 ]] || usage
  local command="$1"
  shift
  case "$command" in
    create) cmd_create "$@" ;;
    *) usage ;;
  esac
}

main "$@"
