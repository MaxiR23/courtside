# api/tests/jobs/test_season_all_star_feed.py
#
# Tests for the All-Star feed of a past season and its feed kind.
#
# Tested:
# - february_days: the US Eastern February days of the end year, sorted and unique, the Eastern day of a late UTC moment, other months and years dropped, none
# - The kind: the season check (range, formats, current and future seasons, not ready), and the target (the current season is the current feed)
# - Discovery: only the February days the calendar lists, in order, until the first with All-Star games; the edition is stored; a stored edition reads no calendar
# - No edition: unknown, nothing stored, remembered with no further read; a previous season with none gives a null recap; a stored edition overrides the memory
# - Build: an after feed is stored at feeds/season-all-star/{season}.json and kept; a feed that is not after is not stored and logs the season
# - Reads: a 404 nulls its part (detail, sections, extras, awards); any other failed read, calendar or day fails the build
# - Previous edition: the recap and the whole edition; none for 1994
# - No per-game highlight, null league teams and no team info read
# - The edition video is served as editionHighlight on the edition, the recap and the previous edition, null when none, and not stored
# - The kind: the cleanup keeps a past season feed
#
# What is covered:
# - Pure logic: happy path and edges
# - Feed kind: success publishes a valid feed, failure stores nothing
#
# Fake adapters and a fake clock are passed to the kind, so no test uses a real
# source or the real clock. Clubs, players and arenas are invented.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_season_all_star_feed.py
#
# SEE: api/app/jobs/season_all_star_feed.py

import datetime as dt
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
import respx
from pydantic import HttpUrl

from app.feeds.all_star import AllStarFeed, AllStarState
from app.feeds.games import Highlight
from app.feeds.playoffs import AwardCode
from app.jobs import all_star_feed
from app.jobs.on_demand import FeedUnavailableError, IdStatus, UnknownFeedError
from app.jobs.season_all_star_feed import KIND, SeasonAllStarFeeds, february_days
from app.jobs.stars import StarsJob
from app.settings import Settings
from app.sources.all_star_detail import AllStarDetailExtras
from app.sources.all_star_scoreboard import AllStarScoreboardGame
from app.sources.game_detail import GameDetail, GameDetailSections
from app.sources.http import Freshness, SourceClient, SourceError
from app.sources.season_awards import SeasonAwards
from app.storage.feeds import read_by_id
from tests.jobs.test_all_star_feed import (
    CHAMPIONSHIP,
    PKS,
    STR,
    WAV,
    AllStarKit,
    award,
    detail,
    extras,
    game,
    round_robin,
    sections_of,
)

EDITION = dt.date(2025, 2, 16)
EARLIER = dt.date(2024, 2, 18)


def at(month: int, day: int, year: int = 2025, hour: int = 17) -> dt.datetime:
    return dt.datetime(year, month, day, hour, tzinfo=dt.UTC)


def earlier_games() -> list[AllStarScoreboardGame]:
    return [
        game("p1", STR, WAV, score=(21, 18)),
        game("p2", WAV, PKS, note=CHAMPIONSHIP, score=(20, 22), minutes=30),
    ]


# Group 1: february_days


def test_february_days_are_the_eastern_february_days_of_the_year_sorted_and_unique() -> (
    None
):
    moments = [
        at(2, 16),
        at(1, 20),
        at(2, 9),
        at(2, 16, hour=20),
        at(3, 3),
        at(2, 9, year=2024),
    ]

    assert february_days(moments, 2025) == [dt.date(2025, 2, 9), dt.date(2025, 2, 16)]


def test_february_days_keep_a_late_utc_moment_that_is_still_february_in_the_east() -> (
    None
):
    assert february_days([at(3, 1, hour=2)], 2025) == [dt.date(2025, 2, 28)]


def test_february_days_are_empty_with_no_february_entry() -> None:
    assert february_days([at(1, 5), at(3, 5)], 2025) == []
    assert february_days([], 2025) == []


# Group 2: the kind


class SeasonAllStarKit(AllStarKit):
    """The season kind over the All-Star kit's store, client, cache and clock,
    with fake adapters that count their calls."""

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.missing: set[str] = set()
        self.calendars: dict[int, list[dt.datetime]] = {
            2025: [at(1, 20), at(2, 9), at(2, 16), at(3, 3)],
            2024: [at(2, 5, 2024), at(2, 18, 2024)],
        }
        self.days = {EDITION: round_robin(), EARLIER: earlier_games()}
        self.season_feeds = SeasonAllStarFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            cast(StarsJob, self.stars),
            fetch_season_calendar=self.fetch_calendar,
            fetch_all_star_games=self.fetch_day,
            fetch_game_detail=self.fetch_game_detail,
            fetch_game_detail_sections=self.fetch_game_detail_sections,
            fetch_all_star_extras=self.fetch_all_star_extras,
            fetch_season_awards=self.fetch_season_awards,
        )

    def read(self, name: str) -> None:
        super().read(name)
        if name in self.missing:
            raise SourceError("test", f"{name} is missing", status_code=404)

    async def fetch_calendar(
        self, client: SourceClient, season: int, settings: Settings
    ) -> list[dt.datetime]:
        self.read(f"calendar/{season}")
        return list(self.calendars.get(season, []))

    async def fetch_season_awards(
        self, client: SourceClient, season: int, settings: Settings
    ) -> SeasonAwards:
        self.read(f"awards/{season}")
        return award(self.mvp_id if season == 2025 else "3001", self.mvp_code)

    async def fetch_game_detail(
        self, client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
    ) -> GameDetail:
        self.read(f"detail/{game_id}")
        return detail()

    async def fetch_game_detail_sections(
        self, client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
    ) -> GameDetailSections:
        self.read(f"sections/{game_id}")
        return sections_of(self.find(game_id))

    async def fetch_all_star_extras(
        self, client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
    ) -> AllStarDetailExtras:
        self.read(f"extras/{game_id}")
        return extras()

    async def request(self, season: str = "2025") -> AllStarFeed:
        body = await self.cache.serve(KIND, season)
        await self.settle()
        return AllStarFeed.model_validate_json(body)

    def stored_feed(self, season: str = "2025") -> AllStarFeed | None:
        body = read_by_id(self.path, KIND, season)
        return None if body is None else AllStarFeed.model_validate_json(body)


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


@pytest.fixture
def kit(tmp_path: Path) -> SeasonAllStarKit:
    return SeasonAllStarKit(tmp_path)


def test_the_check_accepts_the_past_seasons_from_1994(kit: SeasonAllStarKit) -> None:
    for season in ("1994", "2026"):
        assert kit.season_feeds.check(season) is IdStatus.KNOWN
    for season in ("1993", "2027", "2028", "abc", "02025", "2025\n"):
        assert kit.season_feeds.check(season) is IdStatus.UNKNOWN
    assert kit.calls == []


def test_the_check_is_not_ready_while_the_season_is_unknown(
    kit: SeasonAllStarKit,
) -> None:
    kit.stars.season = None

    assert kit.season_feeds.check("2025") is IdStatus.NOT_READY


def test_the_target_resolves_the_current_season_to_the_current_feed(
    kit: SeasonAllStarKit,
) -> None:
    assert kit.season_feeds.target("2027") == (
        all_star_feed.KIND,
        all_star_feed.FEED_ID,
    )
    assert kit.season_feeds.target("2025") == (KIND, "2025")
    kit.stars.season = None
    assert kit.season_feeds.target("2027") == (KIND, "2027")


@pytest.mark.anyio
async def test_discovery_reads_only_the_listed_february_days_up_to_the_edition(
    kit: SeasonAllStarKit,
) -> None:
    await kit.request()

    scan = [c for c in kit.calls if c.startswith(("calendar/2025", "day/2025"))]
    assert scan == ["calendar/2025", "day/2025-02-09", "day/2025-02-16"]
    earlier = [c for c in kit.calls if c.startswith(("calendar/2024", "day/2024"))]
    assert earlier == ["calendar/2024", "day/2024-02-05", "day/2024-02-18"]


@pytest.mark.anyio
async def test_the_found_edition_is_stored(kit: SeasonAllStarKit) -> None:
    await kit.request()

    record = kit.store.all_star_edition(2025)
    assert record is not None
    assert record.game_date == EDITION
    assert record.game_ids == ["g1", "g2", "g3", "g4"]
    assert kit.store.all_star_edition(2024) is not None


@pytest.mark.anyio
async def test_a_stored_edition_is_used_with_no_calendar_read(
    kit: SeasonAllStarKit,
) -> None:
    kit.store.set_all_star_edition(2025, EDITION, ["g1"])
    kit.store.set_all_star_edition(2024, EARLIER, ["p1"])

    feed = await kit.request()

    assert feed.state is AllStarState.AFTER
    assert kit.called("calendar/") == 0
    assert "day/2025-02-16" in kit.calls and "day/2025-02-09" not in kit.calls


@pytest.mark.anyio
async def test_a_season_with_no_edition_is_unknown_stored_nowhere_and_not_scanned_again(
    kit: SeasonAllStarKit, tmp_path: Path
) -> None:
    kit.days = {}
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, "2025")
    await kit.settle()
    calls = len(kit.calls)

    assert kit.season_feeds.check("2025") is IdStatus.UNKNOWN
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, "2025")

    assert len(kit.calls) == calls
    assert kit.store.all_star_edition(2025) is None
    assert kit.store.feed_build(KIND, "2025") is None
    assert not (tmp_path / "feeds" / KIND).exists()


@pytest.mark.anyio
async def test_a_previous_season_with_no_edition_gives_a_null_recap_and_is_remembered(
    kit: SeasonAllStarKit,
) -> None:
    del kit.days[EARLIER]

    feed = await kit.request()

    assert feed.previous is None and feed.previous_edition is None
    assert kit.season_feeds.check("2024") is IdStatus.UNKNOWN
    calls = len(kit.calls)
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, "2024")
    assert len(kit.calls) == calls


def test_an_edition_stored_later_overrides_a_remembered_miss(
    kit: SeasonAllStarKit,
) -> None:
    kit.season_feeds._no_edition.add(2024)
    assert kit.season_feeds.check("2024") is IdStatus.UNKNOWN

    kit.store.set_all_star_edition(2024, EARLIER, ["p1"])

    assert kit.season_feeds.check("2024") is IdStatus.KNOWN


@pytest.mark.anyio
async def test_an_after_feed_is_stored_and_kept(
    kit: SeasonAllStarKit, tmp_path: Path
) -> None:
    feed = await kit.request()

    assert feed.state is AllStarState.AFTER and feed.year == 2025
    assert (tmp_path / "feeds" / KIND / "2025.json").exists()
    assert kit.stored_feed() == feed
    assert kit.season_feeds.stored("2025") == feed
    calls = len(kit.calls)

    kit.clock[0] += dt.timedelta(days=30)
    again = await kit.request()

    assert again == feed
    assert len(kit.calls) == calls


@pytest.mark.anyio
async def test_a_feed_that_is_not_after_is_not_stored_and_logs_the_season(
    kit: SeasonAllStarKit, caplog: pytest.LogCaptureFixture
) -> None:
    kit.days[EDITION] = round_robin(final=False)

    with caplog.at_level(logging.WARNING), pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, "2025")
    await kit.settle()

    assert kit.stored_feed() is None
    assert "season all-star: 2025 not built" in caplog.text


@pytest.mark.anyio
async def test_the_mvp_is_null_when_the_awards_answer_404(
    kit: SeasonAllStarKit,
) -> None:
    kit.missing = {"awards/2025"}
    feed = await kit.request()
    assert feed.mvp is None
    assert feed.previous is not None and feed.previous.mvp is not None


@pytest.mark.anyio
async def test_the_mvp_is_null_when_the_awards_have_no_all_star_mvp(
    kit: SeasonAllStarKit,
) -> None:
    kit.mvp_code = AwardCode.MVP
    feed = await kit.request()
    assert feed.mvp is None
    assert "awards/2025" in kit.calls


@pytest.mark.anyio
async def test_a_non_404_awards_failure_fails_the_build(kit: SeasonAllStarKit) -> None:
    kit.failing = {"awards/2025"}

    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, "2025")
    await kit.settle()

    assert kit.stored_feed() is None


@pytest.mark.anyio
async def test_a_404_on_a_detail_sections_or_extras_read_only_nulls_its_part(
    kit: SeasonAllStarKit,
) -> None:
    kit.missing = {"detail/g1", "sections/g2", "extras/g3"}

    feed = await kit.request()

    assert feed.state is AllStarState.AFTER
    assert kit.stored_feed() is not None


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failing", ["detail/g1", "sections/g2", "extras/g3", "awards/2024", "detail/p1"]
)
async def test_any_other_failed_read_fails_the_build_and_stores_nothing(
    kit: SeasonAllStarKit, failing: str
) -> None:
    kit.failing = {failing}

    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, "2025")
    await kit.settle()

    assert kit.stored_feed() is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failing", ["calendar/2025", "day/2025-02-09", "day/2025-02-16", "calendar/2024"]
)
async def test_a_failed_calendar_or_day_read_fails_the_build_without_a_miss(
    kit: SeasonAllStarKit, failing: str
) -> None:
    kit.failing = {failing}

    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, "2025")
    await kit.settle()

    assert kit.stored_feed() is None
    assert kit.season_feeds._no_edition == set()


@pytest.mark.anyio
async def test_the_previous_edition_is_the_recap_and_the_whole_edition(
    kit: SeasonAllStarKit,
) -> None:
    feed = await kit.request()

    assert feed.previous is not None and feed.previous.year == 2024
    assert feed.previous.mvp is not None
    assert feed.previous_edition is not None
    assert feed.previous_edition.date == feed.previous.date == EARLIER


@pytest.mark.anyio
async def test_1994_has_no_previous_edition_and_reads_nothing_of_1993(
    kit: SeasonAllStarKit,
) -> None:
    kit.calendars[1994] = [at(2, 20, 1994)]
    kit.days = {dt.date(1994, 2, 20): round_robin()}

    feed = await kit.request("1994")

    assert feed.previous is None and feed.previous_edition is None
    assert not any("1993" in call for call in kit.calls)


@pytest.mark.anyio
async def test_no_per_game_highlight_is_set(kit: SeasonAllStarKit) -> None:
    for game_id in ("g1", "p1"):
        kit.store.set_highlight(
            game_id,
            Highlight(
                title="A play",
                channel="Example Channel",
                thumbnail_url=HttpUrl("https://example.com/play.jpg"),
                embed_url=HttpUrl("https://example.com/embed/play"),
            ),
        )

    feed = await kit.request()

    assert feed.previous_edition is not None
    served = [*feed.edition.games, *feed.previous_edition.games]
    assert served and all(g.highlights is None for g in served)


def edition_clip(title: str) -> Highlight:
    return Highlight(
        title=title,
        channel="Example Channel",
        thumbnail_url=HttpUrl("https://example.com/edition.jpg"),
        embed_url=HttpUrl("https://example.com/embed/edition"),
    )


@pytest.mark.anyio
async def test_the_edition_video_is_served_as_edition_highlight_and_not_stored(
    kit: SeasonAllStarKit,
) -> None:
    kit.store.set_all_star_edition_highlight(2025, edition_clip("current"))
    kit.store.set_all_star_edition_highlight(2024, edition_clip("earlier"))

    feed = await kit.request()

    assert feed.edition.edition_highlight == edition_clip("current")
    assert feed.previous is not None
    assert feed.previous.edition_highlight == edition_clip("earlier")
    assert feed.previous_edition is not None
    assert feed.previous_edition.edition_highlight == edition_clip("earlier")
    stored = kit.stored_feed()
    assert stored is not None and stored.previous_edition is not None
    assert stored.edition.edition_highlight is None
    assert stored.previous_edition.edition_highlight is None


@pytest.mark.anyio
async def test_the_edition_video_is_null_when_none_is_stored(
    kit: SeasonAllStarKit,
) -> None:
    feed = await kit.request()

    assert feed.edition.edition_highlight is None
    assert feed.previous is not None and feed.previous.edition_highlight is None


@pytest.mark.anyio
async def test_league_teams_are_null_and_no_team_info_is_read(
    kit: SeasonAllStarKit,
) -> None:
    feed = await kit.request()

    rows = [
        player
        for g in feed.edition.games
        if g.box_score is not None
        for team in (g.box_score.away, g.box_score.home)
        for player in team.players
    ]
    assert rows and all(p.league_team is None for p in rows)
    assert all(r.league_team is None for g in feed.edition.games for r in g.top5)
    assert feed.mvp is None or feed.mvp.league_team is None
    assert kit.called("info/") == 0


def test_the_cleanup_keeps_a_past_season_feed(kit: SeasonAllStarKit) -> None:
    assert kit.season_feeds.keep("2025")
    assert kit.season_feeds.is_fresh(
        cast(AllStarFeed, None), kit.clock[0], kit.clock[0]
    )
