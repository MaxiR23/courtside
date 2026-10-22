# Design: Team identity

The visual, interaction and data specification of team identity across the site: team logos and team colors. It covers the shared team identity data, the hero color rule, the `TeamMark` component extended to draw logos, the redesigned home hero, every placement of the mark, and the footer line on every page. It extends `docs/design.md`: every existing token, component and rule applies here, and only new values are listed under "New tokens". It follows the structure of `docs/design-playoffs.md`.

## Overview

| Surface | Route | Feeds |
|---|---|---|
| Home hero | `/` | The home feed (hero games) |
| Every surface with a team | all | Every feed that carries a league team object |
| Footer | all | None (fixed strings) |

Decisions in force for this design:

1. **A shared team identity per league team**, kept by the backend and refreshed daily: code, logo (light and dark variants, `null` when the team has none), primary color and secondary color (`null` when absent). Every league team object in every feed carries the logo and the colors. Guest sides and historical sides carry `null` logo and `null` colors and keep the neutral monogram.
2. **Hero color rule**, computed by the backend for each hero game and sent as an accent per side. See "Hero color rule".
3. **One `TeamMark` component draws the logo everywhere.** `TeamMark` is the existing component (`part`: tile, label, name), extended with an optional `logo` for its tile. The tile draws the logo (the dark variant on the dark ground, the light variant as fallback) inside `TeamMonogram`'s box, at the size variant asked, in place of the monogram, and the monogram when the logo is `null` or fails to load. The home hero is the first placement; the other placements come in the next issue. Team colors appear only as data (bars, fills, the hero accent), never as page chrome. The site accent stays.
4. **A footer line on every page**, in the page language. See "Footer".

## Implementation rules

Everything under "Implementation rules" in `docs/design.md` applies, plus:

- **`/web` computes nothing.** Logo URLs, the logo variant to use when one is missing, colors, the hero accents, the resolved colors and every color comparison come ready from the feeds. `/web` never measures lightness or distance.
- **Nothing is hardcoded in `/web`:** no team, color, logo, city or arena. No data source name, video platform or URL is written in `/web`.
- **Every user-facing string is translatable**, in English and Spanish.
- **A value that is missing renders `—`. A missing logo renders the monogram.**
- **Team colors are data, not chrome.** They are used only for the color bars of the team page, bars and fills that show a team's data, and the hero accent. Borders, buttons, links, focus rings, tags and backgrounds of the page keep the site tokens and the site accent.
- **Every logo image has an empty alt text** when the team name is written next to it, and the team name as alt text when it stands alone.
- **Logos never stretch:** `object-fit: contain` in a square box.
- **Shared components are reused:** `BlueprintFrame`, `Kicker`, `StatusTag`, the loading skeletons and the footer.

### New components

| Component | What it is |
|---|---|
| `TeamMark` | The existing component, extended: the tile draws the team logo at a size variant in `TeamMonogram`'s box (which gains the `fill` size), or the monogram when the logo is `null` or fails to load. It draws the logo in place of the monogram |
| `HeroSlideSelector` | One slide button of the home hero: the 2px timer track, the logo and the team name |
| `HeroPlayerCard` | The right column of the home hero: the frame, the layers of each slide and the player strip |
| `HeroBackgroundWord` | The outlined star short name behind the hero |

## Hero color rule

The backend computes, for each hero game, one accent per side and sends it with the game. `/web` uses the two accents as sent.

Colors are compared in OKLab. L is the OKLab lightness (0 to 1). The distance between two colors is the Euclidean distance in OKLab.

1. **Home side first.** Its accent is its primary color, unless the primary's L is below 0.36: then it is its secondary color.
2. **Away side second.** Its accent is its primary color, unless the primary's L is below 0.36: then it is its secondary color. Then, if the OKLab distance between that color and the home's resolved accent is below 0.12, the away accent is its secondary color.
3. **A team with no secondary color keeps its primary** in every step above.
4. **A side with no colors** (guest side, historical side, or a team whose identity is not read yet) has a `null` accent in the feed (`Game.accent` is itself `null` on the day feed), and the web draws the neutral site accent `#749dc4` (`--identity-neutral-accent`).

Reference pairs (away at home), used as the tests of the backend:

| Game | Home accent | Away accent |
|---|---|---|
| NYK at ORL | ORL blue | NYK orange |
| MIL at BOS | BOS green | MIL cream |
| LAL at PHX | PHX orange | LAL purple |
| OKC at DEN | DEN gold | OKC blue |

## Home hero

The hero keeps its content (tag, kicker, h1, paragraph, slide selectors, player card) and gets the layout below. Values not listed keep `docs/design.md`.

### Section

- Full width, ground `#0c0e10` (the page ground) with an 88px grid of 1px lines at `rgba(235,232,227,.035)` and a 1px divider at the bottom.
- Content max-width 1320px. Padding: top `clamp(16px, 4vw, 40px)`, sides `clamp(20px, 4vw, 48px)`, bottom `clamp(56px, 6vw, 80px)`.
- Grid `repeat(auto-fit, minmax(min(100%, 440px), 1fr))`, gap `clamp(40px, 6vw, 96px)`, vertically centered, min-height `min(780px, 84vh)`. One column on narrow screens.

### Background word

- The star's short name (the featured game's star player of the active slide's side).
- Barlow Condensed 600, `clamp(180px, 26vw, 420px)`, line-height .8, letter-spacing `-.02em`.
- Transparent fill, 1px stroke in the side's accent at 28% alpha.
- Right-aligned, vertically centered, behind the columns.
- 1.1s crossfade between slides.

### Left column

Gap 28px between its blocks, in order:

1. **Tag and kicker.** The shared `StatusTag` ("Tonight") and the shared `Kicker` "{tip-off} · {home arena}", drawn as they are everywhere (11px, `letter-spacing: .16em`; the kicker in accent-light).
2. **H1, two lines**, uppercase, `clamp(54px, 8.5vw, 132px)`, line-height .86, letter-spacing `-.02em`:
   - Line 1: `[away logo] {Away name}`.
   - Line 2: `at [home logo] {Home name}`, with "at" muted at .42em.
   - Logos are .62em square, `object-fit: contain`, with a .18em gap to the name.
3. **The existing paragraph:** 17px / 1.6, muted, max-width 440px. The Match details and All games buttons and the position label ("02 / 03") stay between the paragraph and the selectors; the idle float and the floor shadow of `docs/design.md` stay.
4. **Slide selectors:** a 2-column grid of buttons up to 200px wide each, 20px gap. Each button holds:
   - A 2px track `rgba(235,232,227,.14)`, filled in the side's accent over 5s linear while its slide is active.
   - Below the track, a 20px `TeamMark` and the team name (Barlow Condensed 600, 15px, `letter-spacing: .08em`, uppercase), ink when active, muted when inactive.
   - A click goes to that slide and restarts the timer.

### Right column: player card

- Max-width 500px, aspect ratio 4:5, margin-top 40px.
- The existing blueprint frame with the 4 corner marks. Background `#11161b` with a 44px grid at `rgba(235,232,227,.045)`. Shadow `0 50px 100px -24px rgba(0,0,0,.9)`. The inner layer has `overflow: hidden`.
- Outer radial glow at inset `-18%`, in the active side's accent at 22% alpha.
- Layers per slide, back to front, 1s crossfade:

| Layer | Spec |
|---|---|
| Inner radial glow | Centered at 50% 60%, the accent at 30% alpha |
| Team logo | Centered, top 6%, width 84%, `object-fit: contain`, opacity .22 |
| Tricode | Barlow Condensed 700, `clamp(130px, 19vw, 232px)`, line-height .8, centered, bottom 17%, solid accent fill |
| Player cutout | Bottom-anchored, centered, width 172%, `filter: drop-shadow(0 0 1px rgba(148,188,227,.35)) drop-shadow(0 30px 30px rgba(0,0,0,.7)) contrast(1.05)` |
| Bottom scrim | 34% high, `linear-gradient(to top, rgba(17,22,27,.95), transparent)` |
| Player strip | 20px from the sides, 18px from the bottom: a 36px `TeamMark`, the player name (Barlow Condensed 600, 26px, `letter-spacing: .04em`, uppercase) over "{City} {Team}" (12px, `letter-spacing: .12em`, uppercase, muted) |

- The inactive slide sits at `translateY(24px) scale(.97)`. The logo and the tricode transition back over 1.2s `cubic-bezier(.2, .7, .1, 1)`.
- Slides auto-advance every 5s, away then home. A new featured game starts at the away slide. The existing parallax may stay.
- No review controls are built.

### A side with no logo

A league side whose identity is not read yet (`null` logo and `null` accent) shows the monogram where the logo would go (h1, selector, player strip, card logo layer) and the neutral accent `#749dc4`. A guest side never reaches the hero (ADR 0025).

## Footer

Every page shows the footer line below, in the page language, in the footer in place of the "Personal project. Not affiliated with the NBA." line: 12px, muted, same position as that line. On a narrow screen it wraps and stays readable; it is never truncated.

## TeamMark placements

`TeamMark` has the same sizes as `TeamMonogram`, plus `fill` (the whole box of its parent). The hero is the only placement so far; the others come in the next issue.

| Surface | Placements |
|---|---|
| Home | Score bar, game list, players to watch, leaders |
| Game page | Header, box score tabs, team stats, play-by-play |
| Standings | Each row and the playoff picture |
| Team | A large logo in the hero (the color bars stay); opponent logos in the schedule and the results |
| Player | Current team; the career table |
| Search | Team results and player results |
| Cup, playoffs, All-Star | Brackets, series headers, champion cards. The All-Star league monograms are replaced by logos; All-Star sides keep the sigla box |
| Day page | Cards as the home |
| Mobile and phone layouts | The same placements at their sizes |

Behavior of `TeamMark`:

- Draws the dark logo variant on the dark ground; when the dark variant is missing it draws the light variant.
- Draws the monogram when the logo is `null`.
- Draws the monogram when the image fails to load (the image error event swaps it in; no broken-image icon is ever shown).
- Reserves its square box before the image loads, so nothing shifts.

## Edge cases

| Case | What shows |
|---|---|
| Team without a secondary color | The secondary is `null`; the team keeps its primary in the hero rule, even when its primary is darker than 0.36 or close to the other side's |
| Two teams with near colors | When the away side's resolved color is under 0.12 OKLab distance from the home's, the away side takes its secondary (reference pairs: MIL at BOS, LAL at PHX) |
| A side without a logo | The monogram in every place the logo goes; the hero uses the neutral accent `#749dc4` for that side |
| A historical side | `null` logo and `null` colors: the neutral monogram and the neutral accent |
| A guest side | A guest game is never in the hero (ADR 0025); in the hero the monogram and the neutral accent apply to a league side whose identity is unknown |
| A logo that fails to load | The monogram replaces the image on the image error; the layout does not move |
| Missing dark variant | The light variant is drawn |
| Spanish strings | Every string has a Spanish text; the h1 "at" word is the Spanish word of the string table; the footer line wraps, never truncates |
| The footer line on every page | The line shows on every route, in the page language, including the loading and the unavailable-feed states |
| Hero with one side missing identity | The other side keeps its accent; the slide selectors and the h1 still show both sides |
| Reduced motion | No slide auto-advance animation of the track, no parallax and no crossfade easing: the active slide shows at once; the click still changes the slide |

## States

| State | What shows |
|---|---|
| Loading | The hero skeleton of `docs/design.md`, with the right column's frame at 4:5; no logo is drawn until the feed arrives; the monogram skeleton block keeps the `TeamMark` size |
| Feed unavailable | The existing states of each page; no logo or color is requested apart from the feeds |
| Logo loading | The reserved square box, then the logo; on error the monogram |
| Hero slide active / inactive | See "Right column: player card" |

## Interactions and motion

| What | How |
|---|---|
| Slide auto-advance | Every 5s, away then home; a new featured game starts at the away slide |
| Selector click | Goes to that slide and restarts the 5s timer |
| Selector track | 2px, fills in the side's accent over 5s linear |
| Background word | 1.1s crossfade between slides |
| Card layers | 1s crossfade between slides |
| Inactive slide | `translateY(24px) scale(.97)`; logo and tricode return over 1.2s `cubic-bezier(.2, .7, .1, 1)` |
| Parallax | The existing parallax may stay |
| Focus | `:focus-visible` as on the home; the selector buttons are keyboard operable |
| Reduced motion | See Edge cases |

## Responsive

- The hero is one column when the width cannot fit two columns of 440px; the player card stays at max-width 500px, aspect 4:5, centered.
- Type sizes of the hero are fluid through the `clamp()` values above.
- The slide selectors keep the 2-column grid.
- `TeamMark` keeps the sizes of `TeamMonogram` on the mobile and phone layouts.
- The footer line wraps on a narrow screen.

## New tokens

Added to `web/src/lib/styles/tokens.css` by the implementing issue. Values not listed map to existing tokens.

| Token | Value | Use |
|---|---|---|
| `--identity-neutral-accent` | `var(--color-accent)` (`#749dc4`) | Accent of a side with no colors |
| `--identity-hero-pad-top` | `clamp(16px, 4vw, 40px)` | Hero padding |
| `--identity-hero-pad-bottom` | `clamp(56px, 6vw, 80px)` | Hero padding |
| `--identity-word-leading` | .8 | Background word |
| `--identity-word-tracking` | `-.02em` | Background word |
| `--identity-word-stroke-alpha` | .28 | Background word stroke |
| `--identity-left-gap` | 28px | Left column |
| `--identity-title-logo-size` | .62em | Logo in the h1 |
| `--identity-title-logo-gap` | .18em | Gap logo to name |
| `--identity-selector-max-width` | 200px | Slide selector |
| `--identity-selector-gap` | 20px | Selector grid |
| `--identity-selector-track-ink` | `rgba(235, 232, 227, 0.14)` | Selector track |
| `--identity-selector-mark` | 20px | Logo in the selector |
| `--identity-selector-name-size` | 15px | Selector team name |
| `--identity-selector-name-tracking` | .08em | Selector team name |
| `--identity-card-margin-top` | 40px | Player card |
| `--identity-card-grid-line` | `rgba(235, 232, 227, 0.045)` | Card grid ink |
| `--identity-card-glow-outer-alpha` | .22 | Outer glow |
| `--identity-card-glow-inner-position` | 50% 60% | Inner glow |
| `--identity-card-glow-inner-alpha` | .3 | Inner glow |
| `--identity-glow-falloff` | 62% | Where both glows fade to transparent |
| `--identity-card-logo-top` | 6% | Card logo layer |
| `--identity-card-logo-width` | 84% | Card logo layer |
| `--identity-card-logo-opacity` | .22 | Card logo layer |
| `--identity-tricode-size` | `clamp(130px, 19vw, 232px)` | Tricode |
| `--identity-tricode-leading` | .8 | Tricode |
| `--identity-tricode-bottom` | 17% | Tricode |
| `--identity-scrim-height` | 34% | Bottom scrim |
| `--identity-scrim` | `linear-gradient(to top, rgba(17, 22, 27, 0.95), transparent)` | Bottom scrim |
| `--identity-strip-inset` | 20px | Player strip sides |
| `--identity-strip-bottom` | 18px | Player strip |
| `--identity-strip-mark` | 36px | Logo in the strip |
| `--identity-strip-name-size` | 26px | Player name |
| `--identity-strip-name-tracking` | .04em | Player name |
| `--identity-strip-team-tracking` | .12em | City and team |
| `--identity-settle-duration` | 1.2s | Logo and tricode return |
| `--font-weight-bold` | 700 | Tricode |

Rows of the specification that map to existing tokens, or that change an existing token that only the hero uses:

| Value | Token |
|---|---|
| Hero grid size 88px, ink .035 | `--hero-grid-size`, `--color-grid-line` |
| Hero max-width 1320px, side padding | `--content-max-width`, `--side-padding` |
| Column minimum 440px, gap | `--hero-column-min`, `--hero-gap` |
| Hero min-height `min(780px, 84vh)` | `--hero-min-height` (value changed) |
| Background word size, 1.1s fade | `--hero-watermark-size`, `--hero-watermark-fade-duration` |
| H1 size `clamp(54px, 8.5vw, 132px)` | `--hero-h1-size` (value changed); leading, tracking and "at" size: `--hero-h1-line-height`, `--hero-h1-letter-spacing`, `--hero-h1-at-size` |
| Selector track height 2px | `--progress-track-height` |
| Auto-advance and track fill, 5s | `--hero-slide-interval` (value changed) |
| Card max-width, ratio, fill, grid size | `--hero-frame-max-width`, `--hero-frame-aspect`, `--color-frame-fill`, `--hero-frame-grid-size` |
| Card shadow | `--shadow-hero-frame` (value changed) |
| Outer glow inset -18% | `calc(-1 * var(--accent-glow-extent))` |
| Layers crossfade 1s | `--hero-crossfade-duration` |
| Cutout width and filter | `--hero-cutout-width`, `--hero-cutout-filter` |
| Inactive slide `translateY(24px) scale(.97)` | `--hero-slide-offset`, `--hero-slide-scale` (values changed) |
| Settle easing | `--ease` |
| City and team size 12px | `--caption-size` |

The kicker size and tracking are those of the shared `Kicker`. The lightness floor 0.36 and the distance floor 0.12 are constants of the backend, not CSS tokens. The divider is `--color-divider`; the site accent is `--color-accent`; accent text is `--color-accent-light`; muted and ink are the existing text tokens.

## Strings

| Key | English | Spanish |
|---|---|---|
| `identity_footer_disclaimer` | Unofficial site, not affiliated with the NBA or its teams. Names and logos belong to their owners. | Sitio no oficial. Sin afiliación con la NBA ni sus equipos. Nombres y logos son propiedad de sus dueños. |
| `identity_hero_slide_away` | Show {team}, away | Mostrar a {team}, visitante |
| `identity_hero_slide_home` | Show {team}, home | Mostrar a {team}, local |

The "Tonight" tag, "at", the kicker and "{city} {team}" keep their existing strings (`status_tonight`, `hero_at`, the kicker built from the tip time and arena, the team name built by the props layer), as do the paragraph and the other hero strings; the keys above are the new ones. `identity_mark_alt` ("{team} logo" / "Logo de {team}") comes with the next issue's standalone logos. The star's short name, the city, the team name, the arena, the tip-off time and the tricode come from the feed. The footer line replaces the previous footer disclaimer string.

## Feed contract

Keys are camelCase. Nullable fields are always present and `null` when absent. Times are UTC, ISO 8601. Every value is computed by the backend; exact field names are set by `docs/api` in the issues that add them.

### Team identity (on every league team object in every feed)

- The team code.
- The logo: `{ light, dark }`, with `light` a string and `dark` a string or `null`; the whole object is `null` when the team has none.
- The colors: `{ primary, secondary }`, hex strings; `secondary` is `null` when absent; the whole object is `null` for a guest or historical side.
- A guest side and a historical side carry `null` logo and `null` colors.
- The identity is kept by the backend and refreshed daily; a feed carries the stored values.

### Home feed hero game

- Per side, an `accent` (hex string) resolved by the hero color rule, home first then away; `null` for a side with no colors, and the web draws the neutral accent `#749dc4`. `Game.accent` is itself `null` on the day feed.
- Per side, the team identity above, the city, the team name and the tricode.
- The star player of each side: name, short name for the background word, and the cutout image.
- The tip-off time and the home arena.
