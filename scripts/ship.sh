#!/usr/bin/env bash
# INFO: Deterministic branch, commit, push and pull request flow that enforces the repository rules.
# REQUIRES: bash 4 or newer and GNU tools, as in the cloud session.
# STEPS:
#   prepare <issue> [path ...]
#     1. Fail if a rebase, merge or cherry-pick is in progress.
#     2. Read the issue labels and require exactly one type label.
#     3. Read the issue title and require its type to match the label.
#     4. Fetch origin.
#     5. On main or on a branch that is not type/short-description: require local main and HEAD to
#        be ancestors of origin/main, create the type/short-description branch from origin/main
#        carrying the uncommitted changes, then fast-forward local main to origin/main.
#     6. Require a valid type/short-description branch.
#     7. Fail if the branch is pushed but has no open PR.
#     8. Fail if the branch has more than one open PR.
#     9. Fail if the branch is not pushed and is behind origin/main.
#    10. Validate every path.
#    11. Refuse Anthropic noreply author or committer identities.
#    12. Run the gate (scripts/gate.sh web and api) and stop if it fails.
#    13. Commit the paths: new commit, amend, or no commit.
#    14. Refuse Co-Authored-By and Claude-Session trailers on the branch.
#    15. Write .claude/loop/pr-<issue>.meta.
#    16. Print the meta file and the branch log, then ask for the PR body and the publish run.
#   publish <issue>
#     1. Require the meta file and a non-empty body file.
#     2. Validate the body.
#     3. Read the meta fields.
#     4. Require the meta branch, the meta commit and no uncommitted tracked changes.
#     5. Require the label to exist in the repository.
#     6. Re-check the open PR against the meta mode.
#     7. Run the gate (scripts/gate.sh web and api) and stop if it fails.
#     8. Push the branch.
#     9. Create mode: create the PR through the REST API with base, title and body, then add the label
#        and the repository owner as assignee.
#    10. Update mode: edit the PR title and body through the REST API.
#    11. Print the PR number, title, labels, draft state, base and URL.
#    12. Print a reminder that the footer removal step from docs/workflow.md is required.

set -euo pipefail

readonly TYPES="feat fix docs chore refactor test style perf ci build"
readonly TYPE_RE="feat|fix|docs|chore|refactor|test|style|perf|ci|build"
readonly BASE="main"
readonly LOOP_DIR=".claude/loop"
readonly REPO_API="repos/{owner}/{repo}"

die() {
  printf 'ship: %s\n' "$*" >&2
  exit 1
}

info() {
  printf 'ship: %s\n' "$*"
}

usage() {
  die "usage: scripts/ship.sh prepare <issue> [path ...] | scripts/ship.sh publish <issue>"
}

require_issue_number() {
  [[ "$1" =~ ^[1-9][0-9]*$ ]] || die "issue must be a positive number, got '$1'"
}

repo_owner() {
  gh api "$REPO_API" --jq '.owner.login' || die "cannot read the repository owner"
}

# Prints the numbers of the open PRs whose head is the given branch, one per line.
open_prs() {
  local owner="$1" branch="$2"
  gh api "$REPO_API/pulls?state=open&head=$owner:$branch&per_page=100" --jq '.[].number' \
    || die "cannot list open pull requests for $branch"
}

check_no_operation_in_progress() {
  local marker
  for marker in rebase-merge rebase-apply MERGE_HEAD CHERRY_PICK_HEAD; do
    if [[ -e "$(git rev-parse --git-path "$marker")" ]]; then
      die "a rebase, merge or cherry-pick is in progress ($marker)"
    fi
  done
}

# Validates one path and prints it without a leading "./".
validate_path() {
  local path="$1" name
  [[ -n "$path" ]] || die "empty path"
  [[ "$path" != /* ]] || die "absolute paths are not allowed: $path"
  case "/$path/" in
    */../*) die "path traversal is not allowed: $path" ;;
  esac
  path="${path#./}"
  case "/$path/" in
    */./* | *//*) die "path is not normalized: $path" ;;
  esac
  name="${path##*/}"
  case "$name" in
    .env.example) ;;
    .env | .env.*) die "refusing environment file: $path" ;;
  esac
  case "$path" in
    .claude/settings.json | .claude/agents/?* | .claude/skills/?*) ;;
    .claude/loop | .claude/loop/*) die "refusing working file: $path" ;;
    .claude/settings.local.json) die "refusing local settings: $path" ;;
    .claude | .claude/*) die "refusing path under .claude/: $path" ;;
  esac
  printf '%s\n' "$path"
}

check_identities() {
  local var ident
  for var in GIT_AUTHOR_IDENT GIT_COMMITTER_IDENT; do
    ident="$(git var "$var")" || die "cannot read $var"
    if [[ "${ident,,}" == *noreply@anthropic.com* ]]; then
      die "$var uses noreply@anthropic.com; set your own git identity"
    fi
  done
}

# Stages the given paths, skipping those whose deletion is already staged.
stage_paths() {
  local deleted path
  deleted="$(git diff --cached --name-only --diff-filter=D)"
  for path in "$@"; do
    if grep -qxF -- "$path" <<<"$deleted"; then
      info "skipping $path: its deletion is already staged"
      continue
    fi
    git add -A -- "$path" || die "cannot stage $path"
  done
}

# Commits the index with the given message; amends HEAD when the second argument is 1.
commit_index() {
  local message="$1" amend="$2"
  if [[ "$amend" == 1 ]]; then
    git commit --amend -m "$message"
  else
    git commit -m "$message"
  fi
}

check_trailers() {
  local messages
  messages="$(git log --format=%B "origin/$BASE..HEAD")"
  if grep -qiE '^(co-authored-by|claude-session):' <<<"$messages"; then
    die "a commit on this branch has a Co-Authored-By or Claude-Session trailer"
  fi
}

# Runs the gate of both apps through scripts/gate.sh, from the repository root.
run_gate() {
  local app
  for app in web api; do
    info "running the gate: scripts/gate.sh $app"
    scripts/gate.sh "$app" || die "the gate failed (scripts/gate.sh $app); fix it and run again"
  done
}

# Creates the branch from origin/main, carrying the uncommitted changes, then fast-forwards
# local main to origin/main. Every check runs before the first change; nothing is forced.
create_branch_from_base() {
  local current="$1" branch="$2"
  if ! git merge-base --is-ancestor "$BASE" "origin/$BASE"; then
    die "prepare: local $BASE has diverged from origin/$BASE; nothing was changed. Reconciling it is the owner's decision"
  fi
  if ! git merge-base --is-ancestor HEAD "origin/$BASE"; then
    die "prepare: $current has commits that are not on origin/$BASE; nothing was changed"
  fi
  git switch --no-track -c "$branch" "origin/$BASE" \
    || die "prepare: cannot create $branch from origin/$BASE (see git's message above); nothing was changed"
  if [[ "$(git rev-parse "$BASE")" != "$(git rev-parse "origin/$BASE")" ]]; then
    git fetch . "refs/remotes/origin/$BASE:refs/heads/$BASE" \
      || die "prepare: $branch was created, but $BASE could not be fast-forwarded to origin/$BASE"
    info "prepare: fast-forwarded $BASE to origin/$BASE"
  fi
}

cmd_prepare() {
  [[ $# -ge 1 ]] || usage
  local issue="$1"
  shift
  require_issue_number "$issue"

  cd "$(git rev-parse --show-toplevel)" || die "not inside a git repository"

  # 1. No operation in progress.
  check_no_operation_in_progress

  # 2. Exactly one type label.
  local is_pr labels label="" count=0 name
  is_pr="$(gh api "$REPO_API/issues/$issue" --jq '.pull_request != null')" \
    || die "cannot read issue #$issue"
  [[ "$is_pr" == false ]] || die "#$issue is a pull request, not an issue"
  labels="$(gh api "$REPO_API/issues/$issue" --jq '.labels[].name')" \
    || die "cannot read the labels of issue #$issue"
  while IFS= read -r name; do
    [[ -n "$name" ]] || continue
    if [[ " $TYPES " == *" $name "* ]]; then
      label="$name"
      count=$((count + 1))
    fi
  done <<<"$labels"
  [[ "$count" -eq 1 ]] || die "issue #$issue must have exactly one type label ($TYPES), found $count"

  # 3. Title type matches the label.
  local title title_type description
  title="$(gh api "$REPO_API/issues/$issue" --jq '.title')" || die "cannot read the title of issue #$issue"
  if [[ ! "$title" =~ ^($TYPE_RE)(\([^\)]*\))?!?:\ (.+)$ ]]; then
    die "issue title is not 'type: description': $title"
  fi
  title_type="${BASH_REMATCH[1]}"
  description="${BASH_REMATCH[3]}"
  [[ "$title_type" == "$label" ]] || die "title type '$title_type' does not match label '$label'"

  # 4. Fetch.
  git fetch --prune origin || die "git fetch origin failed"

  # 5. Create the branch when on main or on a branch that is not a type/short-description branch.
  local branch current
  current="$(git symbolic-ref --short -q HEAD)" || die "HEAD is detached; switch to a branch"
  branch="$current"
  if [[ "$current" == "$BASE" || ! "$current" =~ ^($TYPE_RE)/[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
    local slug
    slug="$(printf '%s' "$description" | tr '[:upper:]' '[:lower:]' \
      | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' | cut -d- -f1-5)"
    [[ -n "$slug" ]] || die "cannot build a branch name from the title: $title"
    branch="$label/$slug"
    if git rev-parse --verify -q "refs/heads/$branch" >/dev/null; then
      die "branch $branch already exists; switch to it and run prepare again"
    fi
    create_branch_from_base "$current" "$branch"
  fi

  # 6. Valid branch name.
  if [[ ! "$branch" =~ ^($TYPE_RE)/[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
    die "branch '$branch' is neither $BASE nor a valid type/short-description branch"
  fi

  # 7 and 8. Open PR state.
  local owner pushed=0 pr="" list
  local -a prs=()
  owner="$(repo_owner)"
  if git rev-parse --verify -q "refs/remotes/origin/$branch" >/dev/null; then
    pushed=1
  fi
  list="$(open_prs "$owner" "$branch")"
  [[ -z "$list" ]] || mapfile -t prs <<<"$list"
  if [[ "${#prs[@]}" -gt 1 ]]; then
    die "branch $branch has more than one open PR: ${prs[*]}"
  fi
  pr="${prs[0]:-}"
  if [[ "$pushed" == 1 && -z "$pr" ]]; then
    die "branch $branch is pushed but has no open PR"
  fi

  # 9. Not pushed and behind origin/main.
  if [[ "$pushed" == 0 ]] && ! git merge-base --is-ancestor "origin/$BASE" HEAD; then
    die "branch $branch is behind origin/$BASE; rebasing is the owner's decision"
  fi

  # 10. Validate paths.
  local -a paths=()
  local path
  for path in "$@"; do
    paths+=("$(validate_path "$path")")
  done

  # 11. Identities.
  check_identities

  # 12. Gate.
  run_gate

  # 13. Commit.
  local ahead amend=0
  ahead="$(git rev-list --count "origin/$BASE..HEAD")"
  if [[ "${#paths[@]}" -eq 0 ]]; then
    if [[ -n "$pr" ]]; then
      info "no paths: description-only update of PR #$pr, no commit"
    elif [[ "$ahead" -gt 0 ]]; then
      info "no paths: branch is already ahead of origin/$BASE, no commit"
    else
      die "no paths given and nothing to deliver"
    fi
  else
    if [[ "$pushed" == 0 && "$ahead" -gt 0 ]]; then
      amend=1
    fi
    stage_paths "${paths[@]}"
    if [[ "$amend" == 0 ]] && git diff --cached --quiet; then
      die "nothing to commit for the given paths"
    fi
    if ! commit_index "$title" "$amend"; then
      info "commit failed; re-staging the same paths and retrying once"
      stage_paths "${paths[@]}"
      commit_index "$title" "$amend" || die "commit failed twice"
    fi
  fi

  # 14. Trailers.
  check_trailers

  # 15. Meta file.
  local mode pr_title meta head
  if [[ -n "$pr" ]]; then
    mode="update #$pr"
    pr_title="$(gh api "$REPO_API/pulls/$pr" --jq '.title')" || die "cannot read PR #$pr"
  else
    mode="create"
    pr_title="$title"
  fi
  head="$(git rev-parse HEAD)"
  mkdir -p "$LOOP_DIR"
  meta="$LOOP_DIR/pr-$issue.meta"
  {
    printf 'Title: %s\n' "$pr_title"
    printf 'Label: %s\n' "$label"
    printf 'Base: %s\n' "$BASE"
    printf 'Branch: %s\n' "$branch"
    printf 'Commit: %s\n' "$head"
    printf 'Mode: %s\n' "$mode"
  } >"$meta"

  # 16. Report.
  printf '\n%s\n' "$meta"
  cat "$meta"
  printf '\ngit log --oneline origin/%s..HEAD\n' "$BASE"
  git log --oneline "origin/$BASE..HEAD"
  printf '\n'
  info "write $LOOP_DIR/pr-$issue.body.md (first line: Closes #$issue), then run: scripts/ship.sh publish $issue"
}

validate_body() {
  local issue="$1" body="$2" first
  first="$(head -n 1 "$body")"
  [[ "$first" == "Closes #$issue" ]] || die "the first line of $body must be exactly 'Closes #$issue'"
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

# Prints the number of the single open PR for the branch, or nothing.
single_open_pr() {
  local owner="$1" branch="$2"
  local list
  local -a prs=()
  list="$(open_prs "$owner" "$branch")"
  [[ -z "$list" ]] || mapfile -t prs <<<"$list"
  [[ "${#prs[@]}" -le 1 ]] || die "branch $branch has more than one open PR: ${prs[*]}"
  printf '%s' "${prs[0]:-}"
}

create_pr() {
  local owner="$1" branch="$2" title="$3" label="$4" body="$5" number

  number="$(gh api -X POST "$REPO_API/pulls" -f title="$title" -f head="$branch" \
    -f base="$BASE" -F body=@"$body" --jq '.number')" || die "cannot create the pull request"
  [[ "$number" =~ ^[1-9][0-9]*$ ]] || die "unexpected pull request number: '$number'"

  gh api -X POST "$REPO_API/issues/$number/labels" -f "labels[]=$label" --silent \
    || die "cannot add label $label to PR #$number"
  gh api -X POST "$REPO_API/issues/$number/assignees" -f "assignees[]=$owner" --silent \
    || die "cannot assign $owner to PR #$number"
  printf '%s' "$number"
}

update_pr() {
  local number="$1" title="$2" body="$3"
  gh api -X PATCH "$REPO_API/pulls/$number" -f title="$title" -F body=@"$body" --silent \
    || die "cannot update PR #$number"
}

cmd_publish() {
  [[ $# -eq 1 ]] || usage
  local issue="$1"
  require_issue_number "$issue"

  cd "$(git rev-parse --show-toplevel)" || die "not inside a git repository"

  # 1. Meta and body files.
  local meta="$LOOP_DIR/pr-$issue.meta" body="$LOOP_DIR/pr-$issue.body.md"
  [[ -f "$meta" ]] || die "$meta is missing; run prepare first"
  [[ -s "$body" ]] || die "$body is missing or empty"

  # 2. Body.
  validate_body "$issue" "$body"

  # 3. Meta fields.
  local line m_title="" m_label="" m_base="" m_branch="" m_commit="" m_mode=""
  while IFS= read -r line; do
    case "$line" in
      "Title: "*) m_title="${line#Title: }" ;;
      "Label: "*) m_label="${line#Label: }" ;;
      "Base: "*) m_base="${line#Base: }" ;;
      "Branch: "*) m_branch="${line#Branch: }" ;;
      "Commit: "*) m_commit="${line#Commit: }" ;;
      "Mode: "*) m_mode="${line#Mode: }" ;;
    esac
  done <"$meta"
  [[ -n "$m_title" && -n "$m_label" && -n "$m_branch" && -n "$m_commit" && -n "$m_mode" ]] \
    || die "$meta is incomplete; prepare again"
  [[ "$m_base" == "$BASE" ]] || die "$meta has base '$m_base', expected $BASE; prepare again"

  # 4. Same branch, same HEAD, clean tracked files.
  local branch
  branch="$(git symbolic-ref --short -q HEAD)" || die "HEAD is detached; prepare again"
  [[ "$branch" == "$m_branch" ]] || die "current branch $branch differs from $m_branch; prepare again"
  [[ "$(git rev-parse HEAD)" == "$m_commit" ]] || die "HEAD differs from the prepared commit; prepare again"
  git diff --quiet HEAD -- || die "there are uncommitted changes in tracked files; prepare again"

  # 5. Label exists.
  gh api "$REPO_API/labels/$m_label" --silent || die "label '$m_label' does not exist in the repository"

  # 6. Open PR matches the mode.
  local owner pr
  owner="$(repo_owner)"
  pr="$(single_open_pr "$owner" "$m_branch")"
  case "$m_mode" in
    create)
      [[ -z "$pr" ]] || die "mode is create but PR #$pr is already open; prepare again"
      ;;
    "update #"*)
      [[ "$pr" == "${m_mode#update #}" ]] || die "mode is '$m_mode' but the open PR is '${pr:-none}'; prepare again"
      ;;
    *)
      die "unknown mode '$m_mode' in $meta"
      ;;
  esac

  # 7. Gate.
  run_gate

  # 8. Push.
  git push -u origin "$m_branch" || die "git push failed"

  # 9 and 10. Create or update.
  local number
  if [[ "$m_mode" == create ]]; then
    number="$(create_pr "$owner" "$m_branch" "$m_title" "$m_label" "$body")"
  else
    number="${m_mode#update #}"
    update_pr "$number" "$m_title" "$body"
  fi

  # 11. Report.
  gh api "$REPO_API/pulls/$number" --jq \
    '"PR #\(.number)\nTitle: \(.title)\nLabels: \([.labels[].name] | join(", "))\nDraft: \(.draft)\nBase: \(.base.ref)\nURL: \(.html_url)"' \
    || die "cannot read PR #$number"

  # 12. Footer reminder.
  printf '\n'
  info "required: remove the PR footer as described in docs/workflow.md, section 7"
}

main() {
  [[ $# -ge 1 ]] || usage
  local command="$1"
  shift
  case "$command" in
    prepare) cmd_prepare "$@" ;;
    publish) cmd_publish "$@" ;;
    *) usage ;;
  esac
}

main "$@"
