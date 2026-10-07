import type { DetailTeam, GameDetailFeed } from '#lib/contract/game-detail.ts';
import { formatDate, formatNumber } from '#lib/format/locale.ts';
import { tipParts } from '#lib/feed/props.ts';
import type {
	GameHeaderView,
	GameLayout,
	GameView,
	HeaderTeam,
	InfoCell,
	MiniScore,
	ScoreboardCenter,
	SectionId,
	SectionTab,
	StatusLine,
	VenueStrip
} from '#lib/game/types.ts';
import { m } from '#lib/paraglide/messages.js';

const TIME_ZONE = 'America/New_York';
const SEPARATOR = ' · ';
const FIRST_OVERTIME = 5; // periods 1 to 4 are quarters

type Options = { videoPlatformName?: string };

// A live or final game without the fields its status requires: the feed cannot be shown.
class IncompleteGame extends Error {}

function required<T>(value: T | null): T {
	if (value === null) throw new IncompleteGame('A game lacks a field its status requires');
	return value;
}

function layoutOf(status: GameDetailFeed['status']): GameLayout {
	if (status === 'live') return 'live';
	if (status === 'final') return 'final';
	return 'pre-game';
}

function dateText(startTime: string): string {
	return formatDate(new Date(startTime), {
		timeZone: TIME_ZONE,
		weekday: 'long',
		month: 'long',
		day: 'numeric'
	});
}

function periodLabel(period: number): string {
	if (period < FIRST_OVERTIME) return m.status_quarter({ number: period });
	return m.game_overtime({ number: period - FIRST_OVERTIME + 1 });
}

function periodText(period: number, clock: string): string {
	return `${periodLabel(period)}${SEPARATOR}${clock}`;
}

function statusLine(feed: GameDetailFeed): StatusLine {
	const arena = feed.venue.name;
	switch (feed.status) {
		case 'live':
			return {
				state: 'live',
				text: [periodText(required(feed.period), required(feed.clock)), arena].join(SEPARATOR)
			};
		case 'final':
			return {
				state: 'final',
				text: [m.status_final(), dateText(feed.startTime), arena].join(SEPARATOR)
			};
		default:
			return { state: feed.status, text: [dateText(feed.startTime), arena].join(SEPARATOR) };
	}
}

function headerTeam(team: DetailTeam): HeaderTeam {
	return {
		code: team.code,
		name: team.name,
		city: team.city,
		record: `${formatNumber(team.record.wins)}–${formatNumber(team.record.losses)}`
	};
}

function center(feed: GameDetailFeed): ScoreboardCenter {
	switch (feed.status) {
		case 'live':
		case 'final': {
			const score = required(feed.score);
			let loser: 'away' | 'home' | null = null;
			if (feed.status === 'final') {
				const winner = required(feed.winner);
				loser = winner === feed.away.code ? 'home' : 'away';
			}
			return { kind: 'score', away: score.away, home: score.home, loser };
		}
		case 'scheduled':
		case 'delayed':
			return {
				kind: 'tip-off',
				...tipParts(feed.startTime),
				broadcast: feed.broadcast,
				delayed: feed.status === 'delayed'
			};
		default:
			return { kind: 'none' };
	}
}

function venueStrip(feed: GameDetailFeed): VenueStrip {
	const cells: InfoCell[] = [];
	if (feed.status !== 'postponed' && feed.status !== 'canceled') {
		const { tipTime, tipSuffix } = tipParts(feed.startTime);
		cells.push({
			label: m.panel_tip_off(),
			value: `${tipTime} ${tipSuffix}`,
			sub: dateText(feed.startTime)
		});
	}
	cells.push({ label: m.panel_venue(), value: feed.venue.name, sub: feed.venue.city });
	if (feed.broadcast !== null) {
		cells.push({ label: m.panel_broadcast(), value: feed.broadcast, sub: null });
	}
	return { arena: feed.venue.name, city: feed.venue.city, photo: feed.venue.photoUrl, cells };
}

const TAB_LABELS: Record<SectionId, () => string> = {
	highlights: m.game_tab_highlights,
	players: m.game_tab_players,
	score: m.game_tab_score,
	'win-probability': m.game_tab_win_probability,
	'box-score': m.game_tab_box_score,
	injuries: m.game_tab_injuries,
	'last-games': m.game_tab_last_games,
	standings: m.game_tab_standings,
	'season-series': m.game_tab_season_series,
	videos: m.game_tab_videos
};

/** The sections of each layout, in the design's order. */
export const SECTION_TABS: Record<GameLayout, SectionId[]> = {
	'pre-game': ['players', 'injuries', 'last-games', 'standings', 'season-series'],
	live: ['score', 'win-probability', 'box-score', 'injuries'],
	final: [
		'highlights',
		'score',
		'win-probability',
		'box-score',
		'injuries',
		'season-series',
		'videos'
	]
};

// Whether the feed has data for a section. A null section is hidden, with its tab.
function hasData(feed: GameDetailFeed, id: SectionId, options: Options): boolean {
	switch (id) {
		case 'highlights':
			// As on the home: only with a configured platform and a search URL.
			return (
				Boolean(options.videoPlatformName) &&
				feed.highlights !== null &&
				feed.highlightsSearchUrl !== null
			);
		case 'players':
			return feed.stars !== null;
		case 'score':
			return feed.lineScore !== null;
		case 'win-probability':
			return feed.winProbability !== null;
		case 'box-score':
			return feed.boxScore !== null;
		case 'injuries':
			return feed.injuries !== null;
		case 'last-games':
			return feed.lastGames !== null;
		case 'standings':
			return feed.standings !== null;
		case 'season-series':
			return feed.seasonSeries !== null;
		case 'videos':
			return feed.videos !== null;
	}
}

function tabs(feed: GameDetailFeed, layout: GameLayout, options: Options): SectionTab[] {
	return SECTION_TABS[layout]
		.filter((id) => hasData(feed, id, options))
		.map((id) => ({
			id,
			label: id === 'season-series' && layout === 'final' ? m.game_tab_series() : TAB_LABELS[id]()
		}));
}

function miniScore(feed: GameDetailFeed): MiniScore | null {
	if (feed.status !== 'live' && feed.status !== 'final') return null;
	const score = required(feed.score);
	return { awayCode: feed.away.code, away: score.away, home: score.home, homeCode: feed.home.code };
}

function header(feed: GameDetailFeed, layout: GameLayout): GameHeaderView {
	return {
		layout,
		status: statusLine(feed),
		away: headerTeam(feed.away),
		home: headerTeam(feed.home),
		center: center(feed),
		venue: layout === 'pre-game' ? venueStrip(feed) : null
	};
}

/** Turns the game detail feed into the page props, or null when it cannot be shown. */
export function toGameView(feed: GameDetailFeed, options: Options): GameView | null {
	const layout = layoutOf(feed.status);
	try {
		return {
			header: header(feed, layout),
			tabs: tabs(feed, layout, options),
			miniScore: miniScore(feed)
		};
	} catch (error) {
		if (error instanceof IncompleteGame) return null;
		throw error;
	}
}
