# Source rules

The rules every job and feed build follows so the data source is asked as little as possible. They are adopted by ADR 0020 and apply to every feed: games, game detail, player and team. Rule L records the season fallbacks of the adapters; it is adopted by ADR 0022. Rule N is adopted by ADR 0056 and retired by ADR 0059, and Rule O is adopted by ADR 0058 and extended by ADR 0059, and rule P is adopted by ADR 0062, which also extends rule H.

References:

- RFC 5861: `stale-while-revalidate` (serve stale and revalidate in the background, triggered by a request) and `stale-if-error` (serve the last stored response when revalidation fails).
- Python 3.14 `asyncio`: keep a strong reference to every created task; `asyncio.wait_for` cancels the awaited task on timeout unless it is wrapped in `asyncio.shield`; `asyncio.Semaphore` with `async with`; asyncio primitives are not thread-safe, and everything here runs in the event loop.
- RFC 6585: status 429 (too many requests) is the rate limit answer.
- RFC 9110, 15.6.4: status 503 is a temporary overload, the equivalent answer.
- Cloudflare's Origin Cache Control documentation: `s-maxage` disables `stale-while-revalidate`, and "Always Online" ignores it.

## A. One shared source cache

Every source response is stored once, by URL, with its fetch time, and reused by every job and every build until it expires. Nothing fetches a URL that is fresh. Expiry by kind:

| Kind | Fresh for |
|---|---|
| Scoreboard day, live game detail | 30 seconds |
| League standings, league injuries | 1 hour |
| Roster, team leaders, depth chart | 24 hours |
| A player's individual averages | Until the player's team has a final game after the fetch |
| Everything else | 1 hour |

## B. Presence

The backend records the time of the last feed request. Someone is present while that time is under 5 minutes ago.

## C. Live games

While any game of the days shown is live:

- With someone present, the scoreboard day and the detail of every live game are refreshed every 30 seconds.
- With nobody present, every 2 minutes.
- A game still scheduled past its start is checked every minute with someone present, and every 2 minutes with nobody present ([ADR 0065](adr/0065-background-work-limited-to-games-highlights-and-stars.md)).
- A feed request that finds its data older than 30 seconds during a live game triggers the refresh immediately, so a visitor never sees a score older than 30 seconds.
- With no live game the live refresh stops, and it resumes at the start time of the next game of the day.

## D. Final games

A final game's detail is built once, on its first request after its final time, reading the summary of the latest ADR 0010 attempt time passed ([ADR 0065](adr/0065-background-work-limited-to-games-highlights-and-stars.md)), and never again. After the fourth failed attempt it is built once with the summary sections null ([ADR 0064](adr/0064-degrade-one-bad-item-instead-of-failing-a-feed.md)). Its stars, highlights and highlights search URL are added when it is served, not stored in it.

## E. Fixed-time work

Unchanged cadences: the daily scoreboard fetch of the days shown at `DAILY_FETCH_TIME`, the stars once a day, and the highlight attempts at their times. The highlights job lists the channel uploads once per run and matches every due game against that one list. Past highlights and the All-Star edition video are found by one on-demand search of the channel by query, started when a feed is served without one, at most `HIGHLIGHTS_SEARCH_DAILY_CAP` searches per US Eastern day, never repeated for a target that was searched and found none ([ADR 0065](adr/0065-background-work-limited-to-games-highlights-and-stars.md)).

## F. Stars

The roster and leaders are fetched once a day per team. A player's individual averages are fetched only when needed and then kept per rule A, so a team with no leader on its roster costs at most one request per player per game played, never per day. The daily mark is the job's own last success, so a restart on a day already fetched does not fetch again; at most 4 source reads are in flight, and a failed team is retried 5 minutes after it failed, one failed team per run ([ADR 0065](adr/0065-background-work-limited-to-games-highlights-and-stars.md)). Every star guarantee of ADR 0014 stays.

## G. On demand

Everything else is built on request only: pre-game game detail, team feeds, player feeds, the standings feed, the search feed, the Cup feed, the Cup matchup feeds, the playoffs feed, the playoffs finals feed, the All-Star feed, the calendar feed, the day feed, the past game detail, and the standings, team and player feeds of a past season, and the Cup and Cup matchup feeds of a past season, and the playoffs and playoffs finals feeds of a past season, and the All-Star feed of a past season. A feed nobody requests is never built, stored or fetched. A stored feed expires:

| Feed | Expires |
|---|---|
| Pre-game game detail, tip-off more than 48 hours away | 12 hours after the build |
| Pre-game game detail, tip-off between 48 and 12 hours away | 6 hours after the build |
| Pre-game game detail, tip-off under 12 hours away or passed | 3 hours after the build |
| Team feed | When the team has a final game whose final time plus 1 hour is after the build, when the stored playoffs feed or the stored Cup feed is rebuilt after the build, and in any case 7 days after the build. Its franchise names are built once per team and kept while `SEASON_BUILD_VERSION` holds, their current season read again 24 hours after the last read (ADR 0065); a team feed is stale while its stored names are of another version |
| Player feed | When the team has a final game whose final time plus 1 hour is after the build, and in any case 7 days after the build; a player on no roster: 7 days after the build. The season codes of its career rows are set when served from the stored franchise names; none is built by the player feed (ADR 0065) |
| Standings feed | When any game of the league has a final time plus 1 hour after the build, and in any case 7 days after the build |
| Search feed | When any game of the league has a final time plus 1 hour after the build, when the stars job fetches a roster after the build, and in any case 7 days after the build |
| Cup feed | When any Cup game has a final time plus 1 hour after the build, and in any case 7 days after the build; once the championship is final, kept while its season is the current one |
| Cup matchup feed | When either of its teams has a final game whose final time plus 1 hour is after the build, when the Cup feed it read is rebuilt, and in any case 7 days after the build |
| Playoffs feed | When any postseason game (a game of the feed, or a final game dated inside its postseason dates) has a final time plus 1 hour after the build; while its state is picture, also when any game of the league has a final time plus 1 hour after the build; at the start of the play-in window when the build precedes it; and in any case 7 days after the build; once the Finals series is complete, kept while its season is the current one |
| Playoffs finals feed | When any postseason game (a game of the playoffs feed it read, or a final game dated inside its postseason dates) has a final time plus 1 hour after the build, when the playoffs feed it read is rebuilt, and in any case 7 days after the build; once the Finals series is complete, kept while its season is the current one |
| All-Star feed | While its state is live or its edition's date is today (US Eastern), 30 seconds after the build (rule C), and a request that finds it stale waits for the rebuild; before the edition, 24 hours after the build (ADR 0065); once every game of the edition is final, kept while its season is the current one, but only when built at least 1 hour after the latest time the feed first saw one of its games final (before that, 30 seconds after the build) |
| Calendar feed | Current season: 24 hours after the build. A past season built after its last day: kept while its `buildVersion` is the current one |
| Day feed | Every game final, or no game: kept. A non-final game: 6 hours after the build |
| Past game detail (a final game of a stored day feed) | Kept: built once (rule D) |
| Standings, team and player feed of a past season | Kept: built once (rebuilt only when its `buildVersion` is not the current one, ADR 0053). The season codes of a past player's career rows are set when served |
| Cup and Cup matchup feed of a past season | Kept: built once. The current season's path serves the current Cup and Cup matchup feeds, with their expiry |
| Playoffs and playoffs finals feed of a past season | Kept: built once. The current season's path serves the current playoffs and playoffs finals feeds, with their expiry |
| All-Star feed of a past season | Kept: built once. The current season's path serves the current All-Star feed, with its expiry |

## H. Serving

- Fresh: served from storage.
- Stale: served from storage at once and rebuilt in the background (`stale-while-revalidate`).
- Missing: built while the request waits up to 20 seconds. The build is shielded, so it finishes and is stored even if the request stops waiting. After 20 seconds the endpoint answers 503 and the front end shows its unavailable state and keeps polling.
- One build per feed at a time: concurrent requests await the same build (a dict of in-flight tasks whose entries are removed when done).
- At most 4 builds run at once (`asyncio.Semaphore`).
- At most 16 builds are started (running, waiting for a slot or for a dependency) at once. A missing feed requested at the cap answers 503 and starts nothing; a stale one is served from storage with no build; a refresh, a warm-up and a dependency start nothing (a dependency is used as stored) (ADR 0062).
- A build runs at most 60 seconds; a build past it is cancelled and recorded as a failure with the reason 'build timed out' (ADR 0062).
- A failed build keeps the stored feed (`stale-if-error`), is recorded in `/health`, and that feed is not rebuilt for 10 minutes.

## I. Unknown ids

Unknown ids answer 404 with no source request: game ids outside the days shown that are not a final game of a stored day feed, player ids neither in the rosters the stars job fetches, nor in the roster of a stored past team season feed, nor in the box score of a stored past game detail, codes outside the 30 standard codes, slot ids outside the 7 of the Cup bracket, on the current and the season matchup paths, calendar seasons that are neither `current` nor a four-digit end year from 1994 to the current season, days that are not a `YYYY-MM-DD` date, are before 1993-10-01, are after today (US Eastern), or are a day of the stored games feed (with none stored, a day the games job would show), season paths of the standings, team and player feeds that are not a four-digit end year from 1994 to the season before the current one, season paths of the Cup and Cup matchup feeds that are not a four-digit end year from 2024 to the current season (the current season serves the current Cup feeds), season paths of the playoffs and playoffs finals feeds that are not a four-digit end year from 1994 to the current season (the current season serves the current playoffs feeds), season paths of the All-Star feed that are not a four-digit end year from 1994 to the current season (the current season serves the current All-Star feed), a past All-Star season whose edition was not found (after one scan of the February days of its calendar, until a restart), and a team code whose franchise has no team that season (after one read of its season team object). While the rosters are not fetched yet, player requests answer 503. On the season player path, a player named by a stored past playoffs or Finals feed (its leaders, award winners, Finals MVP and averages) is also known, and an id known from stored past data never waits for the rosters (ADR 0059). While the current season is not known, calendar requests, `current` included, and season feed requests answer 503.

## J. Restart and cleanup

Stored feeds, source cache entries and build times survive a restart; a restart builds nothing by itself. A cleanup with no source request deletes the stored data of games that left the days shown and of players no longer on any roster. With the games job's daily fetch, a kept past feed (day, past game detail, calendar, and the past team, player, playoffs, Finals, Cup, Cup matchup and All-Star feeds) not served in 90 days is deleted and built again on its next request (ADR 0063).

## K. Cache headers

Feed responses keep `Cache-Control: public, max-age=10` and the ETag. The CDN in front of the API must honor the origin's Cache-Control, must not add `s-maxage`, and must keep "Always Online" off.

## L. Previous season

A source read for the current season that has no regular season data is read once more for the regular season it has. The season leaders and averages fall back to the previous season when the current one has none (the team feed's leaders and the stars job). The division standings, when the response is not of the regular season, are requested once more with the `season` query value: a preseason response of season `Y` reads `Y - 1`, a postseason response of season `Y` reads `Y`. That request is cached under its own URL (rule A), and a fallback that is not of the regular season fails the read.

## M. Missing stats

A missing stat is null, never a failure. A team or player stat the source does not carry is null in the feed, in every adapter; the page hides it. A stat is a counted or rated value of a team's or a player's performance (box score columns, team statistics, leader values); the fields that identify a record (ids, codes, a standings row's record and seed, the Cup table's wins and losses) are not stats. A value that is sent and is not a number still fails the read. A box score row with no player id is skipped and logged once per game read, in every reader (ADR 0055).

## N. Paced past builds

Retired by ADR 0059: no build paces its reads; every past build follows rule O.

## O. Budgeted past builds

- Each past playoffs, Finals, Cup, Cup matchup, All-Star, team, player, day, game detail and standings build declares the most source reads it sends: 63, 11, 44, 2, 60, 5, 4, 1, 1 and 1 (ADR 0059). A read is a request that reaches the network through the shared client; a cache hit, and a caller that joins an in-flight request, are not reads.
- A build that would pass its budget stops before that read, logs the reason and stores nothing.
- At most four reads of a build are in flight at once, with no pause between them.
- A 429 or 503 answer stops the build, logged and recorded with the reason "rate limited", and the feed is retried after 10 minutes (rule H).

See [`adr/0058-bounded-past-competition-reads.md`](adr/0058-bounded-past-competition-reads.md) and [`adr/0059-bounded-past-page-reads.md`](adr/0059-bounded-past-page-reads.md).

## P. Source protection

- At most 8 requests of the shared client are in flight at once, budgeted or not; a build's budget slot is taken before the client slot.
- A 429 or 503 answer pauses every request of the client until its `Retry-After` (seconds or HTTP date), 60 seconds when it is missing or unreadable, at most 15 minutes. A paused read raises "source paused" without a request, a fresh cache entry is still served, the start is logged once without the URL, and a later 429 or 503 only extends it.
- A paused read stops a budgeted build as "rate limited" (rule O). It is a failed request.

See [`adr/0062-bounded-upstream-reads-and-on-demand-builds.md`](adr/0062-bounded-upstream-reads-and-on-demand-builds.md).
