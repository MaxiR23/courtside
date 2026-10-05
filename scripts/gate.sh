#!/usr/bin/env bash
# INFO: Runs the gate of one app. The only place the gate commands are written:
#       CLAUDE.md, scripts/ship.sh and CI call this script and never repeat its commands.
# REQUIRES: bash 3.2 or newer and BSD or GNU tools. Local git hooks call it on macOS,
#           so it must not use bash 4 features or GNU-only flags.
# STEPS:
#   web [fast]
#     1. Require pnpm and web/node_modules.
#     2. Lint.
#     3. Format check.
#     4. svelte-check.
#     5. Tests.
#     6. Production build.
#     fast runs only steps 1 to 3, for the pre-commit hook.
#     Every step runs from web/ through the scripts in web/package.json
#     and stops at the first failure.
#   api [fast]
#     1. Require api/.venv and Python 3.12 in it.
#     2. ruff check.
#     3. ruff format check.
#     4. mypy strict.
#     5. pytest.
#     fast runs only steps 1 to 3, for the pre-commit hook.
#     Every step runs from api/ and stops at the first failure.

set -eu

die() {
  printf 'gate: %s\n' "$*" >&2
  exit 1
}

info() {
  printf 'gate: %s\n' "$*"
}

usage() {
  die "usage: scripts/gate.sh web|api [fast]"
}

require_web() {
  command -v pnpm >/dev/null 2>&1 \
    || die "web: pnpm not found; install pnpm and run 'pnpm install' in web/"
  [ -d web/node_modules ] \
    || die "web: web/node_modules not found; run 'cd web && pnpm install'"
  cd web || die "cannot change to web"
}

fast_web() {
  info "web: lint"
  pnpm run lint || die "web: lint failed"
  info "web: format check"
  pnpm run format:check || die "web: format check failed"
}

gate_web() {
  require_web
  fast_web
  if [ "$1" = fast ]; then
    info "web: fast gate passed"
    return 0
  fi
  info "web: svelte-check"
  pnpm run check || die "web: svelte-check failed"
  info "web: tests"
  pnpm run test || die "web: tests failed"
  info "web: build"
  pnpm run build || die "web: build failed"
  info "web: passed"
}

require_api() {
  venv_python="api/.venv/bin/python"
  [ -x "$venv_python" ] \
    || die "api: api/.venv not found; create it with 'python3.12 -m venv api/.venv' and install api/requirements-dev.txt"
  version="$("$venv_python" -c 'import sys; print("%d.%d" % sys.version_info[:2])')" \
    || die "api: cannot run $venv_python"
  [ "$version" = "3.12" ] \
    || die "api: api/.venv uses Python $version, 3.12 is required; recreate it with 'python3.12 -m venv api/.venv'"
  cd api || die "cannot change to api"
}

fast_api() {
  info "api: ruff check"
  .venv/bin/python -m ruff check . || die "api: ruff check failed"
  info "api: ruff format check"
  .venv/bin/python -m ruff format --check . || die "api: ruff format check failed"
}

gate_api() {
  require_api
  fast_api
  if [ "$1" = fast ]; then
    info "api: fast gate passed"
    return 0
  fi
  info "api: mypy strict"
  .venv/bin/python -m mypy || die "api: mypy failed"
  info "api: pytest"
  .venv/bin/python -m pytest || die "api: pytest failed"
  info "api: passed"
}

main() {
  [ "$#" -ge 1 ] && [ "$#" -le 2 ] || usage
  mode="full"
  if [ "$#" -eq 2 ]; then
    [ "$2" = fast ] || usage
    mode="fast"
  fi
  root="$(git rev-parse --show-toplevel)" || die "not inside a git repository"
  cd "$root" || die "cannot change to $root"
  case "$1" in
    web) gate_web "$mode" ;;
    api) gate_api "$mode" ;;
    *) usage ;;
  esac
}

main "$@"
