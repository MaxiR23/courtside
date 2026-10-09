import type { Clinch, Conference, StandingsFeed, StandingsRow } from '#lib/contract/standings.ts';
import { formatNumber } from '#lib/format/locale.ts';
import { m } from '#lib/paraglide/messages.js';
import type {
	ClinchTone,
	ClinchView,
	StandingsKeyEntry,
	StandingsLine,
	StandingsRowView,
	StandingsView
} from '#lib/standings/types.ts';

const NO_VALUE = '—';
const PLAYOFF_SEED = 6;
const PLAY_IN_SEED = 10;

const CONFERENCE_LONG: Record<Conference, () => string> = {
	east: m.team_conference_east,
	west: m.team_conference_west
};

const CLINCH_TONES: Record<Clinch, ClinchTone> = {
	'*': 'accent',
	z: 'accent',
	y: 'accent',
	x: 'accent',
	xp: 'ink',
	pb: 'ink',
	e: 'muted'
};

const CLINCH_LABELS: Record<Clinch, () => string> = {
	'*': m.clinch_star,
	z: m.clinch_z,
	y: m.clinch_y,
	x: m.clinch_x,
	xp: m.clinch_xp,
	pb: m.clinch_pb,
	e: m.clinch_e
};

const CLINCH_ORDER: Clinch[] = ['*', 'z', 'y', 'x', 'xp', 'pb', 'e'];

function clinchView(code: Clinch): ClinchView {
	return { code, tone: CLINCH_TONES[code] };
}

function lastIndexOfSeed(seeds: (number | null)[], seed: number): number {
	return seeds.lastIndexOf(seed);
}

/** The dashed line goes under the last row of seed 6 and under the last row of seed 10. */
export function lineAfter(seeds: (number | null)[]): (StandingsLine | null)[] {
	const playoff = lastIndexOfSeed(seeds, PLAYOFF_SEED);
	const playIn = lastIndexOfSeed(seeds, PLAY_IN_SEED);
	return seeds.map((_, index) => {
		if (index === playoff) return 'playoff';
		if (index === playIn) return 'play-in';
		return null;
	});
}

function streakView(streak: StandingsRow['streak']): StandingsRowView['streak'] {
	if (!streak) return { text: NO_VALUE, win: false };
	const count = formatNumber(streak.count);
	const win = streak.kind === 'win';
	return { text: win ? m.team_streak_win({ count }) : m.team_streak_loss({ count }), win };
}

function rowView(row: StandingsRow, line: StandingsLine | null): StandingsRowView {
	const { primary, secondary } = row.colors;
	return {
		code: row.code,
		seed: row.seed === null ? NO_VALUE : String(row.seed),
		city: row.city,
		name: row.name,
		strip: primary !== null && secondary !== null ? { primary, secondary } : null,
		clinch: row.clinch ? clinchView(row.clinch) : null,
		eliminated: row.clinch === 'e',
		wins: String(row.wins),
		losses: String(row.losses),
		pct: row.pct ?? NO_VALUE,
		gamesBehind: row.gamesBehind ?? NO_VALUE,
		streak: streakView(row.streak),
		home: row.home,
		away: row.away,
		lastTen: row.lastTen,
		division: row.division,
		conference: row.conference,
		pointsFor: row.pointsFor,
		pointsAgainst: row.pointsAgainst,
		differential: { value: row.differential.value, accent: row.differential.nonNegative },
		total: { value: row.total.value, accent: row.total.nonNegative },
		lineAfter: line
	};
}

function keyEntries(): StandingsKeyEntry[] {
	return CLINCH_ORDER.map((code) => ({ clinch: clinchView(code), label: CLINCH_LABELS[code]() }));
}

/** Turns the standings feed into the page props. Rows and groups keep the feed's order. */
export function toStandingsView(feed: StandingsFeed): StandingsView {
	return {
		header: {
			season: feed.season,
			stateLine:
				feed.state === 'final'
					? m.standings_state_final()
					: m.standings_state_live({ count: feed.gamesPlayed })
		},
		conference: feed.conferences.map((c) => {
			const lines = lineAfter(c.teams.map((t) => t.seed));
			return {
				key: c.key,
				title: CONFERENCE_LONG[c.key](),
				meta: m.standings_meta_conference({ count: c.teamCount }),
				rows: c.teams.map((t, i) => rowView(t, lines[i] ?? null))
			};
		}),
		division: feed.divisions.map((d) => ({
			key: d.name,
			title: d.name,
			meta: m.standings_meta_division({ conference: CONFERENCE_LONG[d.conference]() }),
			rows: d.teams.map((t) => rowView(t, null))
		})),
		key: keyEntries()
	};
}
