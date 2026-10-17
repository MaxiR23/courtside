# Day feed

The games of one past day, in the shape of the games feed.

## Schema

[`api/schemas/days.schema.json`](../../api/schemas/days.schema.json),
generated from the models in `api/app/feeds/days.py`. When this page and the
models disagree, the models win. The feed is decided in
[ADR 0040](../adr/0040-calendar-and-day-feeds.md); it is served at
`/feeds/days/{date}.json`, where `{date}` is a `YYYY-MM-DD` date.

Conventions:

- Keys are camelCase.
- No unknown fields are accepted.
- Nullable fields are always present and `null` when absent.
- Times are UTC, as ISO 8601 with a timezone.

## Feed

| Field         | Type      | Meaning                                                                          | Present |
| ------------- | --------- | -------------------------------------------------------------------------------- | ------- |
| `generatedAt` | datetime  | When the feed was built                                                          | always  |
| `season`      | integer   | The end year of the day's season, as the scoreboard response gives it            | always  |
| `seasonLabel` | season label | Such as `1998-99`                                                             | always  |
| `day`         | `PastDay` | The requested US Eastern day: `date` and `games`                                 | always  |
| `buildVersion` | integer / null | The rules version of a kept day ([ADR 0053](../adr/0053-season-level-rules-for-past-seasons.md)) | null on a stored feed from before the field |

The league sides of a day are named by the day's season team object (name and city), with today's code; a guest side keeps its name ([ADR 0053](../adr/0053-season-level-rules-for-past-seasons.md)). A day with every game final is rebuilt on its next request when its `buildVersion` is not the current one.

`games` holds `PastGame` objects in the provider's order. `PastGame` and
`PastDay` have the schema of `Game` and `Day` of [`games.md`](games.md), apart
from their names, so a day of this feed is valid against the games feed's
`Game` schema. The rules of a past game:

- **Stars**: null on both sides. The games feed's rule "null exactly on a
  guest side" applies to the games feed only.
- **Highlights**: the stored highlight of a final game, added when served
  and never stored ([ADR 0048](../adr/0048-highlights-backfill-and-edition-video.md)); empty otherwise and on an All-Star game.
  `highlightsSearchUrl` is set on a final game, as in the games feed.
- **Stats**: on a final game `statsAvailability` is `available` and `leaders`
  and `teamStats` are null: they are read from its game detail
  ([ADR 0054](../adr/0054-historical-sides-and-past-pages.md)). On any other game all three are null.
- **Sides**: resolved by team id first, with the event's name and city; a side
  whose id is not one of the 30 follows the guest rule (ADR 0025, ADR 0026).
- **Marks**: the Cup, postseason and All-Star marks are read case-insensitively.
  A game without a readable mark has none, and the mark never fails the day.
- **Skipped games**: a game that cannot be mapped or is not valid is left out
  and logged by event id; the other games of the day are published.
- **Empty day**: `games` is `[]`.

## Refresh

- The id is the date; the feed is stored at `feeds/days/{date}.json`.
- Nothing is built without a request.
- The day is read from the scoreboard day of that date through the scoreboard
  adapter, with a 30-second source freshness.
- Built on request under rule G of
  [`docs/source-rules.md`](../source-rules.md): a day whose games are all final,
  or with no game, is kept. A day with any game that is not final expires 6
  hours after the build.
- A scoreboard response without a readable season fails the build
  ([ADR 0042](../adr/0042-calendar-seasons-and-day-season.md)).
- A failed build keeps the stored feed and is listed under `feeds` in
  `/health`; it is not retried for 10 minutes on request.
- The feed is never deleted, and its games never enter the games job, the hero,
  the highlights job or the live refresh. The highlights backfill reads the
  stored day feeds once a day to find the highlights of their final games.

## Endpoint

- `GET /feeds/days/{date}.json` serves the feed through the on-demand cache
  with `Cache-Control: public, max-age=10` and an `ETag`.
- It responds 304 with no body when `If-None-Match` matches the current `ETag`.
- It responds 404 with `{"detail": ...}`, with no source request, for an id that
  is not a `YYYY-MM-DD` date, a date before 1993-10-01, a date after today (US
  Eastern) and a day of the stored games feed (with none stored, a day the
  games job would show).
- It responds 503 after a failed read with nothing stored, and when the
  request's 20 seconds end before a missing feed is built.
- Every feed request records presence.
