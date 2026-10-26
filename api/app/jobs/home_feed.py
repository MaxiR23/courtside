# api/app/jobs/home_feed.py
#
# Home feed builder and kind: what the home shows on a day with no games, with every
# value decided here. The builder is a pure function from the season windows, the
# stored calendar, Cup, All-Star and playoffs data and the games of two days to the
# feed; it reads no clock and no source. The feed is decided in ADR 0074.
#
# Dates of a season window are its start and end as US Eastern dates, both inclusive.
# Today is the games feed's today (ADR 0013): the middle of the days the games job
# shows, else the US Eastern date of the clock before the job's first run.
#
# The scenario is offseason when the postseason ended (the next season's windows are
# then the ones read), or the regular season has not started; else finalsPreview when
# both conference finals are complete and no Finals game is live or final; else
# allStarBreak from the day after the last calendar day before the All-Star date to the
# day before the first calendar day after it; else offDay. With no season type known
# the scenario is offDay.
#
# comingUp lists the events of the season: Opening Night, the Cup group stage, knockout
# rounds (the quarterfinals to the semifinals) and final, the All-Star game, the
# play-in, the playoffs and the Finals (the date of its first game). The Cup dates come
# only from a stored Cup feed of this season: with none, the Cup items are left out. An
# event with no date is left out, never invented. The status of an item is upcoming
# before its start, now from its start to its end, and done after. Outside the
# offseason comingUp is null unless an item is now or an upcoming one starts in
# COMING_UP_DAYS days or less; once open it lists the now items, the upcoming ones
# starting in COMING_UP_DAYS days or less and the done ones that ended COMING_UP_DAYS
# days ago or less, by start date. In the offseason it holds the preseason and Opening
# Night items that have a date, and is null when none has one.
#
# nextGame is the first calendar day after today within COMING_UP_DAYS days: its
# first tip-off and broadcast, and its games without the postponed and canceled ones.
# lastGames are the final games, with no All-Star mark, of the last calendar day
# before today, or in the All-Star break of the last one before the break. Their games
# come from the games job memory for a day of the games feed window and from the day
# feed otherwise.
#
# HomeFeeds is the feed kind of the on-demand cache: the only id is "league", the feed
# is stored at feeds/home/league.json only when requested, and it answers 503 (not
# ready) until the stars job knows the season. Before the build slot, prepare reads the
# season types and makes fresh, through the cache, the calendar of the season (and of
# the previous one when it has no earlier day), then, each only inside its window, the
# Cup, All-Star and playoffs feeds, and the day feed of the lastGames day when it is
# outside the games window. The feed expires at the first US Eastern day change after
# the build, and 1 hour after the build while an item of comingUp is now (rule G).
# The feed is never deleted. A failed read nulls only the field it feeds.
#
# leaders is the first leader of each per-game category (points, rebounds, assists and
# blocks, in that order). In the Finals preview they come from the stored playoffs feed,
# titled playoffs, with no read. In the offseason they are the regular-season leaders of
# the last finished season, titled previousSeason with that season's label; in every
# other scenario those of the current season, titled season. The names and photos come
# from the shared player identities (at most 4 reads, 30 days cached); a leader whose
# identity was not read keeps a dash and no photo. leaders is null when the read failed
# or no category has a leader.
#
# finalsPath exists only in the Finals preview: for each finalist, East first, the three
# series it won in rounds 1 to 3 with the opponent, the result and who won. It is null
# when any series, winner or team is missing.
#
# SEE: docs/api/home.md, docs/adr/0074-home-feed.md, docs/source-rules.md

import asyncio
import datetime as dt
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.feeds.calendar import FIRST_SEASON, CalendarFeed
from app.feeds.cup import CupFeed, CupStage
from app.feeds.days import DayFeed, PastGame
from app.feeds.games import CupRound, GameStatus, PostseasonStage
from app.feeds.home import (
    ComingUpItem,
    ComingUpKey,
    ComingUpStatus,
    FinalistPath,
    FinalsPath,
    HomeFeed,
    HomeLeader,
    HomeLeaderCategory,
    HomeLeaders,
    HomeLeadersTitle,
    HomeLeaderTeam,
    HomeScenario,
    LastGame,
    LastGameLabel,
    LastGames,
    LastGamesTitle,
    LastGamesTitleKey,
    NextGame,
    PathRound,
    PathSeries,
)
from app.feeds.opponent import Opponent
from app.feeds.playoffs import (
    LeaderCategory,
    PlayoffsFeed,
    Series,
    SeriesId,
    SeriesStatus,
    round_of_series,
)
from app.jobs import all_star_feed, cup_feed, playoffs_feed
from app.jobs.calendar_feed import KIND as CALENDAR_KIND
from app.jobs.cup_feed import CupFeeds
from app.jobs.day_feed import KIND as DAY_KIND
from app.jobs.games import (
    DAYS_AROUND,
    FetchGames,
    GamesJob,
    days_shown,
    final_winner,
)
from app.jobs.on_demand import Ensure, FeedCache, FeedKind, IdStatus
from app.jobs.player_identities import PlayerIdentities
from app.jobs.playoffs_feed import UNNAMED, FetchSeasonType, PlayoffsFeeds
from app.jobs.stars import StarsJob
from app.jobs.team_feed import eastern_date, player_name, season_label
from app.jobs.team_identity import (
    code_colors,
    game_accent,
    identified,
    resolved_color,
    team_colors,
)
from app.settings import Settings
from app.sources import scoreboard, season_leaders, season_types
from app.sources.http import ReadBudget, SourceClient, SourceError, within_budget
from app.sources.player_draft import PlayerAthlete
from app.sources.scoreboard import ScoreboardGame
from app.sources.season_leaders import SeasonLeaders
from app.sources.season_types import (
    PLAY_IN,
    POSTSEASON,
    PRESEASON,
    REGULAR_SEASON,
    SeasonWindow,
)
from app.storage.feeds import read_by_id
from app.storage.state import StateStore

KIND = "home"
FEED_ID = "league"
# The one constant of the Coming up window and of the nextGame horizon, in days.
COMING_UP_DAYS = 14
# A feed with an item that is now expires this long after its build.
NOW_FRESH_FOR = dt.timedelta(hours=1)
# A feed built while the games job memory was not loaded, with a game day inside the
# games feed window, expires this long after its build, or once the memory is loaded.
MEMORY_FRESH_FOR = dt.timedelta(hours=1)
# The most source reads one build sends (ADR 0074): the season types, then the next
# game day scoreboard, then the leaders and the identities of the leaders; the calendar,
# Cup, All-Star, playoffs and day feeds built first keep their own budgets.
SEASON_TYPE_READS = 4
SCOREBOARD_READS = 1
LEADER_READS = 1
IDENTITY_READS = len(HomeLeaderCategory)

FetchSeasonLeaders = Callable[[SourceClient, int, Settings], Awaitable[SeasonLeaders]]

GameOfDay = ScoreboardGame | PastGame
KEY_ORDER = list(ComingUpKey)
PLAYOFF_ROUND_LABELS = {
    1: LastGameLabel.FIRST_ROUND,
    2: LastGameLabel.CONFERENCE_SEMIFINALS,
    3: LastGameLabel.CONFERENCE_FINALS,
}
OVERTIME_PERIOD = 5


class HomeBuildError(Exception):
    """The home feed built from the read data is not valid."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class SeasonWindows:
    """The season type windows read; next_season is true when the preseason and the
    regular season are those of the next season."""

    preseason: SeasonWindow | None
    regular: SeasonWindow | None
    play_in: SeasonWindow | None
    postseason: SeasonWindow | None
    next_season: bool = False


@dataclass(frozen=True)
class HomeSources:
    season: int
    today: dt.date
    windows: SeasonWindows
    # The days of the current and, when read, the previous calendar, sorted and unique.
    calendar_days: list[dt.date]
    all_star_date: dt.date | None
    cup: CupFeed | None
    # Already filtered to the playoffs window and the season.
    playoffs: PlayoffsFeed | None
    window_days: list[dt.date] | None
    next_games: list[ScoreboardGame] | None
    last_day: dt.date | None
    last_day_games: Sequence[GameOfDay] | None
    season_leaders: SeasonLeaders | None = None
    identities: Mapping[str, PlayerAthlete | None] = field(default_factory=dict)


def window_dates(window: SeasonWindow | None) -> tuple[dt.date, dt.date] | None:
    """The first and last US Eastern date of a window, or none when it is unknown."""
    if window is None:
        return None
    return eastern_date(window.start), eastern_date(window.end)


def break_days(
    calendar_days: Sequence[dt.date], all_star_date: dt.date | None
) -> tuple[dt.date, dt.date] | None:
    """The last calendar day before the All-Star date and the first one after it, or
    none without the date or without both days."""
    if all_star_date is None:
        return None
    before = [day for day in calendar_days if day < all_star_date]
    after = [day for day in calendar_days if day > all_star_date]
    if not before or not after:
        return None
    return max(before), min(after)


def is_finals_preview(playoffs: PlayoffsFeed | None) -> bool:
    """Both conference finals are complete and no Finals game is live or final."""
    if playoffs is None:
        return False
    series = {item.id: item for item in playoffs.bracket}
    for series_id in (SeriesId.EAST_R3, SeriesId.WEST_R3):
        found = series.get(series_id)
        if found is None or found.status is not SeriesStatus.COMPLETE:
            return False
    finals = series.get(SeriesId.FINALS)
    started = finals is not None and any(
        game.status in (GameStatus.LIVE, GameStatus.FINAL) for game in finals.games
    )
    return not started


def decide_scenario(
    today: dt.date,
    windows: SeasonWindows,
    all_star_break: bool,
    finals_preview: bool,
) -> HomeScenario:
    postseason = window_dates(windows.postseason)
    regular = window_dates(windows.regular)
    if (
        windows.next_season
        or (postseason is not None and today > postseason[1])
        or (regular is not None and today < regular[0])
    ):
        return HomeScenario.OFFSEASON
    if finals_preview:
        return HomeScenario.FINALS_PREVIEW
    if all_star_break:
        return HomeScenario.ALL_STAR_BREAK
    return HomeScenario.OFF_DAY


def scenario_of(
    today: dt.date,
    windows: SeasonWindows,
    calendar_days: Sequence[dt.date],
    all_star_date: dt.date | None,
    playoffs: PlayoffsFeed | None,
) -> HomeScenario:
    around = break_days(calendar_days, all_star_date)
    return decide_scenario(
        today,
        windows,
        around is not None and around[0] < today < around[1],
        is_finals_preview(playoffs),
    )


def item_status(start: dt.date, end: dt.date | None, today: dt.date) -> ComingUpStatus:
    if today < start:
        return ComingUpStatus.UPCOMING
    if today <= (end or start):
        return ComingUpStatus.NOW
    return ComingUpStatus.DONE


def _item(
    key: ComingUpKey, first: dt.date, last: dt.date | None, today: dt.date
) -> ComingUpItem:
    end = last if last is not None and last > first else None
    return ComingUpItem(
        key=key,
        start_date=first,
        end_date=end,
        status=item_status(first, end, today),
    )


def _window_item(
    key: ComingUpKey, window: SeasonWindow | None, today: dt.date
) -> list[ComingUpItem]:
    dates = window_dates(window)
    return [] if dates is None else [_item(key, dates[0], dates[1], today)]


def _cup_items(cup: CupFeed, today: dt.date) -> list[ComingUpItem]:
    stages = {entry.stage: entry for entry in cup.stages}
    items: list[ComingUpItem] = []
    group = stages.get(CupRound.GROUP)
    if group is not None and group.first_date and group.last_date:
        items.append(
            _item(ComingUpKey.CUP_GROUP_STAGE, group.first_date, group.last_date, today)
        )
    quarters = stages.get(CupRound.QUARTERFINALS)
    semis = stages.get(CupRound.SEMIFINALS)
    knockout = [
        entry
        for entry in (quarters, semis)
        if entry is not None and entry.first_date and entry.last_date
    ]
    if knockout:
        first, last = knockout[0].first_date, knockout[-1].last_date
        if first is not None and last is not None:
            items.append(_item(ComingUpKey.CUP_KNOCKOUT, first, last, today))
    final = stages.get(CupRound.CHAMPIONSHIP)
    if final is not None and final.first_date and final.last_date:
        items.append(
            _item(ComingUpKey.CUP_FINAL, final.first_date, final.last_date, today)
        )
    return items


def _finals_date(playoffs: PlayoffsFeed) -> dt.date | None:
    for series in playoffs.bracket:
        if series.id is SeriesId.FINALS:
            for game in series.games:
                if game.number == 1:
                    return game.date
    return None


def events(sources: HomeSources, offseason: bool) -> list[ComingUpItem]:
    """The dated events, in no order."""
    today, windows = sources.today, sources.windows
    items: list[ComingUpItem] = []
    regular = window_dates(windows.regular)
    if regular is not None:
        items.append(_item(ComingUpKey.OPENING_NIGHT, regular[0], None, today))
    if offseason:
        return items + _window_item(ComingUpKey.PRESEASON, windows.preseason, today)
    if sources.cup is not None and sources.cup.season == season_label(sources.season):
        items += _cup_items(sources.cup, today)
    if sources.all_star_date is not None:
        items.append(_item(ComingUpKey.ALL_STAR, sources.all_star_date, None, today))
    items += _window_item(ComingUpKey.PLAY_IN, windows.play_in, today)
    items += _window_item(ComingUpKey.PLAYOFFS, windows.postseason, today)
    if sources.playoffs is not None:
        finals = _finals_date(sources.playoffs)
        if finals is not None:
            items.append(_item(ComingUpKey.FINALS, finals, None, today))
    return items


def _sorted(items: Sequence[ComingUpItem]) -> list[ComingUpItem]:
    return sorted(items, key=lambda item: (item.start_date, KEY_ORDER.index(item.key)))


def coming_up(
    items: Sequence[ComingUpItem], today: dt.date, offseason: bool
) -> list[ComingUpItem] | None:
    if offseason:
        return _sorted(items) or None

    def soon(item: ComingUpItem) -> bool:
        return (item.start_date - today).days <= COMING_UP_DAYS

    if not any(
        item.status is ComingUpStatus.NOW
        or (item.status is ComingUpStatus.UPCOMING and soon(item))
        for item in items
    ):
        return None
    listed = [
        item
        for item in items
        if item.status is ComingUpStatus.NOW
        or (item.status is ComingUpStatus.UPCOMING and soon(item))
        or (
            item.status is ComingUpStatus.DONE
            and (today - (item.end_date or item.start_date)).days <= COMING_UP_DAYS
        )
    ]
    return _sorted(listed)


def next_game_day(calendar_days: Sequence[dt.date], today: dt.date) -> dt.date | None:
    horizon = today + dt.timedelta(days=COMING_UP_DAYS)
    return next((day for day in sorted(calendar_days) if today < day <= horizon), None)


def next_game(
    day: dt.date,
    games: Sequence[ScoreboardGame],
    window_days: Sequence[dt.date] | None,
) -> NextGame | None:
    played = [
        game
        for game in games
        if game.status not in (GameStatus.POSTPONED, GameStatus.CANCELED)
    ]
    if not played:
        return None
    first = min(played, key=lambda game: game.start_time)
    return NextGame(
        date=day,
        first_tip_off=first.start_time,
        broadcast=first.broadcast,
        game_count=len(played),
        in_games_window=window_days is not None and day in window_days,
    )


def last_games_day(
    scenario: HomeScenario,
    calendar_days: Sequence[dt.date],
    today: dt.date,
    around: tuple[dt.date, dt.date] | None,
) -> dt.date | None:
    if scenario is HomeScenario.ALL_STAR_BREAK:
        return None if around is None else around[0]
    return max((day for day in calendar_days if day < today), default=None)


def last_games_title(
    scenario: HomeScenario, day: dt.date, today: dt.date
) -> LastGamesTitle:
    if scenario is HomeScenario.OFFSEASON:
        return LastGamesTitle(key=LastGamesTitleKey.LAST_GAMES_PLAYED, days=None)
    if scenario is HomeScenario.ALL_STAR_BREAK:
        return LastGamesTitle(key=LastGamesTitleKey.BEFORE_THE_BREAK, days=None)
    if scenario is HomeScenario.FINALS_PREVIEW:
        return LastGamesTitle(key=LastGamesTitleKey.CONFERENCE_FINALS, days=None)
    if day == today - dt.timedelta(days=1):
        return LastGamesTitle(key=LastGamesTitleKey.LAST_NIGHT, days=None)
    return LastGamesTitle(key=LastGamesTitleKey.DAYS_AGO, days=(today - day).days)


def game_label(game: GameOfDay) -> tuple[LastGameLabel, int | None]:
    mark = game.postseason
    if mark is not None:
        if mark.stage is PostseasonStage.PLAYIN:
            return LastGameLabel.PLAY_IN, None
        if mark.stage is PostseasonStage.FINALS:
            return LastGameLabel.FINALS, mark.number
        if (
            mark.stage is PostseasonStage.PLAYOFFS
            and mark.round in PLAYOFF_ROUND_LABELS
        ):
            return PLAYOFF_ROUND_LABELS[mark.round], mark.number
    overtime = game.period is not None and game.period >= OVERTIME_PERIOD
    return (LastGameLabel.FINAL_OVERTIME if overtime else LastGameLabel.FINAL), None


def _side(team: Opponent) -> Opponent:
    """The side without identity: the logo and colors are added when served."""
    return Opponent.model_validate(
        team.model_dump(by_alias=False) | {"logo": None, "colors": None}
    )


def last_game(game: GameOfDay) -> LastGame | None:
    """The last game of a final game with a score and no All-Star mark, else none."""
    if (
        game.status is not GameStatus.FINAL
        or game.score is None
        or game.all_star is not None
    ):
        return None
    winner = game.winner if isinstance(game, PastGame) else final_winner(game)
    label, number = game_label(game)
    try:
        return LastGame(
            id=game.id,
            away=_side(game.away),
            home=_side(game.home),
            score=game.score,
            winner=winner,
            label=label,
            game_number=number,
        )
    except ValidationError:
        return None


def _last_games(sources: HomeSources, scenario: HomeScenario) -> LastGames | None:
    day, games = sources.last_day, sources.last_day_games
    if day is None or not games:
        return None
    found = [
        built
        for game in sorted(games, key=lambda item: item.start_time)
        if (built := last_game(game)) is not None
    ]
    if not found:
        return None
    return LastGames(
        date=day,
        title=last_games_title(scenario, day, sources.today),
        games=found,
    )


def leaders_season(season: int, windows: SeasonWindows) -> int:
    """The last finished season in the offseason: the current one once the postseason
    ended (the windows are then the next season's), else the one before."""
    return season if windows.next_season else season - 1


def leader_ids(leaders: SeasonLeaders) -> list[str]:
    """The player id of the first leader of each category, without repeats."""
    ids: list[str] = []
    for category in HomeLeaderCategory:
        entries = leaders.categories.get(LeaderCategory(category.value))
        if entries:
            ids.append(entries[0].player_id)
    return list(dict.fromkeys(ids))


def _playoff_leaders(playoffs: PlayoffsFeed | None) -> list[HomeLeader]:
    if playoffs is None or playoffs.leaders is None:
        return []
    groups = {group.category.value: group for group in playoffs.leaders}
    found: list[HomeLeader] = []
    for category in HomeLeaderCategory:
        group = groups.get(category.value)
        if group is None or not group.leaders:
            continue
        leader = group.leaders[0]
        found.append(
            HomeLeader(
                category=category,
                player_id=leader.player_id,
                name=leader.name,
                photo_url=leader.photo_url,
                team=HomeLeaderTeam(code=leader.team_code),
                value=leader.value,
            )
        )
    return found


def _season_leaders(sources: HomeSources) -> list[HomeLeader]:
    if sources.season_leaders is None:
        return []
    found: list[HomeLeader] = []
    for category in HomeLeaderCategory:
        entries = sources.season_leaders.categories.get(LeaderCategory(category.value))
        if not entries:
            continue
        entry = entries[0]
        athlete = sources.identities.get(entry.player_id)
        found.append(
            HomeLeader.model_validate(
                {
                    "category": category,
                    "player_id": entry.player_id,
                    "name": UNNAMED if athlete is None else player_name(athlete.entry),
                    "photo_url": None
                    if athlete is None
                    else athlete.entry.headshot_url,
                    "team": None
                    if entry.team_code is None
                    else HomeLeaderTeam(code=entry.team_code),
                    "value": entry.value,
                }
            )
        )
    return found


def home_leaders(sources: HomeSources, scenario: HomeScenario) -> HomeLeaders | None:
    """The first leader of each category, or none when there is no leader."""
    try:
        if scenario is HomeScenario.FINALS_PREVIEW:
            categories = _playoff_leaders(sources.playoffs)
            title, label = HomeLeadersTitle.PLAYOFFS, None
        else:
            categories = _season_leaders(sources)
            if scenario is HomeScenario.OFFSEASON:
                title = HomeLeadersTitle.PREVIOUS_SEASON
                label = season_label(leaders_season(sources.season, sources.windows))
            else:
                title, label = HomeLeadersTitle.SEASON, None
        if not categories:
            return None
        return HomeLeaders(title=title, season_label=label, categories=categories)
    except ValidationError:
        return None


def _path_series(series: Series, code: str, round_: PathRound) -> PathSeries | None:
    """The series a finalist won, from its side; none when a team or a win count is
    missing."""
    sides = [series.top, series.bottom]
    own = next((s for s in sides if s.team is not None and s.team.code == code), None)
    other = next((s for s in sides if s is not own), None)
    if (
        own is None
        or other is None
        or other.team is None
        or own.wins is None
        or other.wins is None
    ):
        return None
    return PathSeries(
        round=round_,
        opponent=_side(other.team),
        result=f"{own.wins}\u2013{other.wins}",
        won=series.winner == code,
    )


def _finalist_path(
    playoffs: PlayoffsFeed, conference_final: Series
) -> FinalistPath | None:
    code = conference_final.winner
    if code is None:
        return None
    rounds = list(PathRound)
    path: dict[PathRound, PathSeries] = {}
    team = None
    for series in playoffs.bracket:
        number = round_of_series(series.id)
        if series.winner != code or not 1 <= number <= len(rounds):
            continue
        round_ = rounds[number - 1]
        built = _path_series(series, code, round_)
        if built is None or round_ in path:
            return None
        path[round_] = built
        for side in (series.top, series.bottom):
            if side.team is not None and side.team.code == code:
                team = side.team
    if team is None or list(path) != rounds:
        return None
    return FinalistPath(team=_side(team), series=[path[round_] for round_ in rounds])


def finals_path(playoffs: PlayoffsFeed | None) -> FinalsPath | None:
    """How each finalist reached the Finals, East first; none when a piece is missing."""
    if playoffs is None:
        return None
    by_id = {series.id: series for series in playoffs.bracket}
    try:
        finalists: list[FinalistPath] = []
        for series_id in (SeriesId.EAST_R3, SeriesId.WEST_R3):
            conference_final = by_id.get(series_id)
            built = (
                None
                if conference_final is None
                else _finalist_path(playoffs, conference_final)
            )
            if built is None:
                return None
            finalists.append(built)
        return FinalsPath(finalists=finalists)
    except ValidationError:
        return None


def build_home_feed(sources: HomeSources) -> HomeFeed:
    """Build the home feed; raise HomeBuildError when it is not valid."""
    scenario = scenario_of(
        sources.today,
        sources.windows,
        sources.calendar_days,
        sources.all_star_date,
        sources.playoffs,
    )
    offseason = scenario is HomeScenario.OFFSEASON
    try:
        day = next_game_day(sources.calendar_days, sources.today)
        upcoming = (
            None
            if day is None or sources.next_games is None
            else next_game(day, sources.next_games, sources.window_days)
        )
        return HomeFeed(
            season=season_label(sources.season),
            date=sources.today,
            scenario=scenario,
            coming_up=coming_up(events(sources, offseason), sources.today, offseason),
            next_game=upcoming,
            last_games=_last_games(sources, scenario),
            leaders=home_leaders(sources, scenario),
            finals_path=(
                finals_path(sources.playoffs)
                if scenario is HomeScenario.FINALS_PREVIEW
                else None
            ),
        )
    except ValidationError as error:
        location = ".".join(str(part) for part in error.errors()[0]["loc"])
        raise HomeBuildError(
            f"invalid feed: {error.error_count()} errors, first at {location}"
        ) from None


class HomeFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        games: GamesJob,
        stars: StarsJob,
        cup: CupFeeds,
        playoffs: PlayoffsFeeds,
        identities: PlayerIdentities,
        *,
        fetch_season_type: FetchSeasonType = season_types.fetch_season_type,
        fetch_games: FetchGames = scoreboard.fetch_games,
        fetch_season_leaders: FetchSeasonLeaders = season_leaders.fetch_season_leaders,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._games = games
        self._stars = stars
        self._cup = cup
        self._playoffs = playoffs
        self._identities = identities
        self._fetch_season_type = fetch_season_type
        self._fetch_games = fetch_games
        self._fetch_season_leaders = fetch_season_leaders
        self._prepared: dict[str, SeasonWindows] = {}
        # True until the first build: a stored feed from an earlier process is not
        # known to have used the memory.
        self._without_memory = True
        cache.register(self.kind())

    def check(self, feed_id: str) -> IdStatus:
        if feed_id != FEED_ID:
            return IdStatus.UNKNOWN
        if (
            self._stars.current_season() is None
            and read_by_id(self._settings.data_dir, KIND, FEED_ID) is None
        ):
            return IdStatus.NOT_READY
        return IdStatus.KNOWN

    def today(self) -> dt.date:
        """The games feed's today (ADR 0013)."""
        days = self._games.shown_days()
        if days is not None:
            return days[DAYS_AROUND]
        return eastern_date(self._client.clock())

    async def _window(self, season: int, season_type: int) -> SeasonWindow | None:
        try:
            return await self._fetch_season_type(
                self._client, season, season_type, self._settings
            )
        except SourceError:
            return None

    async def _read_all(self, season: int, today: dt.date) -> SeasonWindows:
        postseason = await self._window(season, POSTSEASON)
        ended = window_dates(postseason)
        if ended is not None and today > ended[1]:
            preseason, regular = await asyncio.gather(
                self._window(season + 1, PRESEASON),
                self._window(season + 1, REGULAR_SEASON),
            )
            return SeasonWindows(preseason, regular, None, postseason, True)
        preseason, regular, play_in = await asyncio.gather(
            self._window(season, PRESEASON),
            self._window(season, REGULAR_SEASON),
            self._window(season, PLAY_IN),
        )
        return SeasonWindows(preseason, regular, play_in, postseason)

    async def _read_windows(self, season: int, today: dt.date) -> SeasonWindows:
        """The season windows, at most SEASON_TYPE_READS reads; a failed read gives
        none for its window only."""
        try:
            return await within_budget(
                ReadBudget(SEASON_TYPE_READS, stop_on_rate_limit=False),
                "home: season types",
                lambda: self._read_all(season, today),
            )
        except SourceError:
            return SeasonWindows(None, None, None, None)

    def _calendar(self, season: int) -> list[dt.date] | None:
        body = read_by_id(self._settings.data_dir, CALENDAR_KIND, str(season))
        if body is None:
            return None
        try:
            return CalendarFeed.model_validate_json(body).days
        except ValidationError:
            return None

    def _calendar_days(self, season: int) -> list[dt.date]:
        days: set[dt.date] = set()
        for found in (self._calendar(season), self._calendar(season - 1)):
            days |= set(found or [])
        return sorted(days)

    def _cup_of_season(self, season: int) -> CupFeed | None:
        cup = self._cup.stored()
        if cup is None or cup.season != season_label(season):
            return None
        return cup

    def _playoffs_in_window(
        self, season: int, today: dt.date, windows: SeasonWindows
    ) -> PlayoffsFeed | None:
        if not self._in_playoffs_window(today, windows):
            return None
        stored = self._playoffs.stored()
        if stored is None or stored.season != season_label(season):
            return None
        return stored

    @staticmethod
    def _in_playoffs_window(today: dt.date, windows: SeasonWindows) -> bool:
        play_in, postseason = (
            window_dates(windows.play_in),
            window_dates(windows.postseason),
        )
        return (
            play_in is not None
            and postseason is not None
            and not windows.next_season
            and play_in[0] <= today <= postseason[1]
        )

    def _all_star_date(self, season: int) -> dt.date | None:
        edition = self._store.all_star_edition(season)
        return None if edition is None else edition.game_date

    def _window_days(self, today: dt.date) -> list[dt.date]:
        return self._games.shown_days() or days_shown(today)

    async def prepare(self, feed_id: str, ensure: Ensure) -> None:
        season = self._stars.current_season()
        if season is None:
            return
        today = self.today()
        windows = await self._read_windows(season, today)
        self._prepared[feed_id] = windows
        # Outside the budget above, so the ensured builds never inherit it.
        await ensure(CALENDAR_KIND, str(season))
        current = self._calendar(season)
        if (
            current is None or not any(day < today for day in current)
        ) and season - 1 >= FIRST_SEASON:
            await ensure(CALENDAR_KIND, str(season - 1))
        starts, ends = (
            dt.date(season, *all_star_feed.EDITION_WINDOW[0]),
            dt.date(season, *all_star_feed.EDITION_WINDOW[1]),
        )
        cup = self._cup.stored()
        wanted: list[tuple[str, str]] = []
        if (
            cup is not None
            and cup.season == season_label(season)
            and cup.first_game_date is not None
            and cup.first_game_date <= today
            and cup.stage is not CupStage.COMPLETE
        ):
            wanted.append((cup_feed.KIND, cup_feed.FEED_ID))
        if starts <= today <= ends:
            wanted.append((all_star_feed.KIND, all_star_feed.FEED_ID))
        if self._in_playoffs_window(today, windows):
            wanted.append((playoffs_feed.KIND, playoffs_feed.FEED_ID))
        await asyncio.gather(*(ensure(kind, id_) for kind, id_ in wanted))
        calendar_days = self._calendar_days(season)
        scenario = scenario_of(
            today,
            windows,
            calendar_days,
            self._all_star_date(season),
            self._playoffs_in_window(season, today, windows),
        )
        day = last_games_day(
            scenario,
            calendar_days,
            today,
            break_days(calendar_days, self._all_star_date(season)),
        )
        if day is not None and day not in self._window_days(today):
            await ensure(DAY_KIND, day.isoformat())

    def _day_games(self, day: dt.date) -> list[ScoreboardGame] | None:
        games = self._games.shown_games()
        if games is None:
            self._without_memory = True
            return None
        return [game for game in games if eastern_date(game.start_time) == day]

    def _stored_day(self, day: dt.date) -> list[PastGame] | None:
        body = read_by_id(self._settings.data_dir, DAY_KIND, day.isoformat())
        if body is None:
            return None
        try:
            return DayFeed.model_validate_json(body).day.games
        except ValidationError:
            return None

    async def _next_games(self, day: dt.date) -> list[ScoreboardGame] | None:
        try:
            return await within_budget(
                ReadBudget(SCOREBOARD_READS, stop_on_rate_limit=False),
                "home: next game day",
                lambda: self._fetch_games(self._client, day, self._settings),
            )
        except SourceError:
            return None

    async def _season_leaders(self, season: int) -> SeasonLeaders | None:
        try:
            return await within_budget(
                ReadBudget(LEADER_READS, stop_on_rate_limit=False),
                "home: leaders",
                lambda: self._fetch_season_leaders(
                    self._client, season, self._settings
                ),
            )
        except SourceError:
            return None

    async def _identities_of(
        self, ids: Sequence[str]
    ) -> Mapping[str, PlayerAthlete | None]:
        if not ids:
            return {}

        async def one(player_id: str) -> PlayerAthlete | None:
            # A rate-limited read nulls only that player; the others keep theirs.
            try:
                return (await self._identities.resolve([player_id]))[player_id]
            except SourceError:
                return None

        async def all_of() -> dict[str, PlayerAthlete | None]:
            unique = list(dict.fromkeys(ids))
            found = await asyncio.gather(*(one(i) for i in unique))
            return dict(zip(unique, found, strict=True))

        try:
            return await within_budget(
                ReadBudget(IDENTITY_READS, stop_on_rate_limit=False),
                "home: player identities",
                all_of,
            )
        except SourceError:
            return {}

    async def build(self, feed_id: str) -> HomeFeed:
        season = self._stars.current_season()
        if season is None:
            raise HomeBuildError("season not known yet")
        today = self.today()
        self._without_memory = False
        windows = self._prepared.pop(feed_id, None)
        if windows is None:
            windows = await self._read_windows(season, today)
        calendar_days = self._calendar_days(season)
        all_star_date = self._all_star_date(season)
        playoffs = self._playoffs_in_window(season, today, windows)
        scenario = scenario_of(today, windows, calendar_days, all_star_date, playoffs)
        last_day = last_games_day(
            scenario, calendar_days, today, break_days(calendar_days, all_star_date)
        )
        last_day_games: Sequence[GameOfDay] | None = None
        if last_day is not None:
            last_day_games = (
                self._day_games(last_day)
                if last_day in self._window_days(today)
                else self._stored_day(last_day)
            )
        window_days = self._games.shown_days()
        next_games: list[ScoreboardGame] | None = None
        day = next_game_day(calendar_days, today)
        if day is not None:
            next_games = (
                self._day_games(day)
                if window_days is not None and day in window_days
                else await self._next_games(day)
            )
        leaders: SeasonLeaders | None = None
        identities: Mapping[str, PlayerAthlete | None] = {}
        if scenario is not HomeScenario.FINALS_PREVIEW:
            leaders = await self._season_leaders(
                leaders_season(season, windows)
                if scenario is HomeScenario.OFFSEASON
                else season
            )
            if leaders is not None:
                identities = await self._identities_of(leader_ids(leaders))
        return build_home_feed(
            HomeSources(
                season=season,
                today=today,
                windows=windows,
                calendar_days=calendar_days,
                all_star_date=all_star_date,
                cup=self._cup_of_season(season),
                playoffs=playoffs,
                window_days=window_days,
                next_games=next_games,
                last_day=last_day,
                last_day_games=last_day_games,
                season_leaders=leaders,
                identities=identities,
            )
        )

    def is_fresh(self, feed: HomeFeed, built_at: dt.datetime, now: dt.datetime) -> bool:
        if self.today() != feed.date:
            return False
        now_item = any(
            item.status is ComingUpStatus.NOW for item in feed.coming_up or []
        )
        if now_item and now - built_at >= NOW_FRESH_FOR:
            return False
        return not (
            self._without_memory
            and (
                self._games.shown_games() is not None
                or now - built_at >= MEMORY_FRESH_FOR
            )
        )

    def serve_with(self, feed_id: str, feed: HomeFeed) -> HomeFeed:
        if (
            feed.last_games is None
            and feed.leaders is None
            and feed.finals_path is None
        ):
            return feed
        identities = self._stars.team_identities()
        update: dict[str, object] = {}
        if feed.last_games is not None:
            games = [
                game.model_copy(
                    update={
                        "accent": game_accent(
                            identified(game.away, identities),
                            identified(game.home, identities),
                        )
                    }
                )
                for game in feed.last_games.games
            ]
            update["last_games"] = feed.last_games.model_copy(update={"games": games})
        if feed.leaders is not None:
            leaders = [
                leader
                if leader.team is None
                else leader.model_copy(
                    update={
                        "team": leader.team.model_copy(
                            update={
                                "accent": resolved_color(
                                    code_colors(leader.team.code, None, identities)
                                )
                            }
                        )
                    }
                )
                for leader in feed.leaders.categories
            ]
            update["leaders"] = feed.leaders.model_copy(update={"categories": leaders})
        if feed.finals_path is not None:
            finalists = [
                finalist.model_copy(
                    update={
                        "accent": resolved_color(
                            team_colors(finalist.team, identities)
                        ),
                        "series": [
                            item.model_copy(
                                update={
                                    "accent": resolved_color(
                                        team_colors(item.opponent, identities)
                                    )
                                }
                            )
                            for item in finalist.series
                        ],
                    }
                )
                for finalist in feed.finals_path.finalists
            ]
            update["finals_path"] = feed.finals_path.model_copy(
                update={"finalists": finalists}
            )
        return HomeFeed.model_validate(
            feed.model_copy(update=update).model_dump(by_alias=False)
        )

    def keep(self, feed_id: str) -> bool:
        return feed_id == FEED_ID

    def kind(self) -> FeedKind[HomeFeed]:
        return FeedKind(
            KIND,
            HomeFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
            serve_with=self.serve_with,
            prepare=self.prepare,
        )
