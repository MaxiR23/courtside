# Testing

Conventions for tests in this repo. The test commands for each app are
listed in `README.md` once that app is scaffolded.

## Tools

| App | Runner | Notes |
|---|---|---|
| `/web` | Vitest | Components are tested with `@testing-library/svelte` |
| `/api` | pytest | HTTP calls are mocked with respx (httpx client) |

## File location

Each app keeps its tests in its own `tests/` folder, mirroring that app's
source structure. Example paths below are illustrative: the real structure
is defined when each app is scaffolded.

```text
web/src/lib/format/clock.ts           -> web/tests/lib/format/clock.test.ts
web/src/lib/components/GameCard.svelte -> web/tests/lib/components/GameCard.test.ts
api/<package>/sources/<adapter>.py    -> api/tests/sources/test_<adapter>.py
```

Cross-cutting tests that do not map to a single module live at the root of
the app's `tests/` folder.

## Naming

Test names describe the behavior being verified, not a category. The name
should be enough to know what broke when it fails.

```ts
it('shows the losing team dimmed on a final game')
it('hides final scores until the card is expanded in spoiler-free mode')
```

```python
def test_keeps_last_valid_feed_when_the_source_fails():
def test_rejects_a_game_without_a_home_team():
```

## Coverage minimums

- **Pure logic** (formatting, sorting, date handling), in either app: happy
  path, edge cases and error case.
- **Source adapters**: a valid response is mapped to the models; an
  unexpected or invalid payload is rejected; an upstream failure (timeout,
  error status) is handled.
- **Jobs**: a successful run publishes a valid feed; a failed run keeps the
  last valid feed published; where a secondary source exists, the job
  falls back to it.
- **Feed models**: a valid feed is accepted and an invalid one is rejected.
- **API endpoints**: the success response and each documented failure.
- **Components**: each state the component can show renders what is
  expected (for a game: scheduled, live, final, and no data), and the
  component responds to user interaction where it applies.

## Front end specifics

- Reactive logic that is more than a line or two lives in its own
  `.svelte.ts` module and is tested there, without mounting a component.
- jsdom does not lay out or animate. Assert state, rendered content,
  attributes and classes. Do not assert computed sizes, positions or
  animation frames: that test would pass without proving anything.

## Time and data

- Tests never depend on the real clock. Anything that uses "today", "now"
  or a game clock receives the time as input or runs with a frozen time.
- Source responses used in tests are stored as fixture files next to the
  tests that use them. Fixtures contain only what the test needs.
- Sample data never names a real brand for what it makes up: made-up
  channels and broadcasters, and any other commercial brand that is not
  the league content itself. Domains are example.com or `.example`. The
  league's own teams, players and arenas are the app's content and stay
  as they are.

## Mocking external services

All network calls are mocked. Tests never reach a real data source or a
real service, not even a sandbox.

- `/web`: feed requests are mocked with Vitest's `vi.fn()` and `vi.mock()`.
- `/api`: HTTP calls are mocked at the HTTP client level with respx.

In both apps, mocks are configured so an unmatched call fails instead of
passing through. Otherwise a test can silently reach a real service.

## File header

Each test file MUST start with this header. Keywords stay in English.

TypeScript:

```ts
// web/tests/lib/components/GameCard.test.ts
//
// Tests for the GameCard component.
//
// Tested:
// - Renders the score and status of a final game
// - Dims the losing team on a final game
// - Expands and collapses when the row is clicked
//
// What is covered:
// - Happy paths, final and live states, user interaction
//
// Run with: <single-file command listed in README.md>
//
// SEE: web/src/lib/components/GameCard.svelte
```

Python:

```python
# api/tests/sources/test_<adapter>.py
#
# Tests for the <adapter> source adapter.
#
# Tested:
# - Maps a valid response to the feed models
# - Rejects a response with an unexpected shape
# - Raises the adapter error on a timeout
#
# What is covered:
# - Happy path, invalid payload, upstream failure
#
# Run with: <single-file command listed in README.md>
#
# SEE: api/<package>/sources/<adapter>.py
```

## Guard tests

Cross-cutting tests at the root of `web/tests/` keep a shared piece the only owner of what it draws (see `docs/design.md`, "Shared components"). Each scans source files and fails when another file re-implements what the piece owns. The scan scope is in each row.

| Test file | Protects |
|---|---|
| `page-header-is-the-one-header.test.ts` | The page header: only `PageHeader` imports the nav row and draws the header grid, and only it and the calendar sheet import the season selector. |
| `headers-first-line-offset.test.ts` | The distance between the nav row and the first line: only `PageHeader` applies the offset tokens, and no component reaches into the nav row. Scans `web/src/lib/components` only. |
| `page-container-is-the-one-content-width.test.ts` | The content width and side padding: only `PageContainer` (and `PageHeader`) set them. |
| `skeleton-bone-is-the-one-bone.test.ts` | The skeleton bone: only `SkeletonBone` defines a `.bone` rule or uses a bone class. |
| `kicker-is-the-one-label.test.ts` | The small uppercase label: only `Kicker` holds its declaration set. |
| `tag-is-the-one-tag.test.ts` | The tag box and the solid tag fill: only `Tag` holds them, besides the listed non-tags. |
| `info-cell-is-the-one-cell.test.ts` | The info cell: only `InfoCell` holds its divider and value declarations, besides the listed lookalikes. |
| `section-head-is-the-one-section-title.test.ts` | The section title: only `SectionHead` styles an `h2` or reads a section title size. |
| `initials-is-the-one-rule.test.ts` | The initials rule: only `format/initials.ts` declares an initials function. Scans `web/src/lib` only. |
| `feed-source-follows-its-url.test.ts` | The feed source of a route: no `new FeedPoller`, `FeedOnce`, `GamesFeedPoller` or `DayLoader` in `web/src/routes` takes a closure that reads `params`. Scans `web/src/routes` only. |
| `sticky-bar-is-the-one-stuck-state.test.ts` | The mini text and the stuck bar: `SectionTabs` shows the mini score or text only from `stickyBar.stuck` and has no prop or branch that shows it otherwise; only `web/src/lib/scroll/scrolled-past.svelte.ts` builds the sticky bar state, only `SectionTabs` registers the bar and draws the mini; every `<SectionTabs>` in `web/src/lib/components` and `web/src/routes` passes `layout` and no element to watch; nothing outside the shared module and `SectionTabs` names the tab bar's class, and `web/src/lib/player/scroll-fade.ts` reads the bar's bottom edge from `stickyBar.bottom` with no element lookup. |

## TDD workflow

Red, green, refactor:

1. Write the test. It fails.
2. Write the minimum code to make it pass.
3. Refactor with the tests green.

Tests and implementation ship in the same branch and the same PR. A change
without tests is not done.

## SEE

- Vitest: https://vitest.dev/
- Svelte Testing Library: https://testing-library.com/docs/svelte-testing-library/intro
- pytest: https://docs.pytest.org/