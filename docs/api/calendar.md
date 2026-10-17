# Calendar feed

The days with games of one season, for the date picker of the past dates.

## Schema

[`api/schemas/calendar.schema.json`](../../api/schemas/calendar.schema.json),
generated from the models in `api/app/feeds/calendar.py`. When this page and
the models disagree, the models win. The feed is decided in
[ADR 0040](../adr/0040-calendar-and-day-feeds.md); it is served at
`/feeds/seasons/{season}/calendar.json`, where `{season}` is the end year of
the season (2026 is the season 2025-26).

Conventions:

- Keys are camelCase.
- No unknown fields are accepted.
- Nullable fields are always present and `null` when absent.
- Times are UTC, as ISO 8601 with a timezone.
- Days are dates (`YYYY-MM-DD`) in the US Eastern calendar.

## Feed

| Field         | Type           | Meaning                                                                                                                  | Present |
| ------------- | -------------- | ------------------------------------------------------------------------------------------------------------------------ | ------- |
| `generatedAt` | datetime       | When the feed was built                                                                                                  | always  |
| `season`      | integer        | The end year of the season, 1994 or later                                                                                | always  |
| `seasonLabel` | season label   | Such as `1998-99`                                                                                                        | always  |
| `firstDay`    | date           | The first of `days`                                                                                                      | always  |
| `lastDay`     | date           | The last of `days`                                                                                                       | always  |
| `days`        | date[]         | The US Eastern days with games, sorted and unique; at least one                                                          | always  |
| `windowDays`  | date[]         | The days of the games feed stored at build time; may be stale on a kept calendar; empty when none was stored             | always  |
| `buildVersion` | integer / null | The rules version of a kept past calendar ([ADR 0055](../adr/0055-past-season-reading-rules-and-versioned-stored-data.md)) | null on a current calendar and on a stored feed from before the field |
| `seasons`     | `{season, seasonLabel}[]` | The current season down to 1994, newest first; set again at serve time ([ADR 0042](../adr/0042-calendar-seasons-and-day-season.md)) | always  |

A lockout season starts in February. A season played in July and August keeps
the gap between its days.

## Refresh

- The id is the season's end year; the feed is stored at
  `feeds/calendars/{season}.json`.
- Nothing is built without a request.
- The calendar is read from the scoreboard day of February 1 of the end year,
  through the source cache. The days are the US Eastern dates of its entries.
  An entry that is not a readable time is skipped and logged; a missing or
  empty calendar fails the build.
- Built on request under rule G of
  [`docs/source-rules.md`](../source-rules.md): the current season expires 24
  hours after the build. A past season built after its last day is kept while its `buildVersion` is the current one
  ([ADR 0055](../adr/0055-past-season-reading-rules-and-versioned-stored-data.md)). A
  calendar stored while its season was current is rebuilt after 24 hours until
  it is built after its last day.
- A failed build keeps the stored feed and is listed under `feeds` in
  `/health`; it is not retried for 10 minutes on request.
- The feed is never deleted.

## Endpoint

- `GET /feeds/seasons/{season}/calendar.json` serves the feed through the
  on-demand cache with `Cache-Control: public, max-age=10` and an `ETag`.
- `current` in place of the season answers the current season's calendar with
  the same body, `Cache-Control` and `ETag` as its end-year path, and 503 while
  the season is not known.
- It responds 304 with no body when `If-None-Match` matches the current `ETag`.
- It responds 404 with `{"detail": ...}`, with no source request, for a season
  that is not four digits, is before 1994 or is after the current season.
- It responds 503 while the current season is not known, after a failed read
  with nothing stored, and when the request's 20 seconds end before a missing
  feed is built.
- Every feed request records presence.
