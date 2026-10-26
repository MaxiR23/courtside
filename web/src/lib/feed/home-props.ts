import type {
	ComingUpItem,
	ComingUpKey,
	ComingUpStatus,
	FinalsPath,
	HomeFeed,
	HomeLeaderCategory,
	HomeLeadersTitle,
	HomeScenario,
	LastGame,
	LastGameLabel,
	LastGamesTitle,
	PathRound,
	Side
} from '#lib/contract/home.ts';
import type { Conference, StandingsFeed } from '#lib/contract/standings.ts';
import { toStandingsView } from '#lib/feed/standings-props.ts';
import { feedDate } from '#lib/feed/team-props.ts';
import { tipParts } from '#lib/feed/props.ts';
import { formatNumber } from '#lib/format/locale.ts';
import type {
	ComingUpItemView,
	ComingUpTarget,
	EmptyDayView,
	HomeLastGameSideView,
	HomeLastGamesView,
	HomeLeadersView,
	HomeStandingsView,
	NoGamesView
} from '#lib/home/types.ts';
import { m } from '#lib/paraglide/messages.js';
import { teamMark } from '#lib/team/mark.ts';

const DATE_SEPARATOR = ' – ';
const RECORD_SEPARATOR = '–';

// Positions in the feed's seed order (docs/api/standings.md); `/web` does not re-sort.
const TOP_ROWS = 6;
const PLAY_IN_ROWS = 10;

const MONTH_DAY: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' };

const SHORT_DAY: Intl.DateTimeFormatOptions = { weekday: 'short', month: 'short', day: 'numeric' };

const tags: Record<HomeScenario, () => string> = {
	offDay: m.home_scenario_off_day,
	allStarBreak: m.home_scenario_all_star_break,
	finalsPreview: m.home_scenario_finals_preview,
	offseason: m.home_scenario_offseason
};

const paragraphs: Record<HomeScenario, () => string> = {
	offDay: m.home_paragraph_off_day,
	allStarBreak: m.home_paragraph_all_star_break,
	finalsPreview: m.home_paragraph_finals_preview,
	offseason: m.home_paragraph_offseason
};

const titles: Record<ComingUpKey, () => string> = {
	openingNight: m.home_coming_up_opening_night,
	preseason: m.home_coming_up_preseason,
	cupGroupStage: m.home_coming_up_cup_group_stage,
	cupKnockout: m.home_coming_up_cup_knockout,
	cupFinal: m.home_coming_up_cup_final,
	allStar: m.home_coming_up_all_star,
	playIn: m.home_coming_up_play_in,
	playoffs: m.home_coming_up_playoffs,
	finals: m.home_coming_up_finals
};

const subs: Record<ComingUpKey, () => string> = {
	openingNight: m.home_coming_up_opening_night_sub,
	preseason: m.home_coming_up_preseason_sub,
	cupGroupStage: m.home_coming_up_cup_group_stage_sub,
	cupKnockout: m.home_coming_up_cup_knockout_sub,
	cupFinal: m.home_coming_up_cup_final_sub,
	allStar: m.home_coming_up_all_star_sub,
	playIn: m.home_coming_up_play_in_sub,
	playoffs: m.home_coming_up_playoffs_sub,
	finals: m.home_coming_up_finals_sub
};

const statusLabels: Record<ComingUpStatus, () => string> = {
	done: m.home_coming_up_status_done,
	now: m.home_coming_up_status_now,
	upcoming: m.home_coming_up_status_upcoming
};

// The link target of each key (ADR 0076); the pages themselves are resolved in ComingUp.
const targets: Record<ComingUpKey, ComingUpTarget | null> = {
	openingNight: null,
	preseason: null,
	cupGroupStage: 'cup',
	cupKnockout: 'cup',
	cupFinal: 'cup',
	allStar: 'allStar',
	playIn: 'playoffs',
	playoffs: 'playoffs',
	finals: 'playoffs'
};

const lastGamesTitles: Record<Exclude<LastGamesTitle['key'], 'daysAgo'>, () => string> = {
	lastNight: m.home_last_games_title_last_night,
	beforeTheBreak: m.home_last_games_title_before_the_break,
	conferenceFinals: m.home_last_games_title_conference_finals,
	lastGamesPlayed: m.home_last_games_title_last_games_played
};

const lastGameLabels: Record<LastGameLabel, () => string> = {
	final: m.home_last_games_label_final,
	finalOvertime: m.home_last_games_label_final_overtime,
	playIn: m.home_last_games_label_play_in,
	firstRound: m.home_last_games_label_first_round,
	conferenceSemifinals: m.home_last_games_label_conference_semifinals,
	conferenceFinals: m.home_last_games_label_conference_finals,
	finals: m.home_last_games_label_finals
};

const conferenceLabels: Record<Conference, () => string> = {
	east: m.home_standings_east,
	west: m.home_standings_west
};

const roundLabels: Record<PathRound, () => string> = {
	firstRound: m.home_finals_path_round_first_round,
	conferenceSemifinals: m.home_finals_path_round_conference_semifinals,
	conferenceFinals: m.home_finals_path_round_conference_finals
};

const leaderCategories: Record<HomeLeaderCategory, () => string> = {
	points: m.home_leaders_points,
	rebounds: m.home_leaders_rebounds,
	assists: m.home_leaders_assists,
	blocks: m.home_leaders_blocks
};

const leaderTitles: Record<Exclude<HomeLeadersTitle, 'previousSeason'>, () => string> = {
	season: m.home_leaders_title_season,
	playoffs: m.home_leaders_title_playoffs
};

function itemDate(item: ComingUpItem): string {
	const start = feedDate(item.startDate, MONTH_DAY);
	return item.endDate === null
		? start
		: `${start}${DATE_SEPARATOR}${feedDate(item.endDate, MONTH_DAY)}`;
}

function toItemView(item: ComingUpItem): ComingUpItemView {
	return {
		key: item.key,
		date: itemDate(item),
		title: titles[item.key](),
		sub: subs[item.key](),
		status: item.status,
		statusLabel: statusLabels[item.status](),
		target: targets[item.key]
	};
}

/**
 * Turns the home feed into the hero of a day with no games. `todayId` is the games feed's today,
 * so the date shows even without the home feed (null: loading, failed or not configured).
 */
export function toNoGamesView(todayId: string, feed: HomeFeed | null): NoGamesView {
	const date = feedDate(todayId, { weekday: 'long', month: 'long', day: 'numeric' });
	if (feed === null) {
		return { date, tag: null, paragraph: null, nextTipOff: null, broadcast: null, comingUp: null };
	}
	const { nextGame } = feed;
	let nextTipOff: string | null = null;
	if (nextGame !== null) {
		const { tipTime, tipSuffix } = tipParts(nextGame.firstTipOff);
		nextTipOff = m.home_next_tip_off({
			day: feedDate(nextGame.date, SHORT_DAY),
			time: `${tipTime} ${tipSuffix}`
		});
	}
	return {
		date,
		tag: tags[feed.scenario](),
		paragraph: paragraphs[feed.scenario](),
		nextTipOff,
		broadcast: nextGame?.broadcast ?? null,
		comingUp: feed.comingUp === null ? null : feed.comingUp.map(toItemView)
	};
}

function lastGamesTitle(title: LastGamesTitle): string {
	if (title.key !== 'daysAgo') return lastGamesTitles[title.key]();
	// The contract gives the number of days with this key; without it no number is invented.
	return title.days === null
		? m.home_last_games_title_last_games_played()
		: m.home_last_games_title_days_ago({ days: formatNumber(title.days) });
}

function lastGameLabel(game: LastGame): string {
	const round = lastGameLabels[game.label]();
	return game.gameNumber === null
		? round
		: m.home_last_games_label_game({ round, number: formatNumber(game.gameNumber) });
}

function lastGameSide(game: LastGame, which: Side): HomeLastGameSideView {
	return {
		team: teamMark(game[which]),
		score: game.score[which],
		loser: game.winner !== null && game.winner !== which,
		accent: game.accent?.[which] ?? null
	};
}

/** Turns the last games of the home feed into the section; null: nothing to show. */
export function toLastGamesView(feed: HomeFeed | null): HomeLastGamesView | null {
	const lastGames = feed?.lastGames;
	if (!lastGames) return null;
	return {
		title: lastGamesTitle(lastGames.title),
		count: m.schedule_game_count({ count: lastGames.games.length }),
		games: lastGames.games.map((game) => ({
			id: game.id,
			label: lastGameLabel(game),
			away: lastGameSide(game, 'away'),
			home: lastGameSide(game, 'home')
		}))
	};
}

/** The box of a selected day with no games; null without the home feed. */
export function toEmptyDayView(feed: HomeFeed | null): EmptyDayView | null {
	if (feed === null) return null;
	const title = m.home_empty_day_title();
	const { nextGame } = feed;
	if (nextGame === null) return { title, text: m.home_empty_day_none(), goTo: null };
	const day = feedDate(nextGame.date, SHORT_DAY);
	return {
		title,
		text: m.home_empty_day_next({
			day,
			games: m.schedule_game_count({ count: nextGame.gameCount })
		}),
		goTo: nextGame.inGamesWindow
			? { date: nextGame.date, label: m.home_empty_day_go_to({ day }) }
			: null
	};
}

/**
 * In the offseason the seven days are empty and say nothing (`docs/design.md`, Home with no
 * games, Schedule).
 */
export function hidesSchedule(feed: HomeFeed | null): boolean {
	return feed?.scenario === 'offseason';
}

function compactStandings(feed: StandingsFeed): HomeStandingsView | null {
	const groups = toStandingsView(feed).conference; // same order as feed.conferences
	const tabs = feed.conferences.flatMap((conference, i) => {
		const rows = (groups[i]?.rows ?? []).map((row) => ({
			code: row.code,
			seed: row.seed,
			team: row.team,
			record: `${row.wins}${RECORD_SEPARATOR}${row.losses}`,
			gamesBehind: row.gamesBehind
		}));
		if (rows.length === 0) return [];
		return [
			{
				key: conference.key,
				label: conferenceLabels[conference.key](),
				rows: rows.slice(0, TOP_ROWS),
				playIn: rows.slice(TOP_ROWS, PLAY_IN_ROWS)
			}
		];
	});
	return tabs.length === 0 ? null : { kind: 'standings', title: m.home_standings_title(), tabs };
}

function finalsPathView(path: FinalsPath): HomeStandingsView {
	return {
		kind: 'finalsPath',
		title: m.home_finals_path_title(),
		tabs: path.finalists.map((finalist, i) => ({
			key: finalist.team.code ?? `finalist-${i}`,
			team: teamMark(finalist.team),
			series: finalist.series.map((series) => ({
				key: series.round,
				round: roundLabels[series.round](),
				opponent: teamMark(series.opponent),
				accent: series.accent,
				result: series.result,
				won: series.won
			}))
		}))
	};
}

/**
 * The Finals preview draws each finalist's path and nothing else; any other scenario, or no home
 * feed, draws the compact standings (`docs/design.md`, Home with no games, Standings (compact)).
 */
export function toHomeStandingsView(
	home: HomeFeed | null,
	standings: StandingsFeed | null
): HomeStandingsView | null {
	if (home?.scenario === 'finalsPreview') {
		return home.finalsPath ? finalsPathView(home.finalsPath) : null;
	}
	return standings ? compactStandings(standings) : null;
}

function leadersTitle(title: HomeLeadersTitle, seasonLabel: string | null): string {
	if (title !== 'previousSeason') return leaderTitles[title]();
	// The contract gives the label with this key; without it no season is invented.
	return seasonLabel === null
		? m.home_leaders_title_last_season()
		: m.home_leaders_title_previous_season({ season: seasonLabel });
}

/** Turns the home feed's leaders into the section, one row per category sent; null: nothing to show. */
export function toHomeLeadersView(home: HomeFeed | null): HomeLeadersView | null {
	const leaders = home?.leaders;
	if (!leaders) return null;
	return {
		title: leadersTitle(leaders.title, leaders.seasonLabel),
		leaders: leaders.categories.map((leader) => ({
			key: leader.category,
			category: leaderCategories[leader.category](),
			team: leader.team
				? teamMark({ code: leader.team.code, name: null, city: null, logo: leader.team.logo })
				: null,
			name: leader.name,
			photo: leader.photoUrl,
			value: leader.value
		}))
	};
}
