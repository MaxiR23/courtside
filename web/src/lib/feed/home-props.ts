import type {
	ComingUpItem,
	ComingUpKey,
	ComingUpStatus,
	HomeFeed,
	HomeScenario,
	LastGame,
	LastGameLabel,
	LastGamesTitle,
	Side
} from '#lib/contract/home.ts';
import { feedDate } from '#lib/feed/team-props.ts';
import { tipParts } from '#lib/feed/props.ts';
import { formatNumber } from '#lib/format/locale.ts';
import type {
	ComingUpItemView,
	ComingUpTarget,
	EmptyDayView,
	HomeLastGameSideView,
	HomeLastGamesView,
	NoGamesView
} from '#lib/home/types.ts';
import { m } from '#lib/paraglide/messages.js';
import { teamMark } from '#lib/team/mark.ts';

const DATE_SEPARATOR = ' – ';

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
