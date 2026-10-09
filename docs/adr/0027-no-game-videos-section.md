# 0027. No videos section on the game page

- Status: Accepted
- Date: 2026-10-09

## Context

Issue 199. The final game page had a Videos section that listed the data
source's related videos as links that opened the source's site in a new tab.
The source's terms of use do not allow using its content outside its own
products, and it offers no official embed player. The official league channel
uploads, for almost every game, only the full game highlights, which the
Highlights section already embeds. Other clips are rare, and their titles
cannot be tied to a game reliably. Stored game detail feeds built before the
change still carry `videos`.

## Decision

The game page shows no videos other than the highlights, and nobody leaves the
site to watch a video. The game detail feed has no `videos` field and no
`Video` type, and the adapter does not read the summary's videos.

A stored game detail feed that still has `videos` is ignored, not rebuilt:
`RETIRED_FIELDS` in `api/app/feeds/game_detail.py` drops the key when the feed
is read, and any other unknown field still fails. Rebuilding was rejected: a
final feed is built once and never again (ADR 0010), and a rebuild would ask
the source again and answer 503 if it failed.

## Consequences

- Highlights stay as they are.
- A served feed never has `videos`.
- Stored files that carry it are deleted by the cleanup when their game leaves
  the days shown, or replaced by a pre-game or live rebuild.
- Removing the `RETIRED_FIELDS` entry is a separate change.
- This rules out linking to the source's site for video.
