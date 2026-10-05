#!/usr/bin/env bash
# INFO: Runs the gate of one app. The only place the gate commands are written:
#       CLAUDE.md, scripts/ship.sh and CI call this script and never repeat its commands.
# REQUIRES: bash 3.2 or newer and BSD or GNU tools. Local git hooks call it on macOS,
#           so it must not use bash 4 features or GNU-only flags.
# STEPS:
#   web
#     1. Run the gate of /web from the repository root.
#   api
#     1. Require api/.venv and Python 3.12 in it.
#     2. ruff check.
#     3. ruff format check.
#     4. mypy strict.
#     5. pytest.
#     Every step runs from api/ and stops at the first failure.
#
# The web gate is pending until /web is scaffolded: until then it reports
# that it is pending and exits successfully.

set -eu

die() {
  printf 'gate: %s\n' "$*" >&2
  exit 1
}

info() {
  printf 'gate: %s\n' "$*"
}

usage() {
  die "usage: scripts/gate.sh web | scripts/gate.sh api"
}

gate_web() {
  # PENDING: the /web gate commands are written here when /web is scaffolded.
  info "web: pending, /web is not scaffolded yet; no checks run"
}

gate_api() {
  venv_python="api/.venv/bin/python"
  [ -x "$venv_python" ] \
    || die "api: api/.venv not found; create it with 'python3.12 -m venv api/.venv' and install api/requirements-dev.txt"
  version="$("$venv_python" -c 'import sys; print("%d.%d" % sys.version_info[:2])')" \
    || die "api: cannot run $venv_python"
  [ "$version" = "3.12" ] \
    || die "api: api/.venv uses Python $version, 3.12 is required; recreate it with 'python3.12 -m venv api/.venv'"
  cd api || die "cannot change to api"
  info "api: ruff check"
  .venv/bin/python -m ruff check . || die "api: ruff check failed"
  info "api: ruff format check"
  .venv/bin/python -m ruff format --check . || die "api: ruff format check failed"
  info "api: mypy strict"
  .venv/bin/python -m mypy || die "api: mypy failed"
  info "api: pytest"
  .venv/bin/python -m pytest || die "api: pytest failed"
  info "api: passed"
}

main() {
  [ "$#" -eq 1 ] || usage
  root="$(git rev-parse --show-toplevel)" || die "not inside a git repository"
  cd "$root" || die "cannot change to $root"
  case "$1" in
    web) gate_web ;;
    api) gate_api ;;
    *) usage ;;
  esac
}

main "$@"
