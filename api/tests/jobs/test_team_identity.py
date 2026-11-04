# api/tests/jobs/test_team_identity.py
#
# Tests for the team identities of the feeds and the hero accent rule.
#
# Tested:
# - identity_of adds the hash to the primary and the secondary and keeps a null secondary and the logo
# - identified sets the logo and colors of a league side, nulls them on a guest, a historical side and a code with no identity, and on a PlayoffTeam sets only the logo and keeps the colors it was built with
# - identified gives a logo to a StandingsRow, a SearchTeam, a LeagueTeam and a TeamFeed and keeps their colors; it gives a logo and colors to a SearchPlayerTeam and to a current Team; it nulls both on a Team with a season code and the logo of a historical StandingsRow and TeamFeed; it keeps the logo of a non-historical past StandingsRow
# - with_identities reaches sides in nested models, lists and optional fields, in every Opponent subclass (GameTeam, DetailTeam, PlayoffTeam), and the root of a model that is a league team object, and returns a validated model
# - with_identities gives each season row of a player feed the logo of each team whose season code is its code, in per game, totals and playoffs rows; null for a historical, unknown or unidentified team; a list of nulls with no season codes; it reads a stored feed without logos and a past player feed, and leaves the career rows alone (ADR 0070)
# - game_accent for NYK at ORL, MIL at BOS, LAL at PHX and OKC at DEN; a team with no secondary keeps its primary; a guest side gets null and the other side keeps its rule; two sides with no colors give null and null
# - team_colors gives the identity colors of a league side and null for no team, a guest, a historical side, a code with no identity and a PlayoffTeam with no identity, ignoring the colors a PlayoffTeam was built with
# - code_colors gives the identity colors of a code with no season code or the same season code, and null for no code, a different season code and an unknown code
# - resolved_color gives the primary, the secondary of a dark primary, and null for no colors
# - pair_colors gives the first side its rule, moves the second to its secondary when too close, and gives null for a missing side
# - oklab of white has lightness 1 and of black 0
#
# What is covered:
# - Pure logic: happy path, edge cases, error case
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_team_identity.py
#
# SEE: api/app/jobs/team_identity.py

import datetime as dt
from typing import Any

import pytest
from pydantic import HttpUrl, ValidationError

from app.feeds.all_star import LeagueTeam
from app.feeds.game_detail import DetailTeam
from app.feeds.games import FeedModel, GameTeam, Team
from app.feeds.opponent import Opponent, TeamColors, TeamLogo
from app.feeds.player import PastPlayerFeed, PlayerFeed
from app.feeds.playoffs import PlayoffTeam
from app.feeds.search import SearchPlayerTeam, SearchTeam
from app.feeds.standings import StandingsColors, StandingsRow
from app.feeds.team import TeamFeed
from app.jobs.team_identity import (
    code_colors,
    game_accent,
    identified,
    identity_of,
    oklab,
    pair_colors,
    resolved_color,
    team_colors,
    with_identities,
)
from app.sources.team_info import TeamInfo
from app.storage.state import TeamIdentity
from tests.feeds.test_player import past_player, split, valid_player

LOGO = TeamLogo(light=HttpUrl("https://example.com/okc.svg"), dark=None)
BUILT = StandingsColors(primary="#111111", secondary=None)


def an_identity(
    code: str = "OKC", primary: str = "#007AC1", secondary: str | None = "#EF3B24"
) -> TeamIdentity:
    return TeamIdentity(
        code=code,
        logo=LOGO,
        colors=TeamColors(primary=primary, secondary=secondary),
    )


IDENTITIES = {"OKC": an_identity()}


def side(code: str | None = "OKC", **more: Any) -> Opponent:
    return Opponent(code=code, name=None, city=None, **more)


def test_identity_of_adds_the_hash_and_keeps_a_null_secondary_and_the_logo() -> None:
    info = TeamInfo(
        location="Harbor City", name="Gulls", color="0b3d91", alternate_color="f2a900"
    )
    plain = TeamInfo(location="Harbor City", name="Gulls", color="0b3d91", logo=LOGO)

    full = identity_of("OKC", info)
    bare = identity_of("OKC", plain)

    assert full.colors == TeamColors(primary="#0b3d91", secondary="#f2a900")
    assert full.logo is None
    assert bare.colors.secondary is None
    assert bare.logo == LOGO


def test_identified_sets_the_logo_and_colors_of_a_league_side() -> None:
    result = identified(side(), IDENTITIES)

    assert result.logo == LOGO
    assert result.colors == IDENTITIES["OKC"].colors


def test_identified_nulls_a_guest_a_historical_side_and_a_code_with_no_identity() -> (
    None
):
    stale = side(logo=LOGO, colors=IDENTITIES["OKC"].colors)
    guest = Opponent(code="OKC", name="Gulls", city=None, guest=True)
    historical = side(season_code="SEA", historical=True)

    for team in (
        guest,
        historical,
        side("BOS"),
        Opponent(code=None, name="X", city=None, guest=True),
    ):
        result = identified(team, IDENTITIES)
        assert (result.logo, result.colors) == (None, None)
    assert identified(stale, {}).logo is None
    assert identified(stale, {}).colors is None


def test_identified_keeps_the_built_colors_of_a_playoff_team() -> None:
    team = PlayoffTeam(code="OKC", name=None, city=None, colors=BUILT)

    result = identified(team, IDENTITIES)

    assert result.logo == LOGO
    assert result.colors == BUILT
    assert identified(team, {}).colors == BUILT


def test_identified_covers_every_opponent_subclass() -> None:
    teams: list[Opponent] = [
        GameTeam(code="OKC", name="Thunder", city="Oklahoma City"),
        DetailTeam.model_validate(
            {
                "code": "OKC",
                "name": "Thunder",
                "city": "Oklahoma City",
                "record": None,
            }
        ),
    ]

    for team in teams:
        assert identified(team, IDENTITIES).logo == LOGO


def test_identified_gives_a_logo_to_the_teams_that_keep_their_colors() -> None:
    row = StandingsRow.model_construct(
        code="OKC", colors=BUILT, historical=False, season_code=None, logo=None
    )
    search = SearchTeam.model_construct(code="OKC", colors=BUILT, logo=None)
    league = LeagueTeam.model_construct(code="OKC", colors=BUILT, logo=None)
    root = TeamFeed.model_construct(
        code="OKC",
        colors=TeamColors(primary="#111111", secondary=None),
        historical=False,
        season_code=None,
        logo=None,
    )

    for team in (row, search, league, root):
        result = identified(team, IDENTITIES)
        assert result.logo == LOGO
        assert result.colors == team.colors


def test_identified_gives_a_logo_and_colors_to_a_search_player_team_and_a_current_team() -> (
    None
):
    player_team = SearchPlayerTeam(code="OKC", primary="#007AC1")
    current = Team(code="OKC", name="Thunder", city="Oklahoma City")

    for team in (player_team, current):
        result = identified(team, IDENTITIES)
        assert result.logo == LOGO
        assert result.colors == IDENTITIES["OKC"].colors


def test_identified_nulls_the_logo_and_colors_of_a_team_with_a_season_code() -> None:
    past = Team(code="OKC", name="Thunder", city="Oklahoma City", season_code="SEA")

    result = identified(past, IDENTITIES)

    assert (result.logo, result.colors) == (None, None)


def test_identified_nulls_the_logo_of_a_historical_row_and_team_feed() -> None:
    row = StandingsRow.model_construct(
        code="OKC", colors=BUILT, historical=True, season_code="SEA", logo=None
    )
    root = TeamFeed.model_construct(
        code="OKC", colors=None, historical=True, season_code="SEA", logo=None
    )

    assert identified(row, IDENTITIES).logo is None
    assert identified(root, IDENTITIES).logo is None


def test_identified_keeps_the_logo_of_a_non_historical_past_row() -> None:
    row = StandingsRow.model_construct(
        code="OKC", colors=BUILT, historical=False, season_code="OKC", logo=None
    )

    assert identified(row, IDENTITIES).logo == LOGO


class Inner(FeedModel):
    opponent: GameTeam
    spare: GameTeam | None = None


class Root(FeedModel):
    code: str
    logo: TeamLogo | None = None
    inner: Inner
    sides: list[GameTeam]


def a_game_team(code: str | None, **more: Any) -> GameTeam:
    return GameTeam(code=code, name="Name", city="City", **more)


def test_with_identities_reaches_nested_sides_lists_optionals_and_the_root() -> None:
    model = Root(
        code="OKC",
        inner=Inner(opponent=a_game_team("OKC"), spare=None),
        sides=[a_game_team("OKC"), a_game_team("BOS")],
    )

    result = with_identities(model, IDENTITIES)

    assert result.logo == LOGO
    assert result.inner.opponent.logo == LOGO
    assert result.inner.spare is None
    assert [s.logo for s in result.sides] == [LOGO, None]
    assert result.sides[0].colors == IDENTITIES["OKC"].colors
    assert isinstance(result, Root)


def test_with_identities_reaches_a_playoff_team_and_a_detail_team() -> None:
    class Teams(FeedModel):
        playoff: PlayoffTeam
        detail: DetailTeam

    model = Teams(
        playoff=PlayoffTeam(code="OKC", name=None, city=None, colors=BUILT),
        detail=DetailTeam.model_validate(
            {"code": "OKC", "name": "Thunder", "city": "Oklahoma City", "record": None}
        ),
    )

    result = with_identities(model, IDENTITIES)

    assert result.playoff.logo == LOGO and result.playoff.colors == BUILT
    assert result.detail.logo == LOGO


def test_with_identities_stamps_the_players_of_a_search_list() -> None:
    class Players(FeedModel):
        players: list[SearchPlayerTeam]

    result = with_identities(
        Players(players=[SearchPlayerTeam(code="OKC", primary=None)]), IDENTITIES
    )

    assert result.players[0].logo == LOGO


def test_with_identities_returns_a_validated_model_and_rejects_nothing_valid() -> None:
    model = Root(
        code="OKC", inner=Inner(opponent=a_game_team("OKC")), sides=[a_game_team("OKC")]
    )

    with_identities(model, IDENTITIES)

    with pytest.raises(ValidationError):
        Root.model_validate({"code": "OKC", "logo": {"light": "no"}})


def test_with_identities_stamps_a_root_that_holds_a_date() -> None:
    class Dated(FeedModel):
        at: dt.date
        code: str
        logo: TeamLogo | None = None

    result = with_identities(Dated(at=dt.date(2026, 1, 1), code="OKC"), IDENTITIES)

    assert result.logo == LOGO


AAA_LOGO = TeamLogo(light=HttpUrl("https://example.com/aaa.svg"), dark=None)
BBB_LOGO = TeamLogo(light=HttpUrl("https://example.com/bbb.svg"), dark=None)
SEASON_COLORS = TeamColors(primary="#111111", secondary=None)
SEASON_IDENTITIES = {
    "AAA": TeamIdentity(code="AAA", logo=AAA_LOGO, colors=SEASON_COLORS),
    "BBB": TeamIdentity(code="BBB", logo=BBB_LOGO, colors=SEASON_COLORS),
}


def with_row(
    payload: dict[str, Any], teams: list[str], codes: list[str | None] | None
) -> dict[str, Any]:
    seasons = payload["seasons"]
    seasons["playoffs"] = split(["2025-26"])
    for rows in (
        seasons["regular"]["perGame"],
        seasons["regular"]["totals"],
        seasons["playoffs"]["perGame"],
        seasons["playoffs"]["totals"],
    ):
        row = rows[0]
        row["teams"] = teams
        if codes is not None:
            row["seasonCodes"] = codes
    return payload


def test_with_identities_gives_each_season_row_the_logo_of_each_current_team() -> None:
    payload = with_row(valid_player(), ["AAA", "BBB"], ["AAA", "BBB"])

    result = with_identities(PlayerFeed.model_validate(payload), SEASON_IDENTITIES)

    for rows in (
        result.seasons.regular.per_game,
        result.seasons.regular.totals,
        result.seasons.playoffs.per_game,
        result.seasons.playoffs.totals,
    ):
        assert rows[0].logos == [AAA_LOGO, BBB_LOGO]


def test_with_identities_nulls_the_logo_of_a_historical_unknown_or_unidentified_team() -> (
    None
):
    payload = with_row(valid_player(), ["AAA", "BBB", "CCC"], ["OLD", None, "CCC"])

    result = with_identities(PlayerFeed.model_validate(payload), SEASON_IDENTITIES)

    assert result.seasons.regular.per_game[0].logos == [None, None, None]


def test_with_identities_nulls_every_logo_of_a_row_without_season_codes() -> None:
    payload = with_row(valid_player(), ["AAA", "BBB"], None)

    result = with_identities(PlayerFeed.model_validate(payload), SEASON_IDENTITIES)

    assert result.seasons.regular.per_game[0].logos == [None, None]


def test_with_identities_reads_a_stored_player_feed_without_logos() -> None:
    payload = with_row(valid_player(), ["AAA"], ["AAA"])
    stored = PlayerFeed.model_validate(payload)
    assert stored.seasons.regular.per_game[0].logos is None

    result = with_identities(stored, SEASON_IDENTITIES)

    assert isinstance(result, PlayerFeed)
    assert result.seasons.regular.per_game[0].logos == [AAA_LOGO]


def test_with_identities_applies_the_same_rule_to_a_past_player_feed() -> None:
    payload = past_player()
    rows = payload["seasons"]["regular"]["perGame"]
    rows[0]["teams"], rows[0]["seasonCodes"] = ["AAA"], ["AAA"]
    rows[1]["teams"], rows[1]["seasonCodes"] = ["AAA"], ["OLD"]

    result = with_identities(PastPlayerFeed.model_validate(payload), SEASON_IDENTITIES)

    assert result.seasons.regular.per_game[0].logos == [AAA_LOGO]
    assert result.seasons.regular.per_game[1].logos == [None]


def test_with_identities_leaves_the_career_rows_alone() -> None:
    payload = with_row(valid_player(), ["AAA"], ["AAA"])
    before = PlayerFeed.model_validate(payload)

    result = with_identities(before, SEASON_IDENTITIES)

    assert result.seasons.regular.career == before.seasons.regular.career


# The colors are inputs of the rule; their OKLab numbers were checked by hand.
def accent_of(
    away: tuple[str, str | None] | None, home: tuple[str, str | None] | None
) -> tuple[str | None, str | None]:
    def colored(colors: tuple[str, str | None] | None) -> Opponent:
        return side(
            "AAA",
            colors=None
            if colors is None
            else TeamColors(primary=colors[0], secondary=colors[1]),
        )

    accent = game_accent(colored(away), colored(home))
    return accent.away, accent.home


@pytest.mark.parametrize(
    ("away", "home", "expected"),
    [
        (
            ("#006bb6", "#f58426"),
            ("#0077c0", "#c4ced4"),
            ("#f58426", "#0077c0"),
        ),
        (
            ("#00471b", "#eee1c6"),
            ("#008348", "#ffffff"),
            ("#eee1c6", "#008348"),
        ),
        (
            ("#552583", "#fdb927"),
            ("#29127a", "#e56020"),
            ("#552583", "#e56020"),
        ),
        (
            ("#007ac1", "#ef3b24"),
            ("#0e2240", "#fec524"),
            ("#007ac1", "#fec524"),
        ),
    ],
    ids=["NYK at ORL", "MIL at BOS", "LAL at PHX", "OKC at DEN"],
)
def test_the_accent_of_a_game(
    away: tuple[str, str | None],
    home: tuple[str, str | None],
    expected: tuple[str, str],
) -> None:
    assert accent_of(away, home) == expected


def test_a_team_without_a_secondary_keeps_its_primary() -> None:
    assert accent_of(("#101820", None), ("#0077c0", "#c4ced4")) == (
        "#101820",
        "#0077c0",
    )
    assert accent_of(("#0072ce", None), ("#0077c0", "#c4ced4")) == (
        "#0072ce",
        "#0077c0",
    )


def test_a_guest_side_gets_null_and_the_other_side_keeps_its_rule() -> None:
    assert accent_of(None, ("#29127a", "#e56020")) == (None, "#e56020")
    assert accent_of(("#00471b", "#eee1c6"), None) == ("#eee1c6", None)


def test_two_sides_with_no_colors_give_null_and_null() -> None:
    assert accent_of(None, None) == (None, None)


def test_oklab_of_white_and_black() -> None:
    white = oklab("#ffffff")
    black = oklab("#000000")

    assert white[0] == pytest.approx(1, abs=1e-6)
    assert black[0] == pytest.approx(0, abs=1e-6)


def test_team_colors_gives_the_identity_colors_of_a_league_side() -> None:
    built = PlayoffTeam(code="OKC", name=None, city=None, colors=BUILT)

    assert team_colors(side(), IDENTITIES) == IDENTITIES["OKC"].colors
    assert team_colors(built, IDENTITIES) == IDENTITIES["OKC"].colors


def test_team_colors_is_null_for_no_team_a_guest_a_historical_side_and_an_unknown_code() -> (
    None
):
    guest = Opponent(code="OKC", name="Gulls", city=None, guest=True)
    historical = side(season_code="SEA", historical=True)
    built = PlayoffTeam(code="BOS", name=None, city=None, colors=BUILT)

    assert team_colors(None, IDENTITIES) is None
    nameless = Opponent(code=None, name="X", city=None, guest=True)
    for team in (guest, historical, side("BOS"), nameless, built):
        assert team_colors(team, IDENTITIES) is None


def test_code_colors_follows_the_season_code() -> None:
    colors = IDENTITIES["OKC"].colors

    assert code_colors("OKC", None, IDENTITIES) == colors
    assert code_colors("OKC", "OKC", IDENTITIES) == colors
    assert code_colors("OKC", "SEA", IDENTITIES) is None
    assert code_colors(None, None, IDENTITIES) is None
    assert code_colors("BOS", None, IDENTITIES) is None


def test_resolved_color_gives_the_primary_the_secondary_of_a_dark_one_or_null() -> None:
    assert resolved_color(TeamColors(primary="#007ac1", secondary="#ef3b24")) == (
        "#007ac1"
    )
    assert resolved_color(TeamColors(primary="#101820", secondary="#ef3b24")) == (
        "#ef3b24"
    )
    assert resolved_color(None) is None


def test_pair_colors_orders_the_sides_and_keeps_a_missing_side_null() -> None:
    near = TeamColors(primary="#0077c0", secondary="#c4ced4")
    other = TeamColors(primary="#006bb6", secondary="#f58426")

    assert pair_colors(near, other) == ("#0077c0", "#f58426")
    assert pair_colors(other, near) == ("#006bb6", "#c4ced4")
    assert pair_colors(None, other) == (None, "#006bb6")
    assert pair_colors(near, None) == ("#0077c0", None)
