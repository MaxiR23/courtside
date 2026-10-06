# 0015. Highlights source

- Status: Accepted
- Date: 2026-10-06

## Context
ADR 0007 reads the league's official video channel through its public feed,
which holds only the latest uploads. A game that ended while the backend was
down could have its video rotate out of that feed before its attempts ran,
and never get its highlights. Raised in #80.

## Decision
- The channel's uploads are listed through the official video API, newest
  first, 50 per request.
- The lookup takes one game: it pages back until it finds the game's video
  or reaches a page with a video published before the game's start, so the
  job never pages past the oldest game in the days shown.
- The API key is read from `HIGHLIGHTS_SOURCE_KEY` through `Settings`, sent
  in a request header and never written to logs, errors or the repository.
- Matching, attempts and storage do not change.

## Consequences
- Refines the "Highlights" of ADR 0007 without superseding it as a whole.
  ADR 0007 is not edited.
- Every lookup costs one request per page it reads.
- A future on-demand lookup can call the same lookup with one game.
- `VIDEO_CHANNEL_FEED_URL` is removed; an `.env` that still sets it fails
  validation until the line is deleted.
