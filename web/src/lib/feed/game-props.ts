import type {
	BoxScore,
	BoxScorePlayer,
	BoxScoreTotals,
	Conference,
	DetailTeam,
	GameDetailFeed,
	LastGame,
	Record as FeedRecord,
	SeriesGame,
	Star
} from '#lib/contract/game-detail.ts';
import { formatDate, formatNumber } from '#lib/format/locale.ts';
import { tipParts, video } from '#lib/feed/props.ts';
import type {
	BoxRow,
	BoxScoreSection,
	BoxScoreTeam,
	BoxTotals,
	DetailTeamStatLine,
	GameHeaderView,
	GameLayout,
	GameSections,
	GameView,
	HeaderTeam,
	InfoCell,
	InjuriesSection,
	InjuryTeam,
	LastGameRow,
	LastGamesSection,
	LastGamesTeam,
	LineScoreTeam,
	MiniScore,
	PlayersSection,
	ScoreSection,
	ScoreboardCenter,
	SeasonSeriesSection,
	SectionId,
	SectionTab,
	SeriesRow,
	StandingRow,
	StandingsSection,
	StarCard,
	StatLeads,
	StatusLine,
	VenueStrip,
	VideosSection,
	WinProbabilitySection
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

function record(r: FeedRecord): string {
	return `${formatNumber(r.wins)}–${formatNumber(r.losses)}`;
}

function headerTeam(team: DetailTeam): HeaderTeam {
	return {
		code: team.code,
		name: team.name,
		city: team.city,
		record: record(team.record)
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
			return (
				feed.lastGames !== null &&
				(feed.lastGames.away.length > 0 || feed.lastGames.home.length > 0)
			);
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

const percent = (v: number) =>
	formatNumber(v, { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 });
const wholePercent = (v: number) => formatNumber(v, { style: 'percent', maximumFractionDigits: 0 });

function lineScoreTeam(team: DetailTeam, periods: number[], total: number): LineScoreTeam {
	return { code: team.code, name: team.name, periods: [...periods], total };
}

function leadSide(feed: GameDetailFeed, code: string | null): 'away' | 'home' | null {
	if (code === feed.away.code) return 'away';
	if (code === feed.home.code) return 'home';
	return null;
}

function scoreSection(feed: GameDetailFeed): ScoreSection {
	const lineScore = required(feed.lineScore);
	const score = required(feed.score);
	const stats = feed.teamStats;
	return {
		lineScore: {
			away: lineScoreTeam(feed.away, lineScore.away, score.away),
			home: lineScoreTeam(feed.home, lineScore.home, score.home)
		},
		stats: stats && {
			away: { ...stats.away } satisfies DetailTeamStatLine,
			home: { ...stats.home } satisfies DetailTeamStatLine,
			leads: Object.fromEntries(
				Object.entries(stats.leaders).map(([key, code]) => [key, leadSide(feed, code)])
			) as StatLeads
		}
	};
}

function winProbabilitySection(feed: GameDetailFeed): WinProbabilitySection {
	const points = required(feed.winProbability);
	const latest = points[points.length - 1].homeWinProbability;
	let meta: string;
	if (feed.status === 'final') {
		meta = m.game_win_probability_final({ team: required(feed.winner) });
	} else if (latest > 0.5) {
		meta = `${feed.home.code} ${wholePercent(latest)}`;
	} else if (latest < 0.5) {
		meta = `${feed.away.code} ${wholePercent(1 - latest)}`;
	} else {
		meta = wholePercent(0.5);
	}
	return {
		awayCode: feed.away.code,
		homeCode: feed.home.code,
		middle: wholePercent(0.5),
		meta,
		points: points.map((p) => ({
			elapsedSeconds: p.elapsedSeconds,
			homeWinProbability: p.homeWinProbability
		}))
	};
}

type Shooting = { made: number; attempted: number };
const shooting = ({ made, attempted }: Shooting) =>
	`${formatNumber(made)}-${formatNumber(attempted)}`;

function boxRow(player: BoxScorePlayer): BoxRow {
	return {
		id: player.playerId,
		name: player.displayName,
		minutes: player.minutes,
		points: formatNumber(player.points),
		fieldGoals: shooting({ made: player.fieldGoalsMade, attempted: player.fieldGoalsAttempted }),
		threePoints: shooting({ made: player.threePointsMade, attempted: player.threePointsAttempted }),
		freeThrows: shooting({ made: player.freeThrowsMade, attempted: player.freeThrowsAttempted }),
		offensiveRebounds: formatNumber(player.offensiveRebounds),
		defensiveRebounds: formatNumber(player.defensiveRebounds),
		rebounds: formatNumber(player.rebounds),
		assists: formatNumber(player.assists),
		turnovers: formatNumber(player.turnovers),
		steals: formatNumber(player.steals),
		blocks: formatNumber(player.blocks),
		fouls: formatNumber(player.fouls),
		plusMinus: formatNumber(player.plusMinus, { signDisplay: 'exceptZero' }),
		plusMinusPositive: player.plusMinus > 0
	};
}

function boxTotals(totals: BoxScoreTotals): BoxTotals {
	return {
		points: formatNumber(totals.points),
		fieldGoals: shooting({ made: totals.fieldGoalsMade, attempted: totals.fieldGoalsAttempted }),
		threePoints: shooting({ made: totals.threePointsMade, attempted: totals.threePointsAttempted }),
		freeThrows: shooting({ made: totals.freeThrowsMade, attempted: totals.freeThrowsAttempted }),
		offensiveRebounds: formatNumber(totals.offensiveRebounds),
		defensiveRebounds: formatNumber(totals.defensiveRebounds),
		rebounds: formatNumber(totals.rebounds),
		assists: formatNumber(totals.assists),
		turnovers: formatNumber(totals.turnovers),
		steals: formatNumber(totals.steals),
		blocks: formatNumber(totals.blocks),
		fouls: formatNumber(totals.fouls),
		fieldGoalPct: percent(totals.fieldGoalPct),
		threePointPct: percent(totals.threePointPct),
		freeThrowPct: percent(totals.freeThrowPct)
	};
}

function boxTeam(team: DetailTeam, box: BoxScore['away']): BoxScoreTeam {
	return {
		code: team.code,
		name: team.name,
		starters: box.players.filter((p) => p.starter).map(boxRow),
		bench: box.players.filter((p) => !p.starter).map(boxRow),
		totals: boxTotals(box.totals)
	};
}

function boxScoreSection(feed: GameDetailFeed): BoxScoreSection {
	const box = required(feed.boxScore);
	return { away: boxTeam(feed.away, box.away), home: boxTeam(feed.home, box.home) };
}

// A contract date has no time: "2026-10-05" is UTC midnight, so it is formatted in UTC to keep the day.
function feedDate(date: string, options: Intl.DateTimeFormatOptions): string {
	return formatDate(new Date(date), { ...options, timeZone: 'UTC' });
}

const rowDate = (date: string) => feedDate(date, { month: 'short', day: 'numeric' });

function starCard(star: Star, team: DetailTeam): StarCard {
	return {
		firstName: star.firstName,
		lastName: star.lastName,
		teamCode: star.teamCode,
		photo: star.photoUrl,
		teamName: `${team.city} ${team.name}`
	};
}

function playersSection(feed: GameDetailFeed): PlayersSection {
	const stars = required(feed.stars);
	return { away: starCard(stars.away, feed.away), home: starCard(stars.home, feed.home) };
}

function injuryTeam(
	team: DetailTeam,
	list: NonNullable<GameDetailFeed['injuries']>['away']
): InjuryTeam {
	return {
		code: team.code,
		name: team.name,
		injuries: list.map((i) => ({ name: i.displayName, status: i.status, comment: i.comment }))
	};
}

function injuriesSection(feed: GameDetailFeed): InjuriesSection {
	const injuries = required(feed.injuries);
	return {
		away: injuryTeam(feed.away, injuries.away),
		home: injuryTeam(feed.home, injuries.home)
	};
}

function lastGameRow(game: LastGame): LastGameRow {
	const team = game.opponent;
	return {
		result: game.result,
		resultLabel: game.result === 'win' ? m.game_last_game_win() : m.game_last_game_loss(),
		date: rowDate(game.date),
		opponent: game.isHome ? m.game_last_game_home({ team }) : m.game_last_game_away({ team }),
		score: `${formatNumber(game.teamScore)}–${formatNumber(game.opponentScore)}`
	};
}

function lastGamesTeam(team: DetailTeam, games: readonly LastGame[]): LastGamesTeam {
	const rows = games.map(lastGameRow);
	return {
		code: team.code,
		name: team.name,
		strip: rows.map((row) => ({ result: row.result, label: row.resultLabel })).reverse(),
		rows
	};
}

function lastGamesSection(feed: GameDetailFeed): LastGamesSection {
	const lastGames = required(feed.lastGames);
	return {
		away: lastGamesTeam(feed.away, lastGames.away),
		home: lastGamesTeam(feed.home, lastGames.home)
	};
}

const CONFERENCE_LABELS: Record<Conference, () => string> = {
	east: m.game_conference_east,
	west: m.game_conference_west
};

function standingRow(
	team: DetailTeam,
	standing: NonNullable<GameDetailFeed['standings']>['away']
): StandingRow {
	return {
		code: team.code,
		name: team.name,
		conference: m.game_standings_rank({
			rank: standing.conferenceRank,
			conference: CONFERENCE_LABELS[standing.conference]()
		}),
		record: record(standing.record),
		home: record(standing.homeRecord),
		away: record(standing.awayRecord),
		lastTen: record(standing.lastTen)
	};
}

function standingsSection(feed: GameDetailFeed): StandingsSection {
	const standings = required(feed.standings);
	return {
		away: standingRow(feed.away, standings.away),
		home: standingRow(feed.home, standings.home)
	};
}

function seriesRow(game: SeriesGame): SeriesRow {
	return {
		date: rowDate(game.date),
		awayCode: game.away,
		awayPoints: game.score.away,
		homePoints: game.score.home,
		homeCode: game.home,
		arena: game.arena
	};
}

// An empty list is a first meeting. The leader compares the two win counts the feed sends.
function seriesSummary(feed: GameDetailFeed, awayWins: number, homeWins: number, played: number) {
	if (played === 0) return m.game_series_first_meeting();
	if (awayWins === homeWins) return m.game_series_tied({ wins: formatNumber(awayWins) });
	const awayLeads = awayWins > homeWins;
	return m.game_series_lead({
		team: awayLeads ? feed.away.code : feed.home.code,
		leading: formatNumber(Math.max(awayWins, homeWins)),
		trailing: formatNumber(Math.min(awayWins, homeWins))
	});
}

function seasonSeriesSection(feed: GameDetailFeed): SeasonSeriesSection {
	const series = required(feed.seasonSeries);
	const played = series.games.length;
	return {
		summary: seriesSummary(feed, series.awayWins, series.homeWins, played),
		meta: m.game_series_played({ played, total: series.totalGames }),
		games: series.games.map(seriesRow)
	};
}

function videosSection(feed: GameDetailFeed): VideosSection {
	return required(feed.videos).map((v) => ({
		title: v.title,
		duration: v.duration,
		thumbnail: v.thumbnailUrl,
		href: v.linkUrl
	}));
}

// A section's props exist only when its tab is shown, so a section hides together with its tab.
function sections(feed: GameDetailFeed, shown: SectionTab[], options: Options): GameSections {
	const has = (id: SectionId) => shown.some((tab) => tab.id === id);
	return {
		highlights:
			has('highlights') && feed.highlights !== null && feed.highlightsSearchUrl !== null
				? {
						platform: options.videoPlatformName ?? '',
						searchUrl: feed.highlightsSearchUrl,
						videos: feed.highlights.map(video)
					}
				: null,
		players: has('players') ? playersSection(feed) : null,
		score: has('score') ? scoreSection(feed) : null,
		winProbability: has('win-probability') ? winProbabilitySection(feed) : null,
		boxScore: has('box-score') ? boxScoreSection(feed) : null,
		injuries: has('injuries') ? injuriesSection(feed) : null,
		lastGames: has('last-games') ? lastGamesSection(feed) : null,
		standings: has('standings') ? standingsSection(feed) : null,
		seasonSeries: has('season-series') ? seasonSeriesSection(feed) : null,
		videos: has('videos') ? videosSection(feed) : null
	};
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
		const shown = tabs(feed, layout, options);
		return {
			header: header(feed, layout),
			tabs: shown,
			miniScore: miniScore(feed),
			sections: sections(feed, shown, options)
		};
	} catch (error) {
		if (error instanceof IncompleteGame) return null;
		throw error;
	}
}
