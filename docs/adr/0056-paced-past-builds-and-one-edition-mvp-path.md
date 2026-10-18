# 0056. Paced past builds and one edition MVP path

- Status: Superseded by 0058 for the past playoffs and Finals reads only, and by 0059 for the paced past team and player reads and `SOURCE_BUILD_PAUSE_MS` only
- Date: 2026-10-17

## Context

Issue 275. The cold build of the past playoffs read about 1,300 game summaries
(ADR 0053), up to 8 at once, and the source rate-limited the API for about 45
minutes afterwards. The audit also found that the recap of the current All-Star
feed (the previous edition) could carry no MVP, or another one, while the
edition's own season feed had one (finding 31). The cause the code allows: the
current feed read the previous edition's awards, sections and extras through a
guard that turned any failure, a rate-limited read included, into a null part
kept until the next daily rebuild, while the season feed fails the build on
anything but a 404. Finding 32 (no edition video for the 2025 edition) is not
an API defect, see Decision.

## Decision

- **Game detail reads of the past rosters go one at a time.** `SeasonRosters`
  (the past team, player, playoffs and Finals rosters) holds one lock for
  every build, and waits `SOURCE_BUILD_PAUSE_MS` (default 250, a non-negative
  integer) from the end of one request to the start of the next. The first read
  after an idle time longer than the pause does not wait. Stored past game
  players and stored past game details are reused with no request and no pause.
  The past Cup reads no game detail, and the Finals' own up to 7 summaries and
  the season All-Star summaries are not paced.
- **A rate limit stops the build.** A 429 (RFC 6585) answer stops the read with
  the reason "rate limited". 503 (RFC 9110, 15.6.4, a temporary overload) is the
  equivalent response and is treated the same; no other status is a rate limit.
  The warning `season rosters: game <id> read rate limited (status <code>), game
  reads held for 10 minutes` is logged, and `FeedCache` records the reason
  "rate limited" for the feed.
- **The hold.** After a rate limit every paced read, in every build, raises
  "rate limited" with no request for 10 minutes (`RETRY_AFTER`, the retry window
  of rule H). This is needed because the roster and playoffs builds read with
  `asyncio.gather`, which does not cancel the sibling reads of a failed one.
  Games read before the limit are stored, so the retry resumes where it
  stopped.
- **One MVP path for a finished edition.** The inputs of an edition's MVP are
  the season awards (the winner), the sections (the box rows his name and lines
  come from) and the extras (his jersey). `read_edition_mvp_inputs` reads them
  with a 24-hour freshness: a 404 nulls its part and any other failure raises
  `SourceError`. The season feed uses it for its own edition and for its
  previous edition, and the current feed uses it for its previous edition. The
  MVP is built by the existing `mvp` in both. Every other read of the current
  feed's previous edition (the day, the details, the team infos) behaves as
  before, and its league teams, the MVP's included, come from today's rosters.
- **Transient failure of an MVP input on the current feed.** If the stored
  current feed has `previous.year == season - 1` and a non-null `previous.mvp`,
  the new build keeps its stored `previous` and `previousEdition` and logs
  `all-star: previous edition of season <year> kept from the stored feed:
  <reason>`; the rest of the feed is rebuilt normally. Otherwise the build
  raises the `SourceError`, the stored feed is served and the build is retried
  after 10 minutes. Carry-forward comes first because a live or on-the-day feed
  is rebuilt every 30 seconds (ADR 0036), and a failed build would freeze its
  scores for up to 10 minutes because of a read of last year's edition.
- **Same MVP** means the same player (`playerId`), `name`, `photoUrl`, `jersey`,
  `lines` and `totals`. `leagueTeam` is left out: the current feed fills it from
  today's rosters and the season feed leaves it null (ADR 0047).
- **Finding 32.** The edition video is added only for an edition with a stored
  `all_star_editions` row, whose window end has passed, and that a backfill
  sweep has covered with a matching upload (ADR 0048). The 2025 row is stored
  when its season feed is first built, so it waits for a sweep after that and
  for the sweep it joins. This is the rule of ADR 0048, not an API defect, and
  no code changes. The stored state was not available to the issue.

## Consequences

- A cold past playoffs build of about 1,300 summaries takes at least about 5.5
  minutes at 250 ms. Team and player builds queue behind it on the same lock
  while holding one of the 4 build slots of rule H, so their requests answer 503
  until each feed is stored.
- A real outage that answers 503 holds the paced reads for 10 minutes too.
- The current feed's previous edition keeps its league teams from today's
  rosters, so its MVP can differ from the edition feed's only in `leagueTeam`.
- A transient failure of an MVP input with no stored previous MVP fails the
  current feed's build: the stored feed is served and the build is retried
  after 10 minutes, which also delays live scores in that case. It needs an MVP
  input failure, an expired 24-hour source cache and no stored previous MVP
  (for example, the first build after a deploy that replaced a feed whose recap
  MVP was null).
- No feed model changes, no generated type changes and no `SEASON_BUILD_VERSION`
  change.
- This replaces ADR 0053's "at most `MAX_GAME_READS` at once" for every past
  roster read. For the inputs of the previous edition's MVP only, it replaces
  ADR 0036's "the awards [...] only nulls its part"; ADR 0036's league-team rule
  stays in force.
