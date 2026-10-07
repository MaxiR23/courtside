import type {
	Game,
	GamesFeed,
	Highlight,
	Leader as FeedLeader,
	Star,
	Team,
	TeamStats
} from '#lib/contract/games.ts';
import { formatDateParts } from '#lib/format/locale.ts';
import type { HeroGame, HeroPlayer, HeroStatus } from '#lib/hero/types.ts';
import { m } from '#lib/paraglide/messages.js';
import type {
	GameDetails,
	GameHighlights,
	HighlightVideo,
	Leader,
	PanelPlayer,
	ScheduleDay,
	ScheduleGame,
	ScheduleTeam,
	TeamStatLine
} from '#lib/schedule/types.ts';

const TODAY_INDEX = 3; // the middle of the seven days, as in DayStrip
const DAYS = 7;
const TIME_ZONE = 'America/New_York';

export type HomeView = {
	today: Date; // days[3], the middle day
	heroGames: HeroGame[]; // the games of today in feed order, without postponed and canceled ones
	days: ScheduleDay[]; // seven days
	updatedMinutesAgo: number;
};

// Games that will not be played today are not in the hero rotation (ADR 0012).
const OFF_HERO: ReadonlySet<Game['status']> = new Set(['postponed', 'canceled']);

type Options = { videoPlatformName?: string };

// A live or final game without the fields its status requires: the feed cannot be shown.
class IncompleteGame extends Error {}

function required<T>(value: T | null): T {
	if (value === null) throw new IncompleteGame('A game lacks a field its status requires');
	return value;
}

function localDate(isoDate: string): Date {
	const [year, month, day] = isoDate.split('-').map(Number);
	return new Date(year, month - 1, day);
}

export function tipParts(startTime: string): { tipTime: string; tipSuffix: string } {
	const parts = formatDateParts(new Date(startTime), {
		timeZone: TIME_ZONE,
		hour: 'numeric',
		minute: '2-digit'
	});
	let tipTime = '';
	let dayPeriod = '';
	for (const part of parts) {
		if (part.type === 'dayPeriod') dayPeriod = part.value;
		else if (!dayPeriod) tipTime += part.value;
	}
	return {
		tipTime: tipTime.trim(),
		tipSuffix: [dayPeriod, m.time_eastern()].filter(Boolean).join(' ')
	};
}

function periodLabel(period: number): string {
	if (period <= 4) return m.status_quarter({ number: period });
	if (period === 5) return m.panel_line_score_overtime();
	return m.panel_line_score_overtime_n({ number: period - 4 });
}

function scheduleTeam(team: Team): ScheduleTeam {
	return { code: team.code, name: team.name, city: team.city };
}

function panelPlayer(star: Star): PanelPlayer {
	return {
		firstName: star.firstName,
		lastName: star.lastName,
		teamCode: star.teamCode,
		photo: star.photoUrl
	};
}

function heroPlayer(star: Star, team: Team): HeroPlayer {
	return {
		firstName: star.firstName,
		lastName: star.lastName,
		shortName: star.shortName,
		teamCode: star.teamCode,
		teamName: `${team.city} ${team.name}`,
		photo: star.photoUrl
	};
}

function leader(entry: FeedLeader): Leader {
	const space = entry.displayName.indexOf(' ');
	return {
		firstName: space === -1 ? entry.displayName : entry.displayName.slice(0, space),
		lastName: space === -1 ? '' : entry.displayName.slice(space + 1),
		teamCode: entry.teamCode,
		photo: entry.photoUrl,
		points: entry.points,
		rebounds: entry.rebounds,
		assists: entry.assists
	};
}

function statLine(stats: TeamStats): TeamStatLine {
	return {
		fieldGoalPct: stats.fieldGoalPct,
		threePointPct: stats.threePointPct,
		rebounds: stats.rebounds,
		assists: stats.assists,
		turnovers: stats.turnovers
	};
}

function withAutoplay(embedUrl: string): string {
	const url = new URL(embedUrl);
	url.searchParams.set('autoplay', '1');
	return url.toString();
}

export function video(highlight: Highlight): HighlightVideo {
	return {
		id: highlight.embedUrl,
		title: highlight.title,
		channel: highlight.channel,
		thumbnail: highlight.thumbnailUrl,
		embedUrl: withAutoplay(highlight.embedUrl)
	};
}

function playedDetails(game: Game, highlights?: GameHighlights): GameDetails {
	const lineScore = required(game.lineScore);
	const leaders = required(game.leaders);
	const teamStats = required(game.teamStats);
	return {
		kind: 'played',
		periods: { away: [...lineScore.away], home: [...lineScore.home] },
		leaders: { away: leader(leaders.away), home: leader(leaders.home) },
		stats: { away: statLine(teamStats.away), home: statLine(teamStats.home) },
		...(highlights ? { highlights } : {})
	};
}

function finalDetails(game: Game, highlights?: GameHighlights): GameDetails {
	switch (game.statsAvailability) {
		case 'available':
			return playedDetails(game, highlights);
		case 'pending':
		case 'unavailable': {
			const lineScore = required(game.lineScore);
			return {
				kind: 'final-without-stats',
				periods: { away: [...lineScore.away], home: [...lineScore.home] },
				statsAvailability: game.statsAvailability,
				...(highlights ? { highlights } : {})
			};
		}
		default:
			throw new IncompleteGame('A final game lacks its stats availability');
	}
}

function scheduleGame(game: Game, options: Options): ScheduleGame {
	const base = { id: game.id, away: scheduleTeam(game.away), home: scheduleTeam(game.home) };
	switch (game.status) {
		case 'scheduled':
			return {
				...base,
				status: { state: 'scheduled', ...tipParts(game.startTime), network: game.broadcast },
				details: {
					kind: 'scheduled',
					venue: game.venue,
					playersToWatch: {
						away: panelPlayer(game.stars.away),
						home: panelPlayer(game.stars.home)
					}
				}
			};
		case 'live': {
			const score = required(game.score);
			return {
				...base,
				status: {
					state: 'live',
					period: periodLabel(required(game.period)),
					clock: required(game.clock),
					awayScore: score.away,
					homeScore: score.home
				},
				details: playedDetails(game)
			};
		}
		case 'final': {
			const score = required(game.score);
			const highlights: GameHighlights | undefined = options.videoPlatformName
				? {
						platform: options.videoPlatformName,
						searchUrl: required(game.highlightsSearchUrl),
						videos: game.highlights.map(video)
					}
				: undefined;
			return {
				...base,
				status: {
					state: 'final',
					awayScore: score.away,
					homeScore: score.home,
					winner: required(game.winner)
				},
				details: finalDetails(game, highlights)
			};
		}
		default:
			return { ...base, status: { state: game.status } };
	}
}

function heroGame(game: Game): HeroGame {
	const status: HeroStatus = game.status === 'scheduled' ? 'tonight' : game.status;
	const { tipTime, tipSuffix } = tipParts(game.startTime);
	return {
		id: game.id,
		status,
		tipTime: `${tipTime} ${tipSuffix}`,
		arena: game.venue,
		away: { name: game.away.name, star: heroPlayer(game.stars.away, game.away) },
		home: { name: game.home.name, star: heroPlayer(game.stars.home, game.home) }
	};
}

/** Turns the games feed into the home page props, or null when it cannot be shown. */
export function toHomeView(feed: GamesFeed, receivedAt: Date, options: Options): HomeView | null {
	if (feed.days.length !== DAYS) return null;
	try {
		const days = feed.days.map((day) => ({
			date: localDate(day.date),
			games: day.games.map((game) => scheduleGame(game, options))
		}));
		const today = feed.days[TODAY_INDEX];
		const generatedAt = new Date(feed.generatedAt).getTime();
		return {
			today: days[TODAY_INDEX].date,
			heroGames: today.games.filter((game) => !OFF_HERO.has(game.status)).map(heroGame),
			days,
			updatedMinutesAgo: Math.max(0, Math.floor((receivedAt.getTime() - generatedAt) / 60_000))
		};
	} catch (error) {
		if (error instanceof IncompleteGame) return null;
		throw error;
	}
}
