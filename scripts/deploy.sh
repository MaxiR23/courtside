#!/usr/bin/env bash
# INFO: Deploys the backend over SSH and the front end to Vercel from the owner's machine.
#       The settings live in .env.deploy at the repository root, listed in .env.deploy.example.
# REQUIRES: bash 3.2 or newer and BSD or GNU tools. It runs on the owner's machine,
#           so it must not use bash 4 features or GNU-only flags.
# STEPS:
#   [api|web|all]   no argument means all
#     1. Read the keys of .env.deploy and stop naming a missing DEPLOY_SSH_HOST,
#        DEPLOY_SITE_URL or DEPLOY_VERCEL_DIR, or naming DEPLOY_SSH_HOST when it is not
#        letters, digits, dots, hyphens and underscores or starts with -.
#     2. Require branch main, a clean tree and main equal to origin/main, and record that
#        commit.
#     3. web, all: require pnpm, vercel, web/.env and a dedicated Vercel folder linked with
#        vercel link: not /, not the home folder, not inside the repository and not a folder
#        that contains it, and DEPLOY_VERCEL_PROJECT_ID set and equal to the projectId in its
#        .vercel/project.json.
#     4. api, all: fetch and fast-forward the machine to exactly that commit over SSH, stop
#        when its HEAD differs, rebuild, then wait up to 180 s for the api service to be
#        healthy.
#     5. web, all: build with every feed URL set to the site's /api/feeds path, replace the
#        Vercel folder except .vercel, add deploy/vercel.json and run vercel deploy --prod.
#     6. Check that / and /api/health on the site answer 200.
#   No message prints a value of .env.deploy.

set -eu

die() {
  printf 'deploy: %s\n' "$*" >&2
  exit 1
}

info() {
  printf 'deploy: %s\n' "$*"
}

usage() {
  die "usage: scripts/deploy.sh [api|web|all]"
}

# Prints the last value of a key in .env.deploy, empty when the line is missing.
read_key() {
  grep -E "^$1=" .env.deploy | tail -n 1 | cut -d= -f2- || true
}

# Prints the projectId of a .vercel/project.json, empty when it has none. Plain text
# matching of "projectId": "<value>", no JSON parser.
read_project_id() {
  sed -n 's/.*"projectId"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$1" | head -n 1 || true
}

require_key() {
  [ -n "$2" ] || die "set $1 in .env.deploy at the repository root"
}

# One "NAME path" pair per line: the feed URLs the front end reads at build time.
feed_paths() {
  cat <<'LIST'
GAMES_FEED_URL games.json
STANDINGS_FEED_URL standings.json
SEARCH_FEED_URL search.json
CUP_FEED_URL cup.json
CUP_MATCHUP_FEED_URL cup/matchups/{id}.json
PLAYOFFS_FEED_URL playoffs.json
PLAYOFFS_FINALS_FEED_URL playoffs/finals.json
ALL_STAR_FEED_URL all-star.json
HOME_FEED_URL home.json
POWER_RANKING_FEED_URL power-ranking.json
GAME_DETAIL_FEED_URL games/{id}.json
TEAM_FEED_URL teams/{code}.json
PLAYER_FEED_URL players/{id}.json
CALENDAR_FEED_URL seasons/{season}/calendar.json
DAY_FEED_URL days/{date}.json
SEASON_STANDINGS_FEED_URL seasons/{season}/standings.json
SEASON_TEAM_FEED_URL seasons/{season}/teams/{code}.json
SEASON_PLAYER_FEED_URL seasons/{season}/players/{id}.json
SEASON_CUP_FEED_URL seasons/{season}/cup.json
SEASON_CUP_MATCHUP_FEED_URL seasons/{season}/cup/matchups/{slot}.json
SEASON_PLAYOFFS_FEED_URL seasons/{season}/playoffs.json
SEASON_PLAYOFFS_FINALS_FEED_URL seasons/{season}/playoffs/finals.json
SEASON_ALL_STAR_FEED_URL seasons/{season}/all-star.json
LIST
}

# Runs in a subshell: the exported feed URLs reach only the build's environment, and
# web/.env is never written. The environment of the build wins over web/.env.
build_web() {
  feed_paths | {
    while read -r name path; do
      export "$name=$site/api/feeds/$path"
    done
    cd web && pnpm install --frozen-lockfile && pnpm run build
  }
}

check_git() {
  branch="$(git symbolic-ref --quiet --short HEAD || true)"
  [ "$branch" = main ] || die "deploy runs only from main"
  [ -z "$(git status --porcelain)" ] || die "the working tree is not clean"
  git fetch --quiet origin main || die "cannot fetch origin"
  [ "$(git rev-parse main)" = "$(git rev-parse origin/main)" ] \
    || die "main is not equal to origin/main"
  commit="$(git rev-parse HEAD)" || die "cannot read the checked commit"
}

check_web() {
  command -v pnpm >/dev/null 2>&1 || die "web: pnpm not found; install pnpm"
  command -v vercel >/dev/null 2>&1 || die "web: vercel not found; run 'pnpm add -g vercel' and 'vercel login'"
  [ -f web/.env ] || die "web/.env not found; copy web/.env.example and set the values that are not feed URLs"
  case "$vercel_dir" in
    /*) ;;
    *) die "DEPLOY_VERCEL_DIR must be an absolute path" ;;
  esac
  vercel_real="$(cd "$vercel_dir" 2>/dev/null && pwd -P)" || die "cannot enter DEPLOY_VERCEL_DIR"
  case "$vercel_real" in
    /) die "DEPLOY_VERCEL_DIR must not be the root folder" ;;
  esac
  home_real="$(cd "${HOME:-/nonexistent}" 2>/dev/null && pwd -P || true)"
  if [ -n "$home_real" ] && [ "$vercel_real" = "$home_real" ]; then
    die "DEPLOY_VERCEL_DIR must not be the home folder"
  fi
  case "$vercel_real/" in
    "$root_real"/*) die "DEPLOY_VERCEL_DIR must be outside the repository" ;;
  esac
  case "$root_real/" in
    "$vercel_real"/*) die "DEPLOY_VERCEL_DIR must not contain the repository" ;;
  esac
  [ -f "$vercel_real/.vercel/project.json" ] \
    || die "DEPLOY_VERCEL_DIR is not a folder linked with vercel link"
  require_key DEPLOY_VERCEL_PROJECT_ID "$vercel_project_id"
  linked_project_id="$(read_project_id "$vercel_real/.vercel/project.json")"
  [ -n "$linked_project_id" ] \
    || die "projectId not found in .vercel/project.json of DEPLOY_VERCEL_DIR; run vercel link there"
  [ "$linked_project_id" = "$vercel_project_id" ] \
    || die "DEPLOY_VERCEL_PROJECT_ID does not match the projectId in .vercel/project.json of DEPLOY_VERCEL_DIR"
}

deploy_api() {
  info "api: moving the machine to $commit"
  ssh "$ssh_host" "cd ~/courtside && git fetch --quiet origin && git merge --ff-only $commit" \
    || die "api: the remote update failed"
  remote_head="$(ssh "$ssh_host" 'cd ~/courtside && git rev-parse HEAD')" \
    || die "api: cannot read the machine's commit"
  [ "$remote_head" = "$commit" ] \
    || die "api: the machine is on $remote_head, not on the checked commit $commit"
  info "api: rebuilding on the machine"
  ssh "$ssh_host" 'cd ~/courtside && sudo docker compose up -d --build' \
    || die "api: the rebuild failed"
  tries=0
  health=""
  while [ "$tries" -lt 36 ]; do
    tries=$((tries + 1))
    health="$(ssh "$ssh_host" 'cd ~/courtside && sudo docker compose ps --format "{{.Health}}" api' || true)"
    [ "$health" = healthy ] && break
    [ "$tries" -lt 36 ] && sleep 5
  done
  [ "$health" = healthy ] \
    || die "api: the api service is not healthy after 180 seconds; run 'docker compose logs api' on the machine"
  info "api: healthy"
}

deploy_web() {
  info "web: building"
  (build_web) || die "web: build failed"
  [ -f web/build/200.html ] || die "web: web/build/200.html missing after the build"
  info "web: replacing the Vercel folder"
  find "$vercel_real" -mindepth 1 -maxdepth 1 ! -name .vercel -exec rm -rf {} +
  cp -R web/build/. "$vercel_real"/
  cp deploy/vercel.json "$vercel_real"/vercel.json
  info "web: deploying to production"
  (cd "$vercel_real" && vercel deploy --prod) || die "web: vercel deploy failed"
}

smoke() {
  for path in / /api/health; do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$site$path" || true)"
    [ "$code" = 200 ] || die "smoke: $path answered $code, expected 200"
    info "smoke: $path answered 200"
  done
}

main() {
  [ "$#" -le 1 ] || usage
  mode="${1:-all}"
  case "$mode" in
    api | web | all) ;;
    *) usage ;;
  esac
  root="$(git rev-parse --show-toplevel)" || die "not inside a git repository"
  cd "$root" || die "cannot change to the repository root"
  root_real="$(pwd -P)"

  [ -f .env.deploy ] \
    || die ".env.deploy not found at the repository root; copy .env.deploy.example and fill it in"
  ssh_host="$(read_key DEPLOY_SSH_HOST)"
  site="$(read_key DEPLOY_SITE_URL)"
  vercel_dir="$(read_key DEPLOY_VERCEL_DIR)"
  vercel_project_id="$(read_key DEPLOY_VERCEL_PROJECT_ID)"
  require_key DEPLOY_SSH_HOST "$ssh_host"
  require_key DEPLOY_SITE_URL "$site"
  require_key DEPLOY_VERCEL_DIR "$vercel_dir"
  case "$ssh_host" in
    -* | *[!abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-]*)
      die "DEPLOY_SSH_HOST must be a host alias or hostname of letters, digits, dots, hyphens and underscores, not starting with -"
      ;;
  esac
  case "$site" in
    https://*) ;;
    *) die "DEPLOY_SITE_URL must start with https://" ;;
  esac
  site="${site%/}"

  check_git
  command -v curl >/dev/null 2>&1 || die "curl not found"
  if [ "$mode" != api ]; then
    check_web
  fi
  if [ "$mode" != web ]; then
    command -v ssh >/dev/null 2>&1 || die "ssh not found"
    deploy_api
  fi
  if [ "$mode" != api ]; then
    deploy_web
  fi
  smoke
  info "done"
}

main "$@"
