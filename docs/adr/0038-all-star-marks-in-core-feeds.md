# 0038. All-Star marks in core feeds

- Status: Superseded by 0039 for its All-Star team test only, and by 0051 for final games without a line score only, and by 0064 for league events and live details that cannot be read only
- Date: 2026-10-14

## Context

Issue 233. The home cards, the game page header and the player page header show
that a game is the All-Star game, and its round, and that a player played in it.
ADR 0036 left the core adapters unchanged and noted that the core never stores a
final time for an All-Star game, because the scoreboard adapter requires a city
on every side and an All-Star team has none. ADR 0031 and ADR 0035 set the shape
for a seasonal mark on core feeds. The recorded All-Star day also has a scheduled
Championship whose two sides are placeholders (`TBD`), which read as guests would
get the same code and fail the games feed.

## Decision

- **The `allStar` mark** (`roundLabel`, `championship`) is added to `games` and
  `game detail`, and `allStarYear` to the player feed.
- **Detection**: season type 2 and competition type `ALLSTAR`, read leniently so
  the detection can never fail an event.
- **Sides**: an All-Star team is read as a guest (ADR 0025, ADR 0026) with a null
  city. `GameTeam.city` is nullable for a guest only; a league team still
  requires one.
- **A placeholder side skips its game**: a game with a side that is not an
  All-Star team is skipped until its teams are known, as ADR 0026 skips a game
  with a side that is not a team.
- **An All-Star event that cannot be mapped or validated is skipped with a log
  line**, in the scoreboard adapter and in the games job (its live detail, its
  game rules); it never fails the day or the games feed, while a league game keeps
  failing them as before; every All-Star game the adapter returns carries its
  mark, which is how the games job recognizes it.
- **The round label** is shown as the feed sends it, except "Championship", which is a translated string ("Campeonato" in Spanish), as on the `/all-star` page.
- **`api/app/sources/all_star_mark.py`** holds the mark function, the detection
  and the note parsing the All-Star feed now imports, as ADR 0035 did for the
  playoffs note tables.
- **The player feed** carries the year of the All-Star game in the season's game
  log. The game is already out of the last five games and out of the hero.
- **Drawing in `/web`** follows ADR 0031: the `allStarMark` and `allStarTag` view
  fields, `all-star-mark-props.ts` and `AllStarTag`, which imports neither the Cup
  nor the playoffs section. The string `allstar_stage_tag` and the token
  `--allstar-mark-gap` are added.
- **Partial supersede of ADR 0036**: its bullet "Two views, core adapters
  unchanged" and its sentence "The core never stores a final time for an All-Star
  game" no longer hold.

## Consequences

- The games job now stores final times for All-Star games, fetches their final
  detail and highlights, and shares the cached responses with the All-Star feed.
- On an All-Star day whose live or final games come without line scores or
  clocks, those games are left out of the core feed and only the All-Star page
  shows them.
- Removing the section also removes `all_star_mark.py`, the `is_all_star` field,
  the detection, the placeholder skip and the All-Star skip in `scoreboard.py`,
  the two All-Star branches in `api/app/jobs/games.py`, the `allStar` and
  `allStarYear` fields, the mapping module, `AllStarTag`, the three view fields
  with their lines, the string and the token. Guests without a city stay allowed.
- The constants in `all_star_scoreboard.py` (`REGULAR_SEASON`, `COMPETITION_TYPE`)
  duplicate the detection values, and the import cycle prevents sharing them.
- An All-Star team code equal to a league code makes that game skipped with a
  log line, and no longer fails the day.
