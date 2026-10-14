# 0035. Playoffs marks in core feeds

- Status: Accepted
- Date: 2026-10-14

## Context

Issue 225. The home cards, the game page header and the team page header show
that a game belongs to the play-in or the playoffs, where it sits in the
bracket and what is at stake, and the team header shows the titles the team won
in the current season. The data lives in the scoreboard (season type,
competition type, note and series object) and in the stored playoffs and Cup
feeds. ADR 0028 and ADR 0031 set the shape for a seasonal mark on core feeds
(the Cup mark). ADR 0032 says the scoreboard adapter and `ScoreboardGame` do not
change; that no longer holds for the mark.

## Decision

- **The `postseason` mark**: `games`, `game detail` and the games of the games
  feed gain `postseason: GamePostseason | null`, with `stage` (`playin`,
  `playoffs`, `finals`), `round` (1 to 4, null for the play-in), `conference`
  (null exactly for the Finals), `number` (1 to 7, null for the play-in),
  `summary` (the series summary, null when none and always for the play-in),
  `playIn` (set exactly for the play-in) and `stakes`.
- **Where the values come from**: the stage from the season type (5 play-in, 3
  series game, any other value no mark), the round from the competition type, the
  play-in conference and kind from the play-in note, the game number and the
  conference of rounds 1 to 3 from the note, the summary and wins from the series
  object.
- **Stakes** belong to the game and are the stakes it had at tip-off, from the
  series wins entering it. The rules apply in order and the first match wins:
  `game_7` for game number 7; `clinched` for a final game whose winner has 4 wins;
  `can_clinch` when one side has 3 entering wins and the other fewer;
  `elimination` when a side has 3 entering wins and the game is not the seventh
  (reachable only on inconsistent data); otherwise null. A final game's series
  object already counts the game, so the winner's entering wins are one fewer.
  In the play-in, `nine_ten` and `eighth_seed` are `elimination` and `seven_eight`
  has none.
- **The mark never fails a core feed.** A mark that cannot be read completely is
  null and the day is published as before.
- **Lenient reading.** The core games feed never fails because of postseason data.
  The scoreboard adapter captures the season type, competition type and series
  object as raw values. It reads them for the mark through lenient shapes, all
  optional and ignoring extra fields, and catches any validation or mapping error.
  An unreadable or inconsistent value, such as a malformed series, an unknown
  competitor id, a missing note or an unknown competition type, makes only that
  game's `postseason` null, logged by event id only. The event, its day and the
  games feed are unaffected. The note keeps the shape the Cup mark already parses.
- **Scoreboard function**: this supersedes ADR 0032's "Scoreboard function"
  bullet. The scoreboard adapter and `ScoreboardGame` change: the adapter builds
  the mark through the pure function in `api/app/sources/postseason_mark.py`, which
  also holds the note and round tables the playoffs feed reads, so both read a note
  the same way. `postseason_scoreboard.py` is not changed.
- `Conference` and `PlayInGameKind` move to `api/app/feeds/games.py`, as the Cup
  mark types did, so the mark can use them without a cycle. No exported schema
  changes by the move.
- **Team titles**: the team feed gains `titles`, a list of 1 to 3 `TeamTitle`
  (`nba_champions`, `nba_cup_champions`, `conference_champions`, in that order, no
  repeated kind) or null. The playoffs titles provider supplies the NBA title (the
  champion) and the conference titles (the `east-r3` and `west-r3` winners) from the
  stored playoffs feed. The Cup titles provider supplies the Cup title (the champion,
  with the year of the final's game) from the stored Cup feed. Each title shows only
  when the stored feed's season is the team feed's season. No feed is built and no
  source is read.
- **Team feed expiry**: the team feed also expires when the stored playoffs feed
  or the stored Cup feed was built after it, the test the finals feed and the Cup
  matchup feed use on the feed they read. Each provider has its own rebuilt check
  on the feed it reads. The player feed's expiry does not change.
- **Isolation in `/api`**: one titles provider per section. The Cup titles provider,
  `api/app/jobs/cup_titles.py`, is in the Cup section and the playoffs titles
  provider, `api/app/jobs/playoffs_titles.py`, is in the playoffs section. Each
  reads only its own section's stored feed. `TeamFeeds` receives a sequence of
  providers, each with a titles callable and a rebuilt check, wired in `main.py` one
  line per section. The core team feed merges their titles in title order, expires
  when any provider reports a rebuild, and imports neither section.
- **In `/web`**, the drawing follows ADR 0031: three nullable view fields
  (`postseasonMark` on the schedule game and the game header, `titles` on the team
  header), one mapping module (`postseason-mark-props.ts`) and the section's own
  components, rendered behind one condition each. This extends ADR 0031 and does not
  supersede it. `TournamentTag` draws only the three postseason stages: the Cup tag
  stays with `CupMarkTag`, because neither section imports the other (ADR 0034).
  The Cup title is drawn by the playoffs section's `TitleBadge` and `TeamTitles` from
  the core `titles` field with the key `playoffs_title_cup`, so it reads no Cup
  module or component.
- **Added strings and token**: four string keys beyond the plan's table.
  `playoffs_context_round_1`, `playoffs_context_round_2` and `playoffs_context_round_3`
  write the round of a series with its conference ("East round 1", "East semifinals",
  "East finals") in the context line, because one key with a round word would not
  translate the Spanish word order. `playoffs_context_game` ("Game {n}") is the
  context line of a Finals game whose series has no summary yet. The token
  `--playoffs-mark-gap` (6px) is the gap between the tag, the context line and the
  flag in the mark, and between the badges of the team titles, so no raw value
  repeats in the components.

## Consequences

- Removing the playoffs section also removes `postseason_mark.py`,
  `playoffs_titles.py` and its one wiring line in `main.py`, the `postseason` field
  and the playoffs titles (`nba_champions`, `conference_champions`) with their
  models, the postseason capture and lenient shapes in `scoreboard.py`, the mapping
  module, the five components and the three view fields with their lines.
- Removing the Cup section extends ADR 0028's removal list: it also removes
  `cup_titles.py` and its one wiring line in `main.py`, and nothing else in the team
  feed.
- The team feed is rebuilt after a rebuild of either stored feed, at the cost of one
  team build per requested team.
- A title shows only once the stored playoffs or Cup feed has been rebuilt after the
  deciding game, that is, after a request to `/playoffs` or `/cup`.
- The scoreboard holds two shapes for the postseason fields: the lenient one in
  `scoreboard.py` for the core mark, and the strict one in `postseason_scoreboard.py`,
  which still fails the playoffs build on bad data (ADR 0032). This is an owner
  decision; a test guards that the lenient shapes read the same field names.
