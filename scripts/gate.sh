#!/usr/bin/env bash
# INFO: Runs the gate of one app. The only place the gate commands are written:
#       CLAUDE.md, scripts/ship.sh and CI call this script and never repeat its commands.
# REQUIRES: bash 3.2 or newer and BSD or GNU tools. Local git hooks call it on macOS,
#           so it must not use bash 4 features or GNU-only flags.
# STEPS:
#   web
#     1. Run the gate of /web from the repository root.
#   api
#     1. Run the gate of /api from the repository root.
#
# Both gates are pending until their app is scaffolded: until then each one
# reports that it is pending and exits successfully.

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
  # PENDING: the /api gate commands are written here when /api is scaffolded.
  info "api: pending, /api is not scaffolded yet; no checks run"
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
