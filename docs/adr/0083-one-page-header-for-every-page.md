# 0083. One page header for every page

- Status: Accepted
- Date: 2026-10-29

## Context

Ten page headers (the home hero, standings, team, player, day, game, playoffs,
the Cup, the All-Star and the series page) each padded, drew the grid
background, set the content width and placed the season selector on their own.
The result drifted: the nav row sat 40px from the top on the home, 14px on
most pages and 0 on the series page, the first line sat 36px, 48px or 137 to
176px below it, and the desktop selector had a row of its own above the
content instead of sitting with the title.

## Decision

- One component, `PageHeader`, owns the grid background, the content width and
  side padding, the nav row, the season selector and the vertical spacing of
  every page header. Pages pass their first line, body, right column and
  full-width rows as snippets, and their layout values (grid size, gaps, side
  padding, flex values, the sticky nav) as token references. Pages never reach
  into it with `:global`.
- The nav row's top is `--identity-hero-pad-top` on every page.
- The first line sits `--header-first-line-offset` (24px) below the nav row on
  desktop and `--header-first-line-offset-mobile` under 680px. The home hero
  has no first line: its copy stays centered.
- On desktop the season selector sits on the first line, at the right edge of
  the content. A right column starts below it and never overlaps it. On mobile
  the selector is full width under the header.
- The All-Star sticky nav and the champion band (the playoffs hero, whose grid
  and divider wrap its rows) are options of `PageHeader`, not copies.
- Only `PageContainer` and `PageHeader` set the content width, only
  `PageHeader` imports `NavRow`, only `PageHeader` and `CalendarSheet` import
  `SeasonSelect`, and only `PageHeader` draws the header grid. Guard tests
  enforce it.

## Consequences

- The Cup's 300px minimum height and the champion hero's 1440px box are
  retired, with the tokens only they used.
- The series page gains the header spacing: its nav moves to the common top
  and its back link becomes the first line.
- A new page header goes through `PageHeader`.
- `/preview` passes a season select to the pages that have one, so the
  selector's position can be measured.
