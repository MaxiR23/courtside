# api/tests/jobs/test_season_playoffs_finals_feed.py
#
# Tests for the playoffs finals feed of a past season and its feed kind.
#
# Tested:
# - check: 1993, abc, 02025, 2025 with a trailing newline, the current season and a future season are unknown; 1994 and the season before the current one are known; an unknown current season is not ready
# - target: the current season maps to the current playoffs finals feed, a past season to the season kind
# - The kind: a past season builds a valid Finals feed after the season playoffs feed (built first through depends_on), with the finalists' season rosters, the game details by provider id first and the season on the team reads
# - The kind: a detail, sections, plays, record, statistics or roster read that answers 404 nulls or empties its part (leaders, curve, largest deficit, records, bar values, averages players)
# - The kind: any other failed read answers unavailable and stores nothing
# - The kind: a season whose playoffs feed cannot be built answers unavailable
# - The kind: the feed is stored under season-playoffs-finals and never rebuilt: a second request, a request years later and a restart serve with no source call
# - The kind: detailAvailable is false and the stored highlights are added when served and not stored; the cleanup keeps it
#
# What is covered:
# - Feed kind: success publishes a valid feed, 404 reads null their part, other failures leave nothing stored, kept for good
#
# Fake adapters and a fake clock are passed to the kinds, so no test uses a real
# source or the real clock.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_season_playoffs_finals_feed.py
#
# SEE: api/app/jobs/season_playoffs_finals_feed.py

import datetime as dt
from pathlib import Path
from typing import Any, cast

import pytest

from app.feeds.games import Highlight
from app.feeds.playoffs import AwardCode
from app.feeds.playoffs_finals import PlayoffsFinalsFeed
from app.jobs.on_demand import FeedUnavailableError, IdStatus, UnknownFeedError
from app.jobs.playoffs_finals_feed import FEED_ID as FINALS_ID
from app.jobs.playoffs_finals_feed import KIND as FINALS_KIND
from app.jobs.season_playoffs_feed import KIND as PLAYOFFS_KIND
from app.jobs.season_playoffs_finals_feed import KIND, SeasonPlayoffsFinalsFeeds
from app.jobs.stars import StarsJob
from app.settings import Settings
from app.sources.finals_plays import PlayScore
from app.sources.game_detail import GameDetail, GameDetailSections
from app.sources.http import Freshness, SourceClient
from app.sources.player_stats import PlayerStats
from app.sources.season_awards import SeasonAwards
from app.sources.team_postseason import TeamPostseasonRecord, TeamPostseasonStats
from app.storage.feeds import read_by_id
from tests.jobs.test_playoffs_feed import HOUR, NOW, award
from tests.jobs.test_playoffs_finals_feed import (
    BOTTOM,
    PLAYERS,
    TOP,
    detail,
    record,
    sections,
    stats_of,
    team_stats,
)
from tests.jobs.test_season_playoffs_feed import (
    YEARS,
    FakeRoster,
    SeasonPlayoffsKit,
    no_network,  # noqa: F401
)

LABEL = "2024-25"


class FinalsKit(SeasonPlayoffsKit):
    """The season playoffs kit plus the season Finals kind, with fake adapters
    that record their calls in self.calls."""

    def __init__(self, path: Path) -> None:
        self.fresh: dict[str, Freshness] = {}
        self.by_id: list[bool] = []
        super().__init__(path)

    def register(self) -> None:
        super().register()
        self.season_finals = SeasonPlayoffsFinalsFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            cast(StarsJob, self.stars),
            self.season_playoffs,
            fetch_game_detail=self.fetch_game_detail,
            fetch_game_detail_sections=self.fetch_game_detail_sections,
            fetch_play_scores=self.fetch_play_scores,
            fetch_player_stats=self.fetch_player_stats,
            fetch_season_roster=self.fetch_finalist_roster,
            fetch_team_postseason_record=self.fetch_finals_record,
            fetch_team_postseason_stats=self.fetch_team_postseason_stats,
        )

    async def fetch_season_awards(
        self, client: SourceClient, season: int, settings: Settings
    ) -> SeasonAwards:
        self.read(f"awards/{season}")
        return SeasonAwards(awards=[award(AwardCode.FINALS_MVP, ["101"])])

    async def fetch_season_roster(
        self, client: SourceClient, code: str, season: int, settings: Settings
    ) -> Any:
        found = await super().fetch_season_roster(client, code, season, settings)
        return FakeRoster([*found.entries, *PLAYERS.get(code, [])])

    async def fetch_finalist_roster(
        self, client: SourceClient, code: str, season: int, settings: Settings
    ) -> Any:
        self.read(f"f-roster/{code}/{season}")
        return FakeRoster(list(PLAYERS[code]))

    async def fetch_game_detail(
        self,
        client: SourceClient,
        game_id: str,
        settings: Settings,
        fresh: Freshness,
        *,
        by_id_first: bool = False,
    ) -> GameDetail:
        self.read(f"detail/{game_id}")
        self.fresh[f"detail/{game_id}"] = fresh
        self.by_id.append(by_id_first)
        return detail()

    async def fetch_game_detail_sections(
        self, client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
    ) -> GameDetailSections:
        self.read(f"sections/{game_id}")
        self.fresh[f"sections/{game_id}"] = fresh
        return sections()

    async def fetch_play_scores(
        self, client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
    ) -> list[PlayScore]:
        self.read(f"plays/{game_id}")
        self.fresh[f"plays/{game_id}"] = fresh
        return [PlayScore(elapsed_seconds=60, home_score=0, away_score=5)]

    async def fetch_player_stats(
        self, client: SourceClient, player_id: str, settings: Settings, **query: Any
    ) -> PlayerStats:
        assert query == {"playoffs": True}
        self.read(f"player/{player_id}")
        return stats_of(10.0, season=LABEL)

    async def fetch_finals_record(
        self, client: SourceClient, team: str, season: int, settings: Settings
    ) -> TeamPostseasonRecord:
        self.read(f"finals-record/{team}/{season}")
        return record()

    async def fetch_team_postseason_stats(
        self, client: SourceClient, team: str, season: int, settings: Settings
    ) -> TeamPostseasonStats:
        self.read(f"stats/{team}/{season}")
        return team_stats()

    async def serve_finals(self, season: str, at: dt.datetime | None = None) -> bytes:
        if at is not None:
            self.clock[0] = at
        body = await self.cache.serve(KIND, season)
        await self.settle()
        return body

    def stored_finals(self, season: str) -> PlayoffsFinalsFeed | None:
        body = read_by_id(self.path, KIND, season)
        return None if body is None else PlayoffsFinalsFeed.model_validate_json(body)


@pytest.fixture
def kit(tmp_path: Path) -> FinalsKit:
    return FinalsKit(tmp_path)


@pytest.mark.parametrize("text", ["1993", "abc", "02025", "2025\n", "", "2027", "2028"])
def test_an_ill_formed_early_current_or_future_season_is_unknown(
    kit: FinalsKit, text: str
) -> None:
    assert kit.season_finals.check(text) is IdStatus.UNKNOWN


def test_the_first_season_and_the_season_before_the_current_one_are_known(
    kit: FinalsKit,
) -> None:
    assert kit.season_finals.check("1994") is IdStatus.KNOWN
    assert kit.season_finals.check("2026") is IdStatus.KNOWN


def test_an_unknown_current_season_is_not_ready_from_1994(kit: FinalsKit) -> None:
    kit.stars.season = None

    assert kit.season_finals.check("2025") is IdStatus.NOT_READY
    assert kit.season_finals.check("1993") is IdStatus.UNKNOWN


def test_the_current_season_maps_to_the_current_finals_feed(kit: FinalsKit) -> None:
    assert kit.season_finals.target("2027") == (FINALS_KIND, FINALS_ID)
    assert kit.season_finals.target("2025") == (KIND, "2025")
    kit.stars.season = None
    assert kit.season_finals.target("2027") == (KIND, "2027")


@pytest.mark.anyio
async def test_a_past_season_builds_a_valid_finals_feed_after_the_season_playoffs_feed(
    kit: FinalsKit,
) -> None:
    body = await kit.serve_finals("2025")

    feed = PlayoffsFinalsFeed.model_validate_json(body)
    assert feed.season == LABEL
    assert str(feed.champion) == TOP
    assert [g.game.id for g in feed.games] == [f"finals-{n}" for n in range(1, 6)]
    assert read_by_id(kit.path, PLAYOFFS_KIND, "2025") is not None
    assert kit.calls.index("standings/2025") < kit.calls.index("detail/finals-1")
    assert sorted(n for n in kit.calls if n.startswith("f-roster/")) == sorted(
        [f"f-roster/{TOP}/2025", f"f-roster/{BOTTOM}/2025"]
    )
    assert kit.by_id and all(kit.by_id)
    assert kit.called("detail/") == kit.called("sections/") == 5
    assert kit.called("plays/") == 5
    assert f"finals-record/{TOP}/2025" in kit.calls
    assert f"stats/{BOTTOM}/2025" in kit.calls
    assert sorted(n for n in kit.calls if n.startswith("player/")) == [
        "player/101",
        "player/102",
        "player/201",
        "player/202",
    ]
    assert kit.fresh and all(f == HOUR for f in kit.fresh.values())
    assert [p.player_id for p in feed.averages[0].players] == ["102", "101"]
    assert feed.finals_mvp is not None and feed.finals_mvp.player_id == "101"
    assert feed.games[0].leaders is not None
    assert feed.games[0].win_probability is not None
    assert feed.games[0].largest_deficit is not None


@pytest.mark.anyio
async def test_a_stored_feed_is_never_rebuilt_even_years_later_or_after_a_restart(
    kit: FinalsKit,
) -> None:
    first = await kit.serve_finals("2025")
    calls = list(kit.calls)
    second = await kit.serve_finals("2025")
    later = await kit.serve_finals("2025", NOW + YEARS)
    kit.start()
    restarted = await kit.serve_finals("2025", NOW + 2 * YEARS)

    assert first == second == later == restarted
    assert kit.calls == calls


@pytest.mark.anyio
async def test_reads_that_answer_404_null_or_empty_their_parts(kit: FinalsKit) -> None:
    kit.not_found = {
        "detail/finals-1",
        "sections/finals-1",
        "plays/finals-1",
        f"finals-record/{TOP}/2025",
        f"stats/{TOP}/2025",
        f"f-roster/{BOTTOM}/2025",
    }

    feed = PlayoffsFinalsFeed.model_validate_json(await kit.serve_finals("2025"))

    first = feed.games[0]
    assert first.leaders is None
    assert first.win_probability is None
    assert first.largest_deficit is None
    assert feed.games[1].leaders is not None
    road = next(r for r in feed.road if str(r.team.code) == TOP)
    assert road.postseason is None
    assert (
        next(r for r in feed.head_to_head.records if r.team_code == TOP).record is None
    )
    assert feed.head_to_head.bars[0].values[0].value is None
    assert feed.head_to_head.bars[0].better is None
    assert next(a for a in feed.averages if a.team_code == BOTTOM).players == []
    assert next(a for a in feed.averages if a.team_code == TOP).players


@pytest.mark.anyio
@pytest.mark.parametrize(
    "name",
    [
        "detail/finals-1",
        "sections/finals-2",
        "plays/finals-3",
        f"finals-record/{TOP}/2025",
        f"stats/{BOTTOM}/2025",
        f"f-roster/{TOP}/2025",
        "player/101",
    ],
)
async def test_any_other_failed_read_answers_unavailable_and_stores_nothing(
    kit: FinalsKit, name: str
) -> None:
    kit.failing = {name}

    with pytest.raises(FeedUnavailableError):
        await kit.serve_finals("2025")

    assert read_by_id(kit.path, KIND, "2025") is None


@pytest.mark.anyio
async def test_a_season_whose_playoffs_feed_cannot_be_built_answers_unavailable(
    kit: FinalsKit,
) -> None:
    kit.failing = {"standings/2025"}

    with pytest.raises(FeedUnavailableError):
        await kit.serve_finals("2025")

    assert read_by_id(kit.path, KIND, "2025") is None
    assert read_by_id(kit.path, PLAYOFFS_KIND, "2025") is None


@pytest.mark.anyio
@pytest.mark.parametrize("season", ["1993", "2027", "abc", "2025\n"])
async def test_an_invalid_id_answers_unknown_with_no_source_request(
    kit: FinalsKit, season: str
) -> None:
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, season)

    assert kit.calls == []


@pytest.mark.anyio
async def test_detail_is_never_available_and_stored_highlights_are_added_when_served_and_not_stored(
    kit: FinalsKit,
) -> None:
    first = PlayoffsFinalsFeed.model_validate_json(await kit.serve_finals("2025"))
    assert all(g.highlights is None for g in first.games)
    game_id = first.games[0].game.id
    clip = Highlight.model_validate(
        {
            "title": "Example highlights",
            "channel": "Example Channel",
            "thumbnail_url": "https://example.com/t.jpg",
            "embed_url": "https://example.com/e/v1",
        }
    )
    kit.store.set_highlight(game_id, clip)

    feed = PlayoffsFinalsFeed.model_validate_json(await kit.serve_finals("2025"))

    assert all(g.game.detail_available is False for g in feed.games)
    served = {g.game.id: g.highlights for g in feed.games}
    assert served[game_id] == [clip]
    assert all(v is None for k, v in served.items() if k != game_id)
    stored = kit.stored_finals("2025")
    assert stored is not None
    assert all(g.highlights is None for g in stored.games)


@pytest.mark.anyio
async def test_the_cleanup_keeps_the_feed(kit: FinalsKit) -> None:
    body = await kit.serve_finals("2025")

    kit.cache.cleanup()

    assert read_by_id(kit.path, KIND, "2025") == body
