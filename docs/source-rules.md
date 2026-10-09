# Source rules

The rules every job and feed build follows so the data source is asked as little as possible. They are adopted by ADR 0020 and apply to every feed: games, game detail, player and team. Rule L records the season fallbacks of the adapters; it is adopted by ADR 0022.

References:

- RFC 5861: `stale-while-revalidate` (serve stale and revalidate in the background, triggered by a request) and `stale-if-error` (serve the last stored response when revalidation fails).
- Python 3.14 `asyncio`: keep a strong reference to every created task; `asyncio.wait_for` cancels the awaited task on timeout unless it is wrapped in `asyncio.shield`; `asyncio.Semaphore` with `async with`; asyncio primitives are not thread-safe, and everything here runs in the event loop.
- Cloudflare's Origin Cache Control documentation: `s-maxage` disables `stale-while-revalidate`, and "Always Online" ignores it.

## A. One shared source cache

Every source response is stored once, by URL, with its fetch time, and reused by every job and every build until it expires. Nothing fetches a URL that is fresh. Expiry by kind:

| Kind | Fresh for |
|---|---|
| Scoreboard day, live game detail | 30 seconds |
| League standings, league injuries | 1 hour |
| Roster, team leaders | 24 hours |
| A player's individual averages | Until the player's team has a final game after the fetch |
| Everything else | 1 hour |

## B. Presence

The backend records the time of the last feed request. Someone is present while that time is under 5 minutes ago.

## C. Live games

While any game of the days shown is live:

- With someone present, the scoreboard day and the detail of every live game are refreshed every 30 seconds.
- With nobody present, every 2 minutes.
- A feed request that finds its data older than 30 seconds during a live game triggers the refresh immediately, so a visitor never sees a score older than 30 seconds.
- With no live game the live refresh stops, and it resumes at the start time of the next game of the day.

## D. Final games

A final game's detail is built once, at its final time with the ADR 0010 attempts, and never again. Its stars, highlights and highlights search URL are added when it is served, not stored in it.

## E. Fixed-time work

Unchanged cadences: the daily scoreboard fetch of the days shown at `DAILY_FETCH_TIME`, the stars once a day, and the highlight attempts at their times. The highlights job lists the channel uploads once per run and matches every due game against that one list.

## F. Stars

The roster and leaders are fetched once a day per team. A player's individual averages are fetched only when needed and then kept per rule A, so a team with no leader on its roster costs at most one request per player per game played, never per day. Every star guarantee of ADR 0014 stays.

## G. On demand

Everything else is built on request only: pre-game game detail, team feeds, player feeds, the standings feed and the search feed. A feed nobody requests is never built, stored or fetched. A stored feed expires:

| Feed | Expires |
|---|---|
| Pre-game game detail, tip-off more than 48 hours away | 12 hours after the build |
| Pre-game game detail, tip-off between 48 and 12 hours away | 6 hours after the build |
| Pre-game game detail, tip-off under 12 hours away or passed | 3 hours after the build |
| Team feed, player feed | When the team has a final game whose final time plus 1 hour is after the build, and in any case 7 days after the build |
| Standings feed | When any game of the league has a final time plus 1 hour after the build, and in any case 7 days after the build |
| Search feed | When any game of the league has a final time plus 1 hour after the build, when the stars job fetches a roster after the build, and in any case 7 days after the build |

## H. Serving

- Fresh: served from storage.
- Stale: served from storage at once and rebuilt in the background (`stale-while-revalidate`).
- Missing: built while the request waits up to 20 seconds. The build is shielded, so it finishes and is stored even if the request stops waiting. After 20 seconds the endpoint answers 503 and the front end shows its unavailable state and keeps polling.
- One build per feed at a time: concurrent requests await the same build (a dict of in-flight tasks whose entries are removed when done).
- At most 4 builds run at once (`asyncio.Semaphore`).
- A failed build keeps the stored feed (`stale-if-error`), is recorded in `/health`, and that feed is not rebuilt for 10 minutes.

## I. Unknown ids

Unknown ids answer 404 with no source request: game ids outside the days shown, player ids not in the rosters the stars job fetches, codes outside the 30 standard codes. While the rosters are not fetched yet, player requests answer 503.

## J. Restart and cleanup

Stored feeds, source cache entries and build times survive a restart; a restart builds nothing by itself. A cleanup with no source request deletes the stored data of games that left the days shown and of players no longer on any roster.

## K. Cache headers

Feed responses keep `Cache-Control: public, max-age=10` and the ETag. The CDN in front of the API must honor the origin's Cache-Control, must not add `s-maxage`, and must keep "Always Online" off.

## L. Previous season

A source read for the current season that has no regular season data is read once more for the regular season it has. The season leaders and averages fall back to the previous season when the current one has none (the team feed's leaders and the stars job). The division standings, when the response is not of the regular season, are requested once more with the `season` query value: a preseason response of season `Y` reads `Y - 1`, a postseason response of season `Y` reads `Y`. That request is cached under its own URL (rule A), and a fallback that is not of the regular season fails the read.
