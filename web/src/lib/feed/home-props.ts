import type {
	ComingUpItem,
	ComingUpKey,
	ComingUpStatus,
	HomeFeed,
	HomeScenario
} from '#lib/contract/home.ts';
import { feedDate } from '#lib/feed/team-props.ts';
import { tipParts } from '#lib/feed/props.ts';
import type { ComingUpItemView, ComingUpTarget, NoGamesView } from '#lib/home/types.ts';
import { m } from '#lib/paraglide/messages.js';

const DATE_SEPARATOR = ' – ';

const MONTH_DAY: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' };

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
			day: feedDate(nextGame.date, { weekday: 'short', month: 'short', day: 'numeric' }),
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
