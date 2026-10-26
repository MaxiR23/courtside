# api/tests/jobs/test_home_feed.py
#
# Tests for the home feed builder and its feed kind.
#
# Tested:
# - Scenario edges: the regular season start day is an off day and the day before is offseason; the day before the All-Star date is the All-Star break and the last game day before it is not; the day after the conference finals is the finals preview, and Finals Game 1 live or final ends it; the first day after the postseason is offseason and its last day is not; the offseason of a build after the postseason uses the next season's windows; with no season type known the scenario is an off day
# - Coming up: null with the next event 15 days away and present at 14; an event with no date never appears; the status is upcoming before an event, now during and done after; a done item is listed only while the window is open and within 14 days; the offseason holds the preseason and Opening Night; a Cup feed of another season gives no Cup item
# - Next game: null with no game day in 14 days; the first tip-off, its broadcast and the count without postponed and canceled games; inGamesWindow follows the games job's shown days; a day inside the window is read from the games job memory with no request
# - Last games: the title for last night, days ago, the break, the finals preview and the offseason; the day per scenario; games from the games job memory inside the window and from the day feed built first outside it; only final games with no All-Star mark; the label of each kind of game
# - Dependencies: the Cup, All-Star, playoffs and day feeds are built first only inside their windows, and the calendar always, with the previous one only with no earlier day
# - Budget and failures: 4 season type reads and 1 scoreboard read at most, 3 season type reads after the postseason, a failed read nulls only what it feeds, a failed dependency never gives a 503, and leaders and finalsPath are null
# - Kind: stored only when requested, unknown and not ready ids, expiry at the day change and 1 hour after the build while an item is now, identity added when served and never stored, and a failed rebuild keeps the stored feed
#
# What is covered:
# - Pure logic happy path, edge and error cases; job success, failure and expiry
#
# The clubs and the broadcasters are made up. Every source read goes through a counted respx route.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_home_feed.py
#
# SEE: api/app/jobs/home_feed.py, docs/api/home.md

import asyncio
import datetime as dt
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
import respx
from pydantic import HttpUrl

from app.feeds.calendar import CalendarFeed
from app.feeds.cup import CupFeed, CupStage, StageEntry
from app.feeds.days import DayFeed
from app.feeds.game_detail import Conference
from app.feeds.games import (
    CupRound,
    FeedModel,
    GameAllStar,
    GamePostseason,
    GameStatus,
    GameTeam,
    LineScore,
    PlayInGameKind,
    PostseasonStage,
    Score,
)
from app.feeds.home import (
    ComingUpKey,
    ComingUpStatus,
    HomeFeed,
    HomeScenario,
    LastGameLabel,
    LastGamesTitleKey,
)
from app.feeds.opponent import TeamColors, TeamLogo
from app.feeds.playoffs import PlayoffsFeed, Series, SeriesGame, SeriesId, SeriesStatus
from app.jobs.calendar_feed import build_calendar_feed
from app.jobs.cup_feed import CupFeeds
from app.jobs.day_feed import build_day_feed
from app.jobs.games import GamesJob
from app.jobs.home_feed import (
    COMING_UP_DAYS,
    FEED_ID,
    KIND,
    MEMORY_FRESH_FOR,
    NOW_FRESH_FOR,
    SCOREBOARD_READS,
    SEASON_TYPE_READS,
    HomeBuildError,
    HomeFeeds,
    HomeSources,
    SeasonWindows,
    break_days,
    build_home_feed,
    game_label,
    item_status,
    last_games_day,
    last_games_title,
    next_game_day,
)
from app.jobs.on_demand import (
    Ensure,
    FeedCache,
    FeedKind,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
)
from app.jobs.playoffs_feed import PlayoffsFeeds
from app.jobs.stars import StarsJob
from app.settings import Settings
from app.sources.game_detail import GameDetail
from app.sources.http import (
    Freshness,
    SourceClient,
    SourceError,
    create_client,
    get_json,
)
from app.sources.scoreboard import ScoreboardGame
from app.sources.season_types import SeasonWindow
from app.storage.feeds import publish_by_id, read_by_id
from app.storage.state import StateStore, TeamIdentity

SOURCE = "https://example.com/source/"
SEASON = 2027
HOUR = dt.timedelta(hours=1)
SECOND = dt.timedelta(seconds=1)
D = dt.date
NOW = dt.datetime(2027, 1, 20, 17, 0, tzinfo=dt.UTC)
TODAY = NOW.date()


def utc(year: int, month: int, day: int, hour: int = 7, minute: int = 0) -> dt.datetime:
    return dt.datetime(year, month, day, hour, minute, tzinfo=dt.UTC)


def window(season_type: int, start: dt.datetime, end: dt.datetime) -> SeasonWindow:
    return SeasonWindow(season_type=season_type, start=start, end=end)


# The 2027 season: preseason from Sep 30, regular season Oct 20 to Apr 12, play-in
# Apr 12 to Apr 17, postseason Apr 17 to Jun 26 (US Eastern dates).
WINDOWS = SeasonWindows(
    preseason=window(1, utc(2026, 9, 30), utc(2026, 10, 20, 6, 59)),
    regular=window(2, utc(2026, 10, 20), utc(2027, 4, 12, 6, 59)),
    play_in=window(5, utc(2027, 4, 12), utc(2027, 4, 17, 6, 59)),
    postseason=window(3, utc(2027, 4, 17), utc(2027, 6, 26, 6, 59)),
)
NEXT_WINDOWS = SeasonWindows(
    preseason=window(1, utc(2027, 9, 29), utc(2027, 10, 19, 6, 59)),
    regular=window(2, utc(2027, 10, 19), utc(2028, 4, 10, 6, 59)),
    play_in=None,
    postseason=WINDOWS.postseason,
    next_season=True,
)
NOTHING_KNOWN = SeasonWindows(None, None, None, None)
WINDOW_TABLE = {
    (2027, 1): WINDOWS.preseason,
    (2027, 2): WINDOWS.regular,
    (2027, 5): WINDOWS.play_in,
    (2027, 3): WINDOWS.postseason,
    (2028, 1): NEXT_WINDOWS.preseason,
    (2028, 2): NEXT_WINDOWS.regular,
}


def sources(**changes: Any) -> HomeSources:
    base = HomeSources(
        season=SEASON,
        today=TODAY,
        windows=WINDOWS,
        calendar_days=[],
        all_star_date=None,
        cup=None,
        playoffs=None,
        window_days=None,
        next_games=None,
        last_day=None,
        last_day_games=None,
    )
    return replace(base, **changes)


def home(**changes: Any) -> HomeFeed:
    return build_home_feed(sources(**changes))


def game(
    game_id: str,
    status: GameStatus,
    start: dt.datetime,
    *,
    away: str = "RVR",
    home: str = "PKS",
    **extra: Any,
) -> ScoreboardGame:
    data: dict[str, Any] = {
        "id": game_id,
        "away": GameTeam(code=away, name="Away", city="Away City"),
        "home": GameTeam(code=home, name="Home", city="Home City"),
        "status": status,
        "start_time": start,
        "venue": "Arena",
    }
    if status in (GameStatus.LIVE, GameStatus.FINAL):
        data["line_score"] = LineScore(away=[20, 20], home=[18, 25])
        data["score"] = Score(away=40, home=43)
    if status is GameStatus.LIVE:
        data.update(period=2, clock="5:00")
    data.update(extra)
    return ScoreboardGame.model_validate(data)


def final(game_id: str, start: dt.datetime, **extra: Any) -> ScoreboardGame:
    return game(game_id, GameStatus.FINAL, start, **extra)


def mark(
    stage: PostseasonStage, round_: int | None = None, number: int | None = None
) -> GamePostseason:
    conference = (
        Conference.EAST
        if stage is PostseasonStage.PLAYIN
        or (stage is PostseasonStage.PLAYOFFS and round_ is not None)
        else None
    )
    return GamePostseason(
        stage=stage,
        round=round_,
        conference=conference,
        number=number,
        summary=None,
        play_in=PlayInGameKind.SEVEN_EIGHT if stage is PostseasonStage.PLAYIN else None,
        stakes=None,
    )


def series_game(number: int, day: dt.date, status: GameStatus) -> SeriesGame:
    return SeriesGame.model_construct(number=number, date=day, status=status)


def series(series_id: SeriesId, status: SeriesStatus, *games: SeriesGame) -> Series:
    return Series.model_construct(id=series_id, status=status, games=list(games))


def playoffs(*bracket: Series, season: str = "2026-27") -> PlayoffsFeed:
    return PlayoffsFeed.model_construct(season=season, bracket=list(bracket))


def conference_finals_done(*finals_games: SeriesGame) -> PlayoffsFeed:
    return playoffs(
        series(SeriesId.EAST_R3, SeriesStatus.COMPLETE),
        series(SeriesId.WEST_R3, SeriesStatus.COMPLETE),
        series(SeriesId.FINALS, SeriesStatus.UPCOMING, *finals_games),
    )


def stage(round_: CupRound, first: dt.date | None, last: dt.date | None) -> StageEntry:
    return StageEntry.model_construct(stage=round_, first_date=first, last_date=last)


CUP_START = D(2026, 11, 7)


def cup(
    *stages: StageEntry,
    season: str = "2026-27",
    cup_stage: CupStage = CupStage.GROUP,
    first_game_date: dt.date | None = CUP_START,
) -> CupFeed:
    return CupFeed.model_construct(
        season=season,
        stage=cup_stage,
        first_game_date=first_game_date,
        stages=list(stages),
    )


def keys(feed: HomeFeed) -> list[ComingUpKey]:
    return [item.key for item in feed.coming_up or []]


def statuses(feed: HomeFeed) -> dict[ComingUpKey, ComingUpStatus]:
    return {item.key: item.status for item in feed.coming_up or []}


# Scenario edges


def test_the_day_the_regular_season_starts_is_an_off_day_and_the_day_before_is_offseason() -> (
    None
):
    assert home(today=D(2026, 10, 20)).scenario is HomeScenario.OFF_DAY
    assert home(today=D(2026, 10, 19)).scenario is HomeScenario.OFFSEASON


BREAK_CALENDAR = [D(2027, 2, 11), D(2027, 2, 12), D(2027, 2, 21), D(2027, 2, 22)]


def test_the_day_before_the_all_star_date_is_the_all_star_break() -> None:
    def scenario(day: dt.date) -> HomeScenario:
        return home(
            today=day, calendar_days=BREAK_CALENDAR, all_star_date=D(2027, 2, 15)
        ).scenario

    assert break_days(BREAK_CALENDAR, D(2027, 2, 15)) == (
        D(2027, 2, 12),
        D(2027, 2, 21),
    )
    assert scenario(D(2027, 2, 12)) is HomeScenario.OFF_DAY
    assert scenario(D(2027, 2, 13)) is HomeScenario.ALL_STAR_BREAK
    assert scenario(D(2027, 2, 14)) is HomeScenario.ALL_STAR_BREAK
    assert scenario(D(2027, 2, 15)) is HomeScenario.ALL_STAR_BREAK
    assert scenario(D(2027, 2, 20)) is HomeScenario.ALL_STAR_BREAK
    assert scenario(D(2027, 2, 21)) is HomeScenario.OFF_DAY


def test_there_is_no_break_without_the_date_or_a_day_on_each_side() -> None:
    assert break_days(BREAK_CALENDAR, None) is None
    assert break_days([D(2027, 2, 12)], D(2027, 2, 15)) is None
    assert break_days([D(2027, 2, 21)], D(2027, 2, 15)) is None


def test_the_day_after_the_conference_finals_end_is_the_finals_preview() -> None:
    today = D(2027, 5, 25)

    assert home(today=today, playoffs=conference_finals_done()).scenario is (
        HomeScenario.FINALS_PREVIEW
    )
    incomplete = playoffs(
        series(SeriesId.EAST_R3, SeriesStatus.COMPLETE),
        series(SeriesId.WEST_R3, SeriesStatus.IN_PROGRESS),
    )
    assert home(today=today, playoffs=incomplete).scenario is HomeScenario.OFF_DAY
    for started in (GameStatus.LIVE, GameStatus.FINAL):
        feed = conference_finals_done(series_game(1, today, started))
        assert home(today=today, playoffs=feed).scenario is HomeScenario.OFF_DAY
    scheduled = conference_finals_done(series_game(1, today, GameStatus.SCHEDULED))
    assert home(today=today, playoffs=scheduled).scenario is (
        HomeScenario.FINALS_PREVIEW
    )


def test_the_first_day_after_the_postseason_is_offseason_and_its_last_day_is_not() -> (
    None
):
    assert home(today=D(2027, 6, 26)).scenario is HomeScenario.OFF_DAY
    assert home(today=D(2027, 6, 27)).scenario is HomeScenario.OFFSEASON


def test_offseason_after_the_postseason_uses_the_next_seasons_preseason_and_opening_night() -> (
    None
):
    feed = home(today=D(2027, 7, 10), windows=NEXT_WINDOWS)

    assert feed.scenario is HomeScenario.OFFSEASON
    assert keys(feed) == [ComingUpKey.PRESEASON, ComingUpKey.OPENING_NIGHT]
    assert feed.coming_up is not None
    assert [(i.start_date, i.end_date) for i in feed.coming_up] == [
        (D(2027, 9, 29), D(2027, 10, 19)),
        (D(2027, 10, 19), None),
    ]
    assert set(statuses(feed).values()) == {ComingUpStatus.UPCOMING}


def test_with_no_season_type_known_the_scenario_is_an_off_day() -> None:
    feed = home(windows=NOTHING_KNOWN)

    assert feed.scenario is HomeScenario.OFF_DAY
    assert feed.coming_up is None


# Coming up


def test_coming_up_is_null_when_the_next_event_is_15_days_away() -> None:
    assert COMING_UP_DAYS == 14
    far = TODAY + dt.timedelta(days=15)

    assert home(all_star_date=far).coming_up is None


def test_coming_up_holds_the_event_14_days_away() -> None:
    near = TODAY + dt.timedelta(days=14)

    feed = home(all_star_date=near)

    assert keys(feed) == [ComingUpKey.ALL_STAR]
    assert statuses(feed) == {ComingUpKey.ALL_STAR: ComingUpStatus.UPCOMING}


def test_an_event_with_no_date_never_appears() -> None:
    nodate = cup(
        stage(CupRound.GROUP, None, None),
        stage(CupRound.QUARTERFINALS, None, None),
        stage(CupRound.SEMIFINALS, None, None),
        stage(CupRound.CHAMPIONSHIP, None, None),
    )

    feed = home(today=D(2027, 4, 20), cup=nodate, playoffs=conference_finals_done())

    assert keys(feed) == [ComingUpKey.PLAY_IN, ComingUpKey.PLAYOFFS]
    assert home(today=D(2027, 4, 20), cup=None).coming_up == feed.coming_up


def test_item_status_is_upcoming_before_now_during_and_done_after_an_event() -> None:
    day = D(2027, 2, 15)
    end = D(2027, 2, 17)

    assert item_status(day, None, D(2027, 2, 14)) is ComingUpStatus.UPCOMING
    assert item_status(day, None, day) is ComingUpStatus.NOW
    assert item_status(day, None, D(2027, 2, 16)) is ComingUpStatus.DONE
    assert item_status(day, end, D(2027, 2, 14)) is ComingUpStatus.UPCOMING
    assert item_status(day, end, day) is ComingUpStatus.NOW
    assert item_status(day, end, end) is ComingUpStatus.NOW
    assert item_status(day, end, D(2027, 2, 18)) is ComingUpStatus.DONE


def test_a_done_item_is_listed_only_while_the_window_is_open_and_within_14_days() -> (
    None
):
    # The play-in ended Apr 17; the postseason is now through Jun 26.
    assert ComingUpKey.PLAY_IN in keys(home(today=D(2027, 5, 1)))
    assert ComingUpKey.PLAY_IN not in keys(home(today=D(2027, 5, 2)))
    assert ComingUpKey.PLAYOFFS in keys(home(today=D(2027, 5, 2)))
    # A done item alone never opens the window.
    assert home(today=D(2027, 2, 25), all_star_date=D(2027, 2, 15)).coming_up is None
    # An item that ended 14 days ago with another one now is listed.
    open_window = home(today=D(2027, 2, 15), all_star_date=D(2027, 2, 15))
    assert statuses(open_window) == {ComingUpKey.ALL_STAR: ComingUpStatus.NOW}


def test_coming_up_is_in_date_order_and_ties_follow_the_order_of_the_keys() -> None:
    feed = home(
        today=D(2027, 4, 12),
        all_star_date=D(2027, 4, 12),
        playoffs=playoffs(
            series(
                SeriesId.FINALS,
                SeriesStatus.UPCOMING,
                series_game(1, D(2027, 6, 3), GameStatus.SCHEDULED),
            )
        ),
    )

    assert keys(feed) == [
        ComingUpKey.ALL_STAR,
        ComingUpKey.PLAY_IN,
        ComingUpKey.PLAYOFFS,
    ]
    assert D(2027, 4, 12) == (feed.coming_up or [])[0].start_date


def test_the_finals_item_is_the_date_of_the_first_finals_game() -> None:
    finals = playoffs(
        series(
            SeriesId.FINALS,
            SeriesStatus.UPCOMING,
            series_game(2, D(2027, 6, 6), GameStatus.SCHEDULED),
            series_game(1, D(2027, 6, 3), GameStatus.SCHEDULED),
        )
    )

    feed = home(today=D(2027, 5, 30), playoffs=finals)

    assert (feed.coming_up or [])[-1].key is ComingUpKey.FINALS
    assert (feed.coming_up or [])[-1].start_date == D(2027, 6, 3)


def test_in_the_offseason_coming_up_holds_the_preseason_and_opening_night() -> None:
    both = home(today=D(2026, 8, 1))
    assert keys(both) == [ComingUpKey.PRESEASON, ComingUpKey.OPENING_NIGHT]

    no_preseason = home(today=D(2026, 8, 1), windows=replace(WINDOWS, preseason=None))
    assert keys(no_preseason) == [ComingUpKey.OPENING_NIGHT]

    none = home(
        today=D(2026, 8, 1), windows=replace(WINDOWS, preseason=None, regular=None)
    )
    assert none.scenario is HomeScenario.OFF_DAY
    assert none.coming_up is None
    postseason_only = home(
        today=D(2027, 7, 1), windows=SeasonWindows(None, None, None, WINDOWS.postseason)
    )
    assert postseason_only.scenario is HomeScenario.OFFSEASON
    assert postseason_only.coming_up is None


def test_a_cup_feed_of_another_season_gives_no_cup_item() -> None:
    stages = (
        stage(CupRound.GROUP, D(2026, 11, 7), D(2026, 12, 2)),
        stage(CupRound.QUARTERFINALS, D(2026, 12, 8), D(2026, 12, 9)),
        stage(CupRound.SEMIFINALS, D(2026, 12, 11), D(2026, 12, 11)),
        stage(CupRound.CHAMPIONSHIP, D(2026, 12, 14), D(2026, 12, 14)),
    )
    today = D(2026, 12, 1)

    other = home(today=today, cup=cup(*stages, season="2025-26"))
    this = home(today=today, cup=cup(*stages))

    assert other.coming_up is None
    assert keys(this) == [
        ComingUpKey.CUP_GROUP_STAGE,
        ComingUpKey.CUP_KNOCKOUT,
        ComingUpKey.CUP_FINAL,
    ]
    assert this.coming_up is not None
    assert [(i.start_date, i.end_date) for i in this.coming_up] == [
        (D(2026, 11, 7), D(2026, 12, 2)),
        (D(2026, 12, 8), D(2026, 12, 11)),
        (D(2026, 12, 14), None),
    ]
    assert statuses(this)[ComingUpKey.CUP_GROUP_STAGE] is ComingUpStatus.NOW


def test_the_cup_knockout_item_uses_the_one_round_that_has_dates() -> None:
    only_semis = cup(
        stage(CupRound.QUARTERFINALS, None, None),
        stage(CupRound.SEMIFINALS, D(2026, 12, 11), D(2026, 12, 12)),
    )
    only_quarters = cup(
        stage(CupRound.QUARTERFINALS, D(2026, 12, 8), D(2026, 12, 9)),
        stage(CupRound.SEMIFINALS, None, None),
    )

    first = home(today=D(2026, 12, 1), cup=only_semis)
    second = home(today=D(2026, 12, 1), cup=only_quarters)

    assert (first.coming_up or [])[0].start_date == D(2026, 12, 11)
    assert (first.coming_up or [])[0].end_date == D(2026, 12, 12)
    assert (second.coming_up or [])[0].start_date == D(2026, 12, 8)
    assert (second.coming_up or [])[0].end_date == D(2026, 12, 9)


# Next game


def test_next_game_is_null_when_no_game_day_falls_in_the_next_14_days() -> None:
    day = TODAY + dt.timedelta(days=15)
    games = [game("g1", GameStatus.SCHEDULED, NOW + dt.timedelta(days=15))]

    assert next_game_day([day], TODAY) is None
    assert next_game_day([TODAY], TODAY) is None
    edge = day - dt.timedelta(days=1)
    assert next_game_day([edge], TODAY) == edge
    assert home(calendar_days=[day], next_games=games).next_game is None
    assert home(calendar_days=[], next_games=games).next_game is None


def test_next_game_takes_the_first_tip_off_and_its_broadcast_and_counts_the_games() -> (
    None
):
    day = D(2027, 1, 22)
    games = [
        game("g1", GameStatus.SCHEDULED, utc(2027, 1, 23, 2), broadcast="Channel Late"),
        game(
            "g2", GameStatus.SCHEDULED, utc(2027, 1, 23, 0), broadcast="Channel Example"
        ),
        game("g3", GameStatus.POSTPONED, utc(2027, 1, 22, 23)),
        game("g4", GameStatus.CANCELED, utc(2027, 1, 22, 22)),
    ]

    feed = home(calendar_days=[day], next_games=games)

    assert feed.next_game is not None
    assert feed.next_game.date == day
    assert feed.next_game.first_tip_off == utc(2027, 1, 23, 0)
    assert feed.next_game.broadcast == "Channel Example"
    assert feed.next_game.game_count == 2


def test_next_game_is_null_when_every_game_of_the_day_is_postponed_or_unread() -> None:
    day = D(2027, 1, 22)
    games = [game("g3", GameStatus.POSTPONED, utc(2027, 1, 22, 23))]

    assert home(calendar_days=[day], next_games=games).next_game is None
    assert home(calendar_days=[day], next_games=None).next_game is None


def test_in_games_window_follows_the_games_job_shown_days() -> None:
    day = D(2027, 1, 22)
    games = [game("g1", GameStatus.SCHEDULED, utc(2027, 1, 23, 0))]
    shown = [D(2027, 1, 17) + dt.timedelta(days=n) for n in range(7)]

    inside = home(calendar_days=[day], next_games=games, window_days=shown)
    outside = home(calendar_days=[day], next_games=games, window_days=shown[:3])
    unknown = home(calendar_days=[day], next_games=games, window_days=None)

    assert inside.next_game is not None and inside.next_game.in_games_window
    assert outside.next_game is not None and not outside.next_game.in_games_window
    assert unknown.next_game is not None and not unknown.next_game.in_games_window


# Last games


def test_last_games_title_is_last_night_for_yesterday() -> None:
    title = last_games_title(HomeScenario.OFF_DAY, D(2027, 1, 19), TODAY)

    assert (title.key, title.days) == (LastGamesTitleKey.LAST_NIGHT, None)


def test_last_games_title_is_days_ago_with_the_count() -> None:
    title = last_games_title(HomeScenario.OFF_DAY, D(2027, 1, 18), TODAY)

    assert (title.key, title.days) == (LastGamesTitleKey.DAYS_AGO, 2)
    assert last_games_title(HomeScenario.OFF_DAY, D(2027, 1, 10), TODAY).days == 10


def test_last_games_in_the_all_star_break_is_the_last_day_before_the_break() -> None:
    today = D(2027, 2, 14)
    around = break_days(BREAK_CALENDAR, D(2027, 2, 15))
    games = [final("g1", utc(2027, 2, 13, 1))]

    assert last_games_day(
        HomeScenario.ALL_STAR_BREAK, BREAK_CALENDAR, today, around
    ) == D(2027, 2, 12)
    feed = home(
        today=today,
        calendar_days=BREAK_CALENDAR,
        all_star_date=D(2027, 2, 15),
        last_day=D(2027, 2, 12),
        last_day_games=games,
    )
    assert feed.last_games is not None
    assert feed.last_games.date == D(2027, 2, 12)
    assert feed.last_games.title.key is LastGamesTitleKey.BEFORE_THE_BREAK


def test_last_games_in_the_finals_preview_is_titled_conference_finals() -> None:
    today = D(2027, 5, 25)
    feed = home(
        today=today,
        playoffs=conference_finals_done(),
        calendar_days=[D(2027, 5, 22)],
        last_day=D(2027, 5, 22),
        last_day_games=[final("g1", utc(2027, 5, 23, 1))],
    )

    assert feed.scenario is HomeScenario.FINALS_PREVIEW
    assert feed.last_games is not None
    assert feed.last_games.title.key is LastGamesTitleKey.CONFERENCE_FINALS
    assert feed.last_games.title.days is None


def test_last_games_in_the_offseason_is_titled_last_games_played_and_reads_the_previous_calendar() -> (
    None
):
    today = D(2026, 8, 1)
    previous = [D(2026, 6, 20), D(2026, 6, 18)]

    assert last_games_day(HomeScenario.OFFSEASON, sorted(previous), today, None) == D(
        2026, 6, 20
    )
    feed = home(
        today=today,
        calendar_days=sorted(previous),
        last_day=D(2026, 6, 20),
        last_day_games=[final("g1", utc(2026, 6, 21, 1))],
    )
    assert feed.scenario is HomeScenario.OFFSEASON
    assert feed.last_games is not None
    assert feed.last_games.title.key is LastGamesTitleKey.LAST_GAMES_PLAYED


def test_last_games_day_is_null_with_no_calendar_day_before_today() -> None:
    assert last_games_day(HomeScenario.OFF_DAY, [D(2027, 1, 21)], TODAY, None) is None
    assert last_games_day(HomeScenario.ALL_STAR_BREAK, [], TODAY, None) is None
    assert home(last_day=None, last_day_games=None).last_games is None


def test_last_games_keep_only_final_games_without_an_all_star_mark() -> None:
    games = [
        game("live", GameStatus.LIVE, utc(2027, 1, 20, 0)),
        game("scheduled", GameStatus.SCHEDULED, utc(2027, 1, 20, 1)),
        final(
            "star",
            utc(2027, 1, 20, 2),
            all_star=GameAllStar(round_label="Round", championship=False),
        ),
        final("late", utc(2027, 1, 20, 4), away="PKS", home="RVR"),
        final("early", utc(2027, 1, 20, 3)),
    ]

    feed = home(last_day=D(2027, 1, 19), last_day_games=games)

    assert feed.last_games is not None
    assert [g.id for g in feed.last_games.games] == ["early", "late"]
    assert feed.last_games.games[0].winner is not None
    assert feed.last_games.games[0].away.logo is None
    assert feed.last_games.games[0].accent is None
    assert home(last_day=D(2027, 1, 19), last_day_games=games[:3]).last_games is None


@pytest.mark.parametrize(
    ("extra", "label", "number"),
    [
        ({}, LastGameLabel.FINAL, None),
        ({"period": 4}, LastGameLabel.FINAL, None),
        ({"period": 5}, LastGameLabel.FINAL_OVERTIME, None),
        ({"postseason": mark(PostseasonStage.PLAYIN)}, LastGameLabel.PLAY_IN, None),
        (
            {"postseason": mark(PostseasonStage.PLAYOFFS, 1, 3)},
            LastGameLabel.FIRST_ROUND,
            3,
        ),
        (
            {"postseason": mark(PostseasonStage.PLAYOFFS, 2, 6)},
            LastGameLabel.CONFERENCE_SEMIFINALS,
            6,
        ),
        (
            {"postseason": mark(PostseasonStage.PLAYOFFS, 3, None)},
            LastGameLabel.CONFERENCE_FINALS,
            None,
        ),
        (
            {"postseason": mark(PostseasonStage.FINALS, 4, 7), "period": 5},
            LastGameLabel.FINALS,
            7,
        ),
        (
            {"postseason": mark(PostseasonStage.PLAYOFFS, None, 2), "period": 6},
            LastGameLabel.FINAL_OVERTIME,
            None,
        ),
    ],
    ids=[
        "final",
        "regulation",
        "overtime",
        "play-in",
        "first round",
        "semifinals",
        "conference finals without number",
        "finals",
        "playoff mark without round",
    ],
)
def test_game_labels_cover_final_overtime_play_in_each_round_and_the_finals(
    extra: dict[str, Any], label: LastGameLabel, number: int | None
) -> None:
    assert game_label(final("g1", NOW, **extra)) == (label, number)


def test_an_invalid_feed_is_wrapped_in_a_build_error() -> None:
    bad = replace(sources(), season=1)

    with pytest.raises(HomeBuildError) as raised:
        build_home_feed(bad)

    assert raised.value.reason.startswith("invalid feed: ")


# The kit


class Nothing(FeedModel):
    id: str


class StubStars:
    def __init__(self) -> None:
        self.season: int | None = SEASON
        self.identities: dict[str, TeamIdentity] = {}

    def current_season(self) -> int | None:
        return self.season

    def team_identities(self) -> dict[str, TeamIdentity]:
        return dict(self.identities)


class StubStored:
    def __init__(self) -> None:
        self.feed: Any = None

    def stored(self) -> Any:
        return self.feed


async def no_detail(
    client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
) -> GameDetail:
    raise SourceError("test", "no detail")


class HomeKit:
    """A games job, a feed cache and the home kind over one client and one clock.

    Every fake adapter reads one URL through the source cache from a counted respx
    route, so route calls are real source requests. The calendar, day and playoffs
    kinds are stand-ins that record their builds.
    """

    def __init__(self, path: Path, now: dt.datetime = NOW) -> None:
        self.path = path
        self.clock = [now]
        self.store = StateStore(path)
        self.store.migrate()
        self.settings = Settings(_env_file=None, data_dir=path)  # type: ignore[call-arg]
        self.client = create_client(self.store, clock=lambda: self.clock[0])
        self.requests: list[str] = []
        self.calls: list[str] = []
        self.built: list[tuple[str, str]] = []
        self.failing: set[str] = set()
        self.scoreboard: dict[dt.date, list[ScoreboardGame]] = {}
        self.calendars: dict[int, list[dt.date]] = {}
        self.windows = dict(WINDOW_TABLE)
        respx.get(url__startswith=SOURCE).mock(side_effect=self.answer)
        self.stars = StubStars()
        self.cup = StubStored()
        self.playoffs = StubStored()
        self.cache = FeedCache(
            path,
            self.store,
            clock=lambda: self.clock[0],
            identities=self.stars.team_identities,
        )
        self.games = GamesJob(
            self.settings,
            self.store,
            self.client,
            fetch_games=self.fetch_games,
            fetch_game_detail=no_detail,
        )
        self.home = HomeFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            self.games,
            cast(StarsJob, self.stars),
            cast(CupFeeds, self.cup),
            cast(PlayoffsFeeds, self.playoffs),
            fetch_season_type=self.fetch_season_type,
            fetch_games=self.fetch_next_day,
        )
        self.cache.register(
            FeedKind(
                "calendars",
                CalendarFeed,
                check=lambda feed_id: IdStatus.KNOWN,
                build=self.build_calendar,
                is_fresh=lambda feed, built_at, now: now - built_at < 24 * HOUR,
                keep=lambda feed_id: True,
            )
        )
        self.cache.register(
            FeedKind(
                "days",
                DayFeed,
                check=self.check_day,
                build=self.build_day,
                is_fresh=lambda feed, built_at, now: True,
                keep=lambda feed_id: True,
            )
        )
        self.cache.register(
            FeedKind(
                "playoffs",
                Nothing,
                check=lambda feed_id: IdStatus.KNOWN,
                build=self.build_playoffs,
                is_fresh=lambda feed, built_at, now: False,
                keep=lambda feed_id: True,
            )
        )

    def answer(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request.url.path.removeprefix("/source/"))
        return httpx.Response(200, json={"ok": True})

    async def read(self, name: str, fresh: Freshness) -> None:
        self.calls.append(name)
        if name in self.failing:
            raise SourceError("test", f"{name} is down")
        await get_json(self.client, SOURCE + name, source="test", fresh=fresh)

    def requested(self, prefix: str) -> int:
        return sum(1 for name in self.requests if name.startswith(prefix))

    async def fetch_games(
        self, client: SourceClient, day: dt.date, settings: Settings
    ) -> list[ScoreboardGame]:
        return list(self.scoreboard.get(day, []))

    async def fetch_season_type(
        self, client: SourceClient, season: int, season_type: int, settings: Settings
    ) -> SeasonWindow:
        await self.read(f"types/{season}/{season_type}", HOUR)
        found = self.windows.get((season, season_type))
        if found is None:
            raise SourceError("test", "no such season type")
        return found

    async def fetch_next_day(
        self, client: SourceClient, day: dt.date, settings: Settings
    ) -> list[ScoreboardGame]:
        await self.read(f"day/{day.isoformat()}", 30 * SECOND)
        return list(self.scoreboard.get(day, []))

    async def build_calendar(self, feed_id: str) -> CalendarFeed:
        self.built.append(("calendars", feed_id))
        if "calendar" in self.failing:
            raise SourceError("test", "calendar is down")
        return calendar_of(
            self.clock[0], int(feed_id), self.calendars.get(int(feed_id), [])
        )

    def check_day(self, feed_id: str) -> IdStatus:
        shown = self.games.shown_days() or []
        return (
            IdStatus.UNKNOWN
            if dt.date.fromisoformat(feed_id) in shown
            else IdStatus.KNOWN
        )

    async def build_day(self, feed_id: str) -> DayFeed:
        self.built.append(("days", feed_id))
        if "day-feed" in self.failing:
            raise SourceError("test", "day feed is down")
        day = dt.date.fromisoformat(feed_id)
        return build_day_feed(
            self.clock[0],
            day,
            SEASON,
            self.scoreboard.get(day, []),
            lambda found: "https://example.com/search",
        )

    async def build_playoffs(self, feed_id: str) -> Nothing:
        self.built.append(("playoffs", feed_id))
        raise SourceError("test", "playoffs is down")

    async def settle(self) -> None:
        while self.cache.in_flight:
            await next(iter(self.cache.in_flight.values()))
            await asyncio.sleep(0)
        await asyncio.sleep(0)

    async def run_games(self, at: dt.datetime | None = None) -> None:
        if at is not None:
            self.clock[0] = at
        await self.games.run(self.clock[0])
        await self.settle()

    async def serve(self, at: dt.datetime | None = None) -> bytes:
        if at is not None:
            self.clock[0] = at
        body = await self.cache.serve(KIND, FEED_ID)
        await self.settle()
        return body

    def stored(self) -> HomeFeed | None:
        body = read_by_id(self.path, KIND, FEED_ID)
        return None if body is None else HomeFeed.model_validate_json(body)

    def last_build(self) -> dt.datetime | None:
        state = self.store.feed_build(KIND, FEED_ID)
        return None if state is None else state.last_build

    def store_calendar(self, season: int, days: list[dt.date]) -> None:
        feed = calendar_of(self.clock[0], season, days)
        assert publish_by_id(self.path, "calendars", CalendarFeed, str(season), feed)

    async def ensure(self, kind: str, feed_id: str) -> None:
        """A recording ensure that stores the calendar a build would."""
        self.built.append((kind, feed_id))
        if kind == "calendars" and self.calendars.get(int(feed_id)):
            self.store_calendar(int(feed_id), self.calendars[int(feed_id)])

    async def prepare_at(self, at: dt.datetime) -> list[tuple[str, str]]:
        self.clock[0] = at
        self.built.clear()
        await self.home.prepare(FEED_ID, cast(Ensure, self.ensure))
        return list(self.built)


def calendar_of(
    generated_at: dt.datetime, season: int, days: list[dt.date]
) -> CalendarFeed:
    moments = [dt.datetime.combine(day, dt.time(17), dt.UTC) for day in days]
    return build_calendar_feed(generated_at, season, moments, [], SEASON)


def at_noon(day: dt.date) -> dt.datetime:
    """Noon US Eastern of a winter or summer day, as UTC (UTC-5 until Mar 14, else UTC-4)."""
    offset = 5 if day < D(day.year, 3, 14) or day >= D(day.year, 11, 7) else 4
    return dt.datetime.combine(day, dt.time(12 + offset), dt.UTC)


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


@pytest.fixture
def kit(tmp_path: Path) -> HomeKit:
    return HomeKit(tmp_path)


# Next game and last games through the kit


@pytest.mark.anyio
async def test_a_next_game_day_inside_the_window_is_read_from_the_games_job_memory_with_no_request(
    kit: HomeKit,
) -> None:
    kit.calendars[SEASON] = [D(2027, 1, 14), D(2027, 1, 22)]
    kit.scoreboard[D(2027, 1, 22)] = [
        game(
            "g1", GameStatus.SCHEDULED, utc(2027, 1, 23, 0), broadcast="Channel Example"
        )
    ]
    await kit.run_games()

    await kit.serve()

    feed = kit.stored()
    assert feed is not None and feed.next_game is not None
    assert feed.next_game.in_games_window is True
    assert feed.next_game.broadcast == "Channel Example"
    assert kit.requested("day/") == 0


@pytest.mark.anyio
async def test_last_games_inside_the_window_come_from_the_games_job_memory(
    kit: HomeKit,
) -> None:
    kit.calendars[SEASON] = [D(2027, 1, 19)]
    kit.scoreboard[D(2027, 1, 19)] = [final("g1", utc(2027, 1, 20, 0))]
    await kit.run_games()

    await kit.serve()

    feed = kit.stored()
    assert feed is not None and feed.last_games is not None
    assert [g.id for g in feed.last_games.games] == ["g1"]
    assert feed.last_games.title.key is LastGamesTitleKey.LAST_NIGHT
    assert ("days", "2027-01-19") not in kit.built


async def build_without_the_memory(kit: HomeKit, *, days_set: bool) -> None:
    kit.calendars[SEASON] = [D(2027, 1, 19), D(2027, 1, 22)]
    kit.scoreboard[D(2027, 1, 19)] = [final("g1", utc(2027, 1, 20, 0))]
    kit.scoreboard[D(2027, 1, 22)] = [
        game("g2", GameStatus.SCHEDULED, utc(2027, 1, 23, 0))
    ]
    if days_set:
        await kit.run_games()
    else:
        assert kit.games.shown_days() is None
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(kit.games, "shown_games", lambda: None)
        await kit.serve()
        feed = kit.stored()
        assert feed is not None
        assert feed.last_games is None
        assert (feed.next_game is None) is days_set
        built_at = kit.last_build()
        assert built_at is not None
        # Still fresh while the memory is not loaded, until the short freshness ends.
        assert kit.home.is_fresh(feed, built_at, built_at + MEMORY_FRESH_FOR - SECOND)
        assert not kit.home.is_fresh(feed, built_at, built_at + MEMORY_FRESH_FOR)
    if not days_set:
        await kit.run_games()
    # The memory is loaded: the feed is stale before the day change.
    assert not kit.home.is_fresh(feed, built_at, built_at + SECOND)
    await kit.serve()
    await kit.serve()
    rebuilt = kit.stored()
    assert rebuilt is not None
    assert rebuilt.last_games is not None
    assert [g.id for g in rebuilt.last_games.games] == ["g1"]
    assert rebuilt.next_game is not None and rebuilt.next_game.date == D(2027, 1, 22)
    assert kit.home.is_fresh(rebuilt, kit.clock[0], kit.clock[0])


@pytest.mark.anyio
async def test_a_build_with_the_days_shown_but_no_games_memory_is_rebuilt_once_it_loads(
    kit: HomeKit,
) -> None:
    await build_without_the_memory(kit, days_set=True)


@pytest.mark.anyio
async def test_a_build_before_the_games_job_ran_is_rebuilt_once_the_memory_loads(
    kit: HomeKit,
) -> None:
    await build_without_the_memory(kit, days_set=False)


@pytest.mark.anyio
async def test_a_feed_stored_by_an_earlier_process_is_stale_once_the_memory_loads(
    tmp_path: Path,
) -> None:
    first = HomeKit(tmp_path)
    first.calendars[SEASON] = [D(2027, 1, 10)]
    await first.serve()
    feed = first.stored()
    built_at = first.last_build()
    assert feed is not None and built_at is not None

    restarted = HomeKit(tmp_path)
    assert restarted.games.shown_games() is None
    assert restarted.home.is_fresh(feed, built_at, built_at + MEMORY_FRESH_FOR - SECOND)
    assert not restarted.home.is_fresh(feed, built_at, built_at + MEMORY_FRESH_FOR)
    await restarted.run_games()
    assert not restarted.home.is_fresh(feed, built_at, built_at + SECOND)


@pytest.mark.anyio
async def test_last_games_outside_the_window_come_from_the_day_feed_built_first(
    kit: HomeKit,
) -> None:
    kit.calendars[SEASON] = [D(2027, 1, 14)]
    kit.scoreboard[D(2027, 1, 14)] = [final("g1", utc(2027, 1, 15, 0))]
    await kit.run_games()

    await kit.serve()

    feed = kit.stored()
    assert feed is not None and feed.last_games is not None
    assert [g.id for g in feed.last_games.games] == ["g1"]
    assert feed.last_games.title.key is LastGamesTitleKey.DAYS_AGO
    assert feed.last_games.title.days == 6
    assert kit.built.index(("days", "2027-01-14")) > kit.built.index(
        ("calendars", "2027")
    )


# Dependencies


@pytest.mark.anyio
async def test_the_cup_feed_is_built_first_only_from_its_first_game_date_to_its_championship(
    kit: HomeKit,
) -> None:
    kit.calendars[SEASON] = [D(2026, 10, 25)]
    kit.cup.feed = cup(cup_stage=CupStage.GROUP, first_game_date=D(2026, 11, 7))

    def built_cup(built: list[tuple[str, str]]) -> bool:
        return ("cup", "league") in built

    assert not built_cup(await kit.prepare_at(at_noon(D(2026, 11, 6))))
    assert built_cup(await kit.prepare_at(at_noon(D(2026, 11, 7))))
    kit.cup.feed = cup(cup_stage=CupStage.CHAMPIONSHIP, first_game_date=D(2026, 11, 7))
    assert built_cup(await kit.prepare_at(at_noon(D(2026, 12, 20))))
    kit.cup.feed = cup(cup_stage=CupStage.COMPLETE, first_game_date=D(2026, 11, 7))
    assert not built_cup(await kit.prepare_at(at_noon(D(2026, 12, 20))))
    kit.cup.feed = cup(season="2025-26", first_game_date=D(2025, 11, 7))
    assert not built_cup(await kit.prepare_at(at_noon(D(2026, 11, 20))))
    kit.cup.feed = cup(first_game_date=None)
    assert not built_cup(await kit.prepare_at(at_noon(D(2026, 11, 20))))
    kit.cup.feed = None
    assert not built_cup(await kit.prepare_at(at_noon(D(2026, 11, 20))))


@pytest.mark.anyio
async def test_the_all_star_feed_is_built_first_only_from_february_1_to_march_7(
    kit: HomeKit,
) -> None:
    kit.calendars[SEASON] = [D(2027, 1, 10)]
    expected = {
        D(2027, 1, 31): False,
        D(2027, 2, 1): True,
        D(2027, 3, 7): True,
        D(2027, 3, 8): False,
    }

    for day, wanted in expected.items():
        built = await kit.prepare_at(at_noon(day))
        assert (("all-star", "league") in built) is wanted, day


@pytest.mark.anyio
async def test_the_playoffs_feed_is_built_first_only_from_the_play_in_start_to_the_postseason_end(
    kit: HomeKit,
) -> None:
    kit.calendars[SEASON] = [D(2027, 4, 1)]
    expected = {
        D(2027, 4, 11): False,
        D(2027, 4, 12): True,
        D(2027, 6, 26): True,
        D(2027, 6, 27): False,
    }

    for day, wanted in expected.items():
        built = await kit.prepare_at(at_noon(day))
        assert (("playoffs", "league") in built) is wanted, day


@pytest.mark.anyio
async def test_the_playoffs_feed_is_not_built_first_when_a_season_type_is_unknown(
    kit: HomeKit,
) -> None:
    kit.calendars[SEASON] = [D(2027, 4, 1)]
    del kit.windows[(2027, 5)]

    built = await kit.prepare_at(at_noon(D(2027, 5, 1)))

    assert ("playoffs", "league") not in built


@pytest.mark.anyio
async def test_the_day_feed_is_built_first_only_for_a_day_outside_the_games_window(
    kit: HomeKit,
) -> None:
    kit.calendars[SEASON] = [D(2027, 1, 14), D(2027, 1, 19)]
    await kit.run_games()

    # Yesterday is inside the window.
    built = await kit.prepare_at(at_noon(D(2027, 1, 20)))
    assert not [item for item in built if item[0] == "days"]
    # Three days later the last calendar day, Jan 19, has left the window.
    await kit.run_games(at_noon(D(2027, 1, 23)))
    built = await kit.prepare_at(at_noon(D(2027, 1, 23)))
    assert ("days", "2027-01-19") in built


@pytest.mark.anyio
async def test_the_day_feed_is_built_first_for_a_day_outside_the_days_shown_before_the_games_job_runs(
    kit: HomeKit,
) -> None:
    kit.calendars[SEASON] = [D(2027, 1, 10), D(2027, 1, 19)]

    built = await kit.prepare_at(at_noon(D(2027, 1, 20)))
    assert [item for item in built if item[0] == "days"] == []
    kit.calendars[SEASON] = [D(2027, 1, 10)]
    built = await kit.prepare_at(at_noon(D(2027, 1, 20)))
    assert ("days", "2027-01-10") in built


@pytest.mark.anyio
async def test_the_calendar_is_always_built_first_and_the_previous_one_only_with_no_earlier_day(
    kit: HomeKit,
) -> None:
    kit.calendars[SEASON] = [D(2027, 1, 10)]
    built = await kit.prepare_at(at_noon(D(2027, 1, 20)))
    assert [item for item in built if item[0] == "calendars"] == [("calendars", "2027")]

    kit.calendars[SEASON] = [D(2027, 1, 25)]
    built = await kit.prepare_at(at_noon(D(2027, 1, 20)))
    assert [item for item in built if item[0] == "calendars"] == [
        ("calendars", "2027"),
        ("calendars", "2026"),
    ]


@pytest.mark.anyio
async def test_prepare_does_nothing_while_the_season_is_not_known(kit: HomeKit) -> None:
    kit.stars.season = None

    assert await kit.prepare_at(NOW) == []
    assert kit.requests == []


# Budget and failures


def test_the_budgets_are_4_season_types_and_1_scoreboard_day() -> None:
    assert (SEASON_TYPE_READS, SCOREBOARD_READS) == (4, 1)


@pytest.mark.anyio
async def test_a_build_in_season_sends_at_most_4_season_type_reads_and_1_scoreboard_read(
    kit: HomeKit,
) -> None:
    kit.calendars[SEASON] = [D(2027, 1, 19), D(2027, 1, 27)]
    kit.scoreboard[D(2027, 1, 19)] = [final("g0", utc(2027, 1, 20, 0))]
    kit.scoreboard[D(2027, 1, 27)] = [
        game("g1", GameStatus.SCHEDULED, utc(2027, 1, 28, 0))
    ]
    await kit.run_games()

    await kit.serve()

    assert kit.requested("types/") == 4
    assert kit.requested("day/") == 1
    assert kit.requests.count("day/2027-01-27") == 1
    feed = kit.stored()
    assert feed is not None and feed.next_game is not None
    assert feed.next_game.date == D(2027, 1, 27)
    assert feed.next_game.in_games_window is False
    assert feed.last_games is not None


@pytest.mark.anyio
async def test_a_build_after_the_postseason_sends_3_season_type_reads(
    tmp_path: Path,
) -> None:
    kit = HomeKit(tmp_path, at_noon(D(2027, 7, 10)))
    kit.calendars[SEASON] = [D(2027, 6, 20)]

    await kit.serve()

    assert sorted(
        request for request in kit.requests if request.startswith("types/")
    ) == [
        "types/2027/3",
        "types/2028/1",
        "types/2028/2",
    ]
    feed = kit.stored()
    assert feed is not None
    assert feed.scenario is HomeScenario.OFFSEASON
    assert keys(feed) == [ComingUpKey.PRESEASON, ComingUpKey.OPENING_NIGHT]
    assert feed.last_games is None or feed.last_games.title.key is (
        LastGamesTitleKey.LAST_GAMES_PLAYED
    )


@pytest.mark.anyio
async def test_a_failed_season_type_read_nulls_only_what_it_feeds_and_the_feed_is_stored(
    tmp_path: Path,
) -> None:
    kit = HomeKit(tmp_path, at_noon(D(2027, 4, 20)))
    kit.calendars[SEASON] = [D(2027, 4, 19)]
    kit.failing.add("types/2027/5")

    await kit.serve()

    feed = kit.stored()
    assert feed is not None
    assert keys(feed) == [ComingUpKey.PLAYOFFS]
    assert ("playoffs", "league") not in kit.built
    assert feed.scenario is HomeScenario.OFF_DAY


@pytest.mark.anyio
async def test_every_failed_season_type_read_still_stores_a_feed(
    tmp_path: Path,
) -> None:
    kit = HomeKit(tmp_path, at_noon(D(2027, 4, 20)))
    kit.calendars[SEASON] = [D(2027, 4, 19)]
    kit.failing |= {f"types/2027/{n}" for n in (1, 2, 3, 5)}

    await kit.serve()

    feed = kit.stored()
    assert feed is not None
    assert feed.coming_up is None
    assert feed.scenario is HomeScenario.OFF_DAY


@pytest.mark.anyio
async def test_a_failed_scoreboard_read_gives_a_null_next_game_and_the_feed_is_stored(
    kit: HomeKit,
) -> None:
    kit.calendars[SEASON] = [D(2027, 1, 19), D(2027, 1, 27)]
    kit.failing.add("day/2027-01-27")
    await kit.run_games()

    await kit.serve()

    feed = kit.stored()
    assert feed is not None
    assert feed.next_game is None
    assert feed.last_games is None or feed.last_games.date == D(2027, 1, 19)


@pytest.mark.anyio
async def test_a_failed_dependency_gives_null_fields_and_never_a_503(
    tmp_path: Path,
) -> None:
    for name in "abc":
        (tmp_path / name).mkdir()
    calendar_down = HomeKit(tmp_path / "a")
    calendar_down.calendars[SEASON] = [D(2027, 1, 19), D(2027, 1, 27)]
    calendar_down.failing.add("calendar")
    body = await calendar_down.serve()
    feed = HomeFeed.model_validate_json(body)
    assert feed.next_game is None and feed.last_games is None

    day_down = HomeKit(tmp_path / "b")
    day_down.calendars[SEASON] = [D(2027, 1, 14)]
    day_down.scoreboard[D(2027, 1, 14)] = [final("g1", utc(2027, 1, 15, 0))]
    day_down.failing.add("day-feed")
    await day_down.run_games()
    feed = HomeFeed.model_validate_json(await day_down.serve())
    assert feed.last_games is None

    playoffs_down = HomeKit(tmp_path / "c", at_noon(D(2027, 5, 25)))
    playoffs_down.calendars[SEASON] = [D(2027, 5, 24)]
    feed = HomeFeed.model_validate_json(await playoffs_down.serve())
    assert ("playoffs", "league") in playoffs_down.built
    assert feed.scenario is HomeScenario.OFF_DAY
    assert keys(feed) == [ComingUpKey.PLAYOFFS]


@pytest.mark.anyio
async def test_the_scenario_comes_from_the_stored_playoffs_feed_inside_its_window(
    tmp_path: Path,
) -> None:
    kit = HomeKit(tmp_path, at_noon(D(2027, 5, 25)))
    kit.calendars[SEASON] = [D(2027, 5, 24)]
    kit.playoffs.feed = conference_finals_done()

    feed = HomeFeed.model_validate_json(await kit.serve())

    assert feed.scenario is HomeScenario.FINALS_PREVIEW


@pytest.mark.anyio
async def test_leaders_and_finals_path_are_null(kit: HomeKit) -> None:
    kit.calendars[SEASON] = [D(2027, 1, 19)]
    kit.scoreboard[D(2027, 1, 19)] = [final("g1", utc(2027, 1, 20, 0))]
    await kit.run_games()

    feed = HomeFeed.model_validate_json(await kit.serve())

    assert feed.leaders is None
    assert feed.finals_path is None
    assert b'"leaders":null' in await kit.serve()
    assert b'"finalsPath":null' in await kit.serve()


# The kind


@pytest.mark.anyio
async def test_the_feed_is_stored_at_feeds_home_league_json_only_when_requested(
    kit: HomeKit, tmp_path: Path
) -> None:
    kit.calendars[SEASON] = [D(2027, 1, 19)]
    await kit.run_games()
    kit.cache.cleanup()
    await kit.settle()

    assert kit.requests == []
    assert not (tmp_path / "feeds" / KIND).exists()

    await kit.serve()

    assert (tmp_path / "feeds" / "home" / "league.json").is_file()
    assert kit.last_build() == NOW


def test_check_answers_unknown_for_another_id_and_not_ready_before_the_season(
    kit: HomeKit,
) -> None:
    for feed_id in ("LEAGUE", "okc", ""):
        assert kit.home.check(feed_id) is IdStatus.UNKNOWN
    assert kit.home.check(FEED_ID) is IdStatus.KNOWN
    kit.stars.season = None
    assert kit.home.check(FEED_ID) is IdStatus.NOT_READY


@pytest.mark.anyio
async def test_serving_answers_unknown_and_unavailable_with_no_build(
    kit: HomeKit,
) -> None:
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, "okc")
    kit.stars.season = None
    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, FEED_ID)

    assert kit.requests == [] and kit.built == []


@pytest.mark.anyio
async def test_a_build_without_a_season_is_a_build_error(kit: HomeKit) -> None:
    kit.stars.season = None

    with pytest.raises(HomeBuildError) as raised:
        await kit.home.build(FEED_ID)

    assert raised.value.reason == "season not known yet"


@pytest.mark.anyio
async def test_the_feed_is_stale_after_the_day_change_and_fresh_before_it(
    kit: HomeKit,
) -> None:
    kit.calendars[SEASON] = [D(2027, 1, 10)]
    await kit.serve()
    feed = kit.stored()
    assert feed is not None
    built_at = kit.last_build()
    assert built_at is not None

    before = utc(2027, 1, 21, 4, 59)
    after = utc(2027, 1, 21, 5, 0)
    kit.clock[0] = before
    assert kit.home.is_fresh(feed, built_at, before)
    kit.clock[0] = after
    assert not kit.home.is_fresh(feed, built_at, after)
    assert kit.home.keep(FEED_ID) and not kit.home.keep("other")


@pytest.mark.anyio
async def test_the_feed_is_stale_1_hour_after_the_build_while_an_item_is_now(
    tmp_path: Path,
) -> None:
    kit = HomeKit(tmp_path, at_noon(D(2027, 5, 10)))
    kit.calendars[SEASON] = [D(2027, 5, 9)]
    await kit.run_games()
    await kit.serve()
    feed = kit.stored()
    assert feed is not None
    assert ComingUpStatus.NOW in statuses(feed).values()
    built_at = kit.clock[0]

    assert kit.home.is_fresh(feed, built_at, built_at + NOW_FRESH_FOR - SECOND)
    assert not kit.home.is_fresh(feed, built_at, built_at + NOW_FRESH_FOR)

    quiet = HomeFeed.model_validate(
        {**feed.model_dump(by_alias=True), "comingUp": None}
    )
    assert kit.home.is_fresh(quiet, built_at, built_at + 2 * NOW_FRESH_FOR)


@pytest.mark.anyio
async def test_a_served_feed_carries_logos_colors_and_accents_and_the_stored_file_does_not(
    kit: HomeKit,
) -> None:
    kit.stars.identities = {
        "RVR": TeamIdentity(
            code="RVR",
            logo=TeamLogo(light=HttpUrl("https://example.com/rvr.svg"), dark=None),
            colors=TeamColors(primary="#112233", secondary=None),
        ),
        "PKS": TeamIdentity(
            code="PKS",
            logo=TeamLogo(light=HttpUrl("https://example.com/pks.svg"), dark=None),
            colors=TeamColors(primary="#AA5500", secondary=None),
        ),
    }
    kit.calendars[SEASON] = [D(2027, 1, 19)]
    kit.scoreboard[D(2027, 1, 19)] = [final("g1", utc(2027, 1, 20, 0))]
    await kit.run_games()

    served = HomeFeed.model_validate_json(await kit.serve())
    stored = kit.stored()

    assert served.last_games is not None
    first = served.last_games.games[0]
    assert first.away.logo is not None and first.home.colors is not None
    assert first.accent is not None and first.accent.away is not None
    assert stored is not None and stored.last_games is not None
    kept = stored.last_games.games[0]
    assert kept.away.logo is None and kept.home.colors is None and kept.accent is None


@pytest.mark.anyio
async def test_a_failed_rebuild_keeps_the_stored_feed(kit: HomeKit) -> None:
    kit.calendars[SEASON] = [D(2027, 1, 19)]
    first = await kit.serve()
    kit.failing |= {f"types/2027/{n}" for n in (1, 2, 3, 5)}
    kit.stars.season = SEASON

    async def broken(feed_id: str) -> HomeFeed:
        raise HomeBuildError("broken")

    kit.cache._kinds[KIND].build = broken
    second = await kit.serve(NOW + 2 * 24 * HOUR)

    assert second == first
    state = kit.store.feed_build(KIND, FEED_ID)
    assert state is not None and state.last_failure_reason == "broken"
