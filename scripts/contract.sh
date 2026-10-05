#!/usr/bin/env bash
# INFO: Regenerates the feed contract: the JSON Schema from the Pydantic models, then the
#       TypeScript types from the schema.
# REQUIRES: bash 3.2 or newer and BSD or GNU tools.
# STEPS:
#   1. Require api/.venv and web/node_modules.
#   2. Export the JSON Schema: cd api && .venv/bin/python -m app.feeds.schema
#   3. Generate the types: cd web && pnpm run contract

set -eu

die() {
  printf 'contract: %s\n' "$*" >&2
  exit 1
}

info() {
  printf 'contract: %s\n' "$*"
}

main() {
  root="$(git rev-parse --show-toplevel)" || die "not inside a git repository"
  cd "$root" || die "cannot change to $root"
  [ -x api/.venv/bin/python ] \
    || die "api: api/.venv not found; create it with 'python3.12 -m venv api/.venv' and install api/requirements-dev.txt"
  command -v pnpm >/dev/null 2>&1 \
    || die "web: pnpm not found; install pnpm and run 'pnpm install' in web/"
  [ -d web/node_modules ] \
    || die "web: web/node_modules not found; run 'cd web && pnpm install'"
  info "exporting the JSON Schema"
  (cd api && .venv/bin/python -m app.feeds.schema) || die "schema export failed"
  info "generating the TypeScript types"
  (cd web && pnpm run contract) || die "type generation failed"
  info "done"
}

main "$@"
