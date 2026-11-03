# News design

The News pages and the notes that appear across the site. Colors, type, spacing and motion follow `docs/design.md`; copy is in both message files. The feeds are specified in `docs/api/news.md` and the decisions in ADR 0086.

## Places

1. The home carousel, after Standings and Leaders.
2. The News page, `/news`.
3. The note page, `/news/{id}`.
4. The News section of the team page and of the player page.
5. The Recap section of a final game page.

Every news block is absent when its feed has no URL, answers 404, fails or holds no notes: no tab, no section, no link. While a block loads it shows card-shaped bones with the home's shimmer (stopped under reduced motion), and no tab. The news request never delays the page it sits on.

## The note card

`NewsCard` is the only place a note is drawn. The whole card is one link to `/news/{id}`, with no nested link and no target. Layouts:

- **card**: photo on top (16:9), tags, the headline in Barlow Condensed uppercase (23px) and a 3-line description, in a `BlueprintFrame`.
- **row**: a 160px thumbnail on the left, the tags without the date, the headline and a 2-line description; the date on the right; a hairline divider between rows.
- **feature**: photo on the left half, text on the right half, the headline `clamp(34px, 3vw, 38px)`. On mobile (under 680px) the photo sits above the text, because half a phone leaves no room for a 34px headline.

A note with no photo, or whose photo fails to load, is drawn as text only in every layout. The headline is an `h3`.

Tags (`NewsTags`): the kind, accent for a recap ("Recap" / "Crónica") and muted for news; the first team code of the note, uppercase; `EN` when the note is in English and the page is in Spanish; then the date.

## Dates

- Under 24 hours old: hours, at least 1: "16 h ago" / "hace 16 h". A time later than now shows 1 h.
- Otherwise the day and the short month in the viewer's zone ("2 nov" / "Nov 2"), with the year when it is not the current one ("2 nov 2025").
- The note page also shows the full date and time: "2 de noviembre de 2026, 20:30" / "November 2, 2026, 8:30 PM".
- The note's game button names the game's own day, in US Eastern (ADR 0082, the NBA day), taken from the game's start time in the game detail feed. The note's published time is not used, since a late game's recap can be published the next day. Until that feed loads, or if it fails, the button shows the score without the date.

## Home carousel

A section titled "News" ("Noticias") with the kicker "League" ("Liga"). On the right, "See all →" (to `/news`) and two 44px buttons, previous and next, with accessible names. The track scrolls horizontally with scroll snap; cards are 300px. The buttons scroll by the distance between two cards, smoothly, and at once under reduced motion. Previous is disabled at the first card and next at the last. Under the track, one bar per card, the current one in the accent color. It shows the 10 latest notes.

## News page

The nav row, the kicker "League" and the h1 "News". Then a type filter (All · Recaps · News) and, when the search feed loads, a team select (All teams and the 30 teams, sorted by name in the active language). Then a grid of cards: three columns on a wide screen, two on a medium one and one on a phone, from the card minimum width and capped at three columns. "Load more" loads the next page while the feed says there is more; notes already shown are dropped by id.

The feeds have no kind path, so the type filter filters the notes already loaded: Load more can add no visible note under a filter. The team select switches to the team's feed and its first page. When the filter leaves no note, the page says "No notes." States: loading shows bones; a missing URL or a failed first page shows "Data isn't available right now. Check back later."

## Note page

The nav row with a back link "← News" to `/news`. Then the tags and the full date, the headline (52px, 34px on mobile), the photo at full width (edge to edge on mobile) with its credit under it, and the description (20px, 17px on mobile). Then "Related": buttons to the game (accent border, "GSW 119 – 114 MIN · Oct 28"; the score alone until the date loads, and no score when the game has none), the note's teams (the code) and its players (the name). There is no game button when the site does not hold the game. States: a 404 or an empty note reads "Note not found." with a link back; a failure reads the unavailable message.

## Links

Every link in a news element goes to a page of the site: `/news`, `/news/{id}`, `/player/{id}`, `/team/{code}` or `/game/{id}`. None leaves the site (`news-links-stay-in-the-site.test.ts`).

## Sections on the team, player and game pages

See `docs/design-profiles.md` (section 9) and `docs/design-game-detail.md` (section 12). The News tab is the last tab; the section is the last section.
