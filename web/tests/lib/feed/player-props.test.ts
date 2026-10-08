// web/tests/lib/feed/player-props.test.ts
//
// Tests for the props layer that turns the player feed into the player page props.
//
// Tested:
// - The header: line, status tag, injury card, hero stats (rank sub-line, null rank, null summary)
// - The tabs in order and the mini name; sections without data leave with their tab
// - The profile cells: formatting, sub-lines, a null draft, null fields leaving their cell
// - The next game, the live card view and its null line
// - The last 5 rows: result, date, opponent, score, tag, points line and links
// - The averages: season sub-lines, a null row, the Career accent, formatting
// - Season by season: columns, combined teams, the Career row, playoffs, made–attempted
// - The milestones, the game log filters and rows, the awards
// - Spanish copy
//
// What is covered:
// - Pure logic on a recorded feed (tests/lib/feed/fixtures/player.json); no clock, no network
//
// Run with: cd web && pnpm exec vitest run tests/lib/feed/player-props.test.ts
//
// SEE: web/src/lib/feed/player-props.ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { PlayerFeed } from '../../../src/lib/contract/player';
import { toPlayerView } from '../../../src/lib/feed/player-props';
import type { PlayerView } from '../../../src/lib/player/types';
import { preferLanguages } from '../../prefer-languages';

const feed = (): PlayerFeed =>
	JSON.parse(readFileSync(join(__dirname, 'fixtures', 'player.json'), 'utf8')) as PlayerFeed;

const view = (source: PlayerFeed = feed()): PlayerView => toPlayerView(source);

const LINE = {
	points: 14,
	fieldGoalsMade: 7,
	fieldGoalsAttempted: 15,
	threePointsMade: 1,
	threePointsAttempted: 4,
	freeThrowsMade: 3,
	freeThrowsAttempted: 4,
	offensiveRebounds: 1,
	defensiveRebounds: 3,
	rebounds: 4,
	assists: 5,
	turnovers: 2,
	steals: 1,
	blocks: 0,
	fouls: 2,
	playerId: 'p-2',
	displayName: 'S. Gilgeous-Alexander',
	starter: true,
	minutes: '24:10',
	plusMinus: 6,
	photoUrl: 'https://example.com/players/p-2.png'
};

const liveFeed = (period = 3, line: typeof LINE | null = LINE): PlayerFeed => {
	const source = feed();
	source.live = {
		gameId: 'g-live',
		opponent: 'DEN',
		isHome: false,
		period,
		clock: '4:12',
		teamScore: 78,
		opponentScore: 74,
		line
	};
	return source;
};

afterEach(() => {
	vi.restoreAllMocks();
});

describe('toPlayerView header', () => {
	it('builds the line, names, team tag, Active status and photo', () => {
		const { header } = view();
		expect(header.firstName).toBe('Shai');
		expect(header.lastName).toBe('Gilgeous-Alexander');
		expect(header.line).toBe('#2 · Guard · Oklahoma City Thunder');
		expect(header.teamCode).toBe('OKC');
		expect(header.status).toEqual({ label: 'Active', injured: false });
		expect(header.photo).toBe('https://example.com/players/p-2.png');
		expect(header.injury).toBeNull();
	});

	it('leaves a null number out of the line', () => {
		const source = feed();
		source.number = null;
		expect(view(source).header.line).toBe('Guard · Oklahoma City Thunder');
	});

	it('shows the injury status in the tag and the injury card with the Eastern update time', () => {
		const source = feed();
		source.injury = {
			status: 'questionable',
			comment: 'Left ankle sprain',
			updatedAt: '2026-10-07T19:15:00Z'
		};
		const { header } = view(source);
		expect(header.status).toEqual({ label: 'Questionable', injured: true });
		expect(header.injury).toEqual({
			status: 'questionable',
			comment: 'Left ankle sprain',
			updated: 'Updated Oct 7 · 3:15 PM ET'
		});
	});

	it('keeps a null injury comment', () => {
		const source = feed();
		source.injury = { status: 'out', comment: null, updatedAt: '2026-10-07T19:15:00Z' };
		expect(view(source).header.injury?.comment).toBeNull();
	});

	it('has the four hero stats with the rank sub-lines', () => {
		const { stats } = view().header;
		expect(stats?.label).toBe('2025-26 · per game');
		expect(stats?.cells).toEqual([
			{ label: 'Points', value: '31.8', sub: '1st in NBA' },
			{ label: 'Rebounds', value: '4.9', sub: '41st in NBA' },
			{ label: 'Assists', value: '6.4', sub: '5th in NBA' },
			{ label: 'FG%', value: '47.3%', sub: '12th in NBA' }
		]);
	});

	it('uses the ordinal forms and gives a null rank no sub-line', () => {
		const source = feed();
		source.summary!.points.rank = 2;
		source.summary!.rebounds.rank = 3;
		source.summary!.assists.rank = null;
		const cells = view(source).header.stats?.cells;
		expect(cells?.[0]?.sub).toBe('2nd in NBA');
		expect(cells?.[1]?.sub).toBe('3rd in NBA');
		expect(cells?.[2]?.sub).toBeNull();
	});

	it('has no stats with a null summary', () => {
		const source = feed();
		source.summary = null;
		expect(view(source).header.stats).toBeNull();
	});
});

describe('toPlayerView tabs', () => {
	it('lists the tabs in order with the mini name', () => {
		const result = view();
		expect(result.tabs.map((tab) => tab.id)).toEqual([
			'profile',
			'averages',
			'seasons',
			'milestones',
			'game-log',
			'awards'
		]);
		expect(result.tabs.map((tab) => tab.label)).toEqual([
			'Profile',
			'Averages',
			'Seasons',
			'Milestones',
			'Game log',
			'Awards'
		]);
		expect(result.mini).toBe('#2 S. Gilgeous-Alexander');
	});

	it('leaves the number out of the mini name when it is null', () => {
		const source = feed();
		source.number = null;
		expect(view(source).mini).toBe('S. Gilgeous-Alexander');
	});

	it('hides each section without data together with its tab', () => {
		const ids = (source: PlayerFeed) => view(source).tabs.map((tab) => tab.id);
		const noMilestones = feed();
		noMilestones.milestones = null;
		expect(ids(noMilestones)).not.toContain('milestones');
		const noLog = feed();
		noLog.gameLog = null;
		expect(ids(noLog)).not.toContain('game-log');
		const emptyLog = feed();
		emptyLog.gameLog = { season: '2025-26', entries: [] };
		expect(ids(emptyLog)).not.toContain('game-log');
		const noAwards = feed();
		noAwards.awards = [];
		expect(ids(noAwards)).not.toContain('awards');
		const noAverages = feed();
		noAverages.averages = { regular: null, playoffs: null, career: null };
		expect(ids(noAverages)).not.toContain('averages');
		const noSeasons = feed();
		noSeasons.seasons.regular = { perGame: [], totals: [], career: null };
		noSeasons.profile.seasons = null;
		noSeasons.profile.debutSeason = null;
		expect(ids(noSeasons)).not.toContain('seasons');
		expect(ids(noSeasons)).toContain('profile');
	});
});

describe('toPlayerView profile', () => {
	it('formats every cell with its sub-line', () => {
		expect(view().sections.profile.cells).toEqual([
			{ label: 'Height', value: '6\'6"', sub: '198 cm' },
			{ label: 'Weight', value: '195 lb', sub: '88 kg' },
			{ label: 'Born', value: 'July 12, 1998', sub: 'Age 28' },
			{ label: 'Birthplace', value: 'Hamilton, Ontario', sub: 'Canada' },
			{ label: 'College', value: 'Kentucky', sub: null },
			{ label: 'Draft', value: '2018 · Round 1 · Pick 11', sub: 'Charlotte Hornets' },
			{ label: 'Seasons', value: '3', sub: 'Debut 2018-19' }
		]);
	});

	it('shows Undrafted for a null draft', () => {
		const source = feed();
		source.profile.draft = null;
		const cell = view(source).sections.profile.cells.find((c) => c.label === 'Draft');
		expect(cell).toEqual({ label: 'Draft', value: 'Undrafted', sub: null });
	});

	it('removes only the cell of a null field and keeps the order', () => {
		const source = feed();
		source.profile.height = null;
		source.profile.college = null;
		source.profile.birthplace = null;
		source.profile.age = null;
		const cells = view(source).sections.profile.cells;
		expect(cells.map((cell) => cell.label)).toEqual(['Weight', 'Born', 'Draft', 'Seasons']);
		expect(cells[1]?.sub).toBeNull();
	});

	it('hides the Born cell without a birth date and the Seasons cell without a count', () => {
		const source = feed();
		source.profile.birthDate = null;
		source.profile.seasons = null;
		source.profile.debutSeason = null;
		const labels = view(source).sections.profile.cells.map((cell) => cell.label);
		expect(labels).not.toContain('Born');
		expect(labels).not.toContain('Seasons');
	});
});

describe('toPlayerView next game and live', () => {
	it('builds the next game unlinked when the detail is not available', () => {
		const { nextGame, live } = view().sections.profile;
		expect(live).toBeNull();
		expect(nextGame).toMatchObject({
			gameId: 'g-6',
			linked: false,
			opponent: 'vs DEN',
			time: '7:30 PM ET · Courtside TV'
		});
	});

	it('links the next game only with the detail available', () => {
		const source = feed();
		source.nextGame!.detailAvailable = true;
		expect(view(source).sections.profile.nextGame?.linked).toBe(true);
	});

	it('has a null next game when the feed has none', () => {
		const source = feed();
		source.nextGame = null;
		expect(view(source).sections.profile.nextGame).toBeNull();
	});

	it('builds the live view with the five line cells', () => {
		const { live } = view(liveFeed()).sections.profile;
		expect(live).toEqual({
			gameId: 'g-live',
			opponent: '@ DEN',
			score: '78–74',
			clock: 'Q3 · 4:12',
			line: [
				{ label: 'MIN', value: '24:10', sub: null },
				{ label: 'PTS', value: '14', sub: null },
				{ label: 'REB', value: '4', sub: null },
				{ label: 'AST', value: '5', sub: null },
				{ label: 'FG', value: '7–15', sub: null }
			]
		});
	});

	it('shows overtime periods in the clock', () => {
		expect(view(liveFeed(5)).sections.profile.live?.clock).toBe('OT1 · 4:12');
	});

	it('has a null line when the player is not in the box score', () => {
		expect(view(liveFeed(3, null)).sections.profile.live?.line).toBeNull();
	});
});

describe('toPlayerView last games', () => {
	it('formats each row and links only with the detail available', () => {
		const { recent } = view().sections.profile;
		expect(recent).toHaveLength(5);
		expect(recent[0]).toEqual({
			gameId: 'g-5',
			linked: true,
			result: 'win',
			resultLabel: 'W',
			date: 'Apr 29',
			opponent: '@ MEM',
			score: '118–104',
			tag: 'West R1 · G4',
			points: '31',
			line: '8 REB · 6 AST'
		});
		expect(recent[1]).toMatchObject({ result: 'loss', resultLabel: 'L', opponent: 'vs MEM' });
		expect(recent[1]?.linked).toBe(false);
		expect(recent[2]?.tag).toBeNull();
		expect(recent[4]?.tag).toBe('NBA Cup');
	});

	it('is empty when the feed has no last games', () => {
		const source = feed();
		source.lastGames = [];
		expect(view(source).sections.profile.recent).toEqual([]);
	});
});

describe('toPlayerView averages', () => {
	it('has the three rows with season sub-lines and the 12 columns', () => {
		const averages = view().sections.averages;
		expect(averages?.columns.map((c) => c.label)).toEqual([
			'GP',
			'MIN',
			'FG%',
			'3P%',
			'FT%',
			'REB',
			'AST',
			'BLK',
			'STL',
			'PF',
			'TOV',
			'PTS'
		]);
		expect(averages?.rows.map((r) => [r.label, r.sub, r.accent])).toEqual([
			['Regular season', '2025-26', false],
			['Playoffs', '2024-25', false],
			['Career', null, true]
		]);
		expect(averages?.rows[0]?.cells).toEqual([
			'70',
			'34.2',
			'47.3%',
			'35.0%',
			'89.8%',
			'4.9',
			'6.4',
			'0.9',
			'1.7',
			'2.6',
			'2.4',
			'31.8'
		]);
	});

	it('shows a dash in every cell of a null row and takes the other row season', () => {
		const source = feed();
		source.averages.playoffs = null;
		const row = view(source).sections.averages?.rows[1];
		expect(row?.cells).toEqual(Array(12).fill('—'));
		expect(row?.sub).toBe('2025-26');
	});

	it('has no season sub-line when both season rows are null', () => {
		const source = feed();
		source.averages.regular = null;
		source.averages.playoffs = null;
		const rows = view(source).sections.averages?.rows;
		expect(rows?.[0]?.sub).toBeNull();
		expect(rows?.[1]?.sub).toBeNull();
	});
});

describe('toPlayerView seasons', () => {
	it('has MIN in per game and not in totals', () => {
		const seasons = view().sections.seasons;
		const per = seasons?.regular.perGame.columns.map((c) => c.label);
		const tot = seasons?.regular.totals.columns.map((c) => c.label);
		expect(per).toContain('MIN');
		expect(tot).not.toContain('MIN');
		expect(per).toHaveLength(18);
		expect(tot).toHaveLength(17);
	});

	it('lists the seasons newest first with the teams and the Career row last', () => {
		const rows = view().sections.seasons?.regular.perGame.rows;
		expect(rows?.map((r) => [r.label, r.sub])).toEqual([
			['2025-26', 'OKC'],
			['2024-25', 'LAC · OKC'],
			['2018-19', 'LAC'],
			['Career', null]
		]);
	});

	it('formats made–attempted with one decimal per game and whole in totals', () => {
		const seasons = view().sections.seasons;
		expect(seasons?.regular.perGame.rows[0]?.cells.slice(0, 5)).toEqual([
			'70',
			'70',
			'34.2',
			'10.1–20.3',
			'49.8%'
		]);
		expect(seasons?.regular.totals.rows[0]?.cells.slice(0, 5)).toEqual([
			'70',
			'70',
			'650–1,300',
			'50.0%',
			'98–280'
		]);
	});

	it('has the playoffs split, and null without playoff seasons', () => {
		expect(view().sections.seasons?.playoffs?.perGame.rows.map((r) => r.label)).toEqual([
			'2024-25',
			'Career'
		]);
		const source = feed();
		source.seasons.playoffs = { perGame: [], totals: [], career: null };
		expect(view(source).sections.seasons?.playoffs).toBeNull();
	});
});

describe('toPlayerView milestones', () => {
	it('has the eight cells in order with the career sub-line and the season meta', () => {
		const milestones = view().sections.milestones;
		expect(milestones?.meta).toBe('2025-26');
		expect(milestones?.cells.map((c) => c.label)).toEqual([
			'Double-doubles',
			'Triple-doubles',
			'Disqualifications',
			'Ejections',
			'Technical fouls',
			'Flagrant fouls',
			'AST/TO',
			'STL/TO'
		]);
		expect(milestones?.cells[0]).toEqual({
			label: 'Double-doubles',
			value: '12',
			sub: 'Career 75'
		});
		expect(milestones?.cells[6]).toEqual({ label: 'AST/TO', value: '2.67', sub: 'Career 1.92' });
	});
});

describe('toPlayerView game log', () => {
	it('lists All, Regular season, NBA Cup and Playoffs with their rows', () => {
		const log = view().sections.gameLog;
		expect(log?.meta).toBe('2025-26');
		expect(log?.filters.map((f) => [f.id, f.label, f.rows.length])).toEqual([
			['all', 'All', 6],
			['regular', 'Regular season', 3],
			['cup', 'NBA Cup', 1],
			['playoffs', 'Playoffs', 2]
		]);
	});

	it('does not list a filter without rows', () => {
		const source = feed();
		source.gameLog!.entries = source.gameLog!.entries.filter((e) => e.kind !== 'playoffs');
		const ids = view(source).sections.gameLog?.filters.map((f) => f.id);
		expect(ids).toEqual(['all', 'regular', 'cup']);
	});

	it('builds the row header, tag line, result cell and links', () => {
		const rows = view().sections.gameLog?.filters[0]?.rows;
		expect(rows?.[0]).toMatchObject({
			label: 'Apr 29 · @ MEM',
			sub: 'West R1 · G4',
			link: { gameId: 'g-5', linked: true }
		});
		expect(rows?.[0]?.cells[0]).toEqual({ mark: 'W', win: true, text: '118–104' });
		expect(rows?.[1]?.link?.linked).toBe(false);
		expect(rows?.[1]?.cells[0]).toEqual({ mark: 'L', win: false, text: '101–108' });
	});

	it('shows the date alone for the All-Star game, with its tag', () => {
		const row = view().sections.gameLog?.filters[0]?.rows.find((r) => r.key === 'g-as');
		expect(row?.label).toBe('Feb 15');
		expect(row?.sub).toBe('All-Star');
	});

	it('formats the stat cells', () => {
		const row = view().sections.gameLog?.filters[0]?.rows[0];
		expect(row?.cells.slice(1)).toEqual([
			'34',
			'11–21',
			'52.4%',
			'2–5',
			'40.0%',
			'7–8',
			'87.5%',
			'8',
			'6',
			'1',
			'2',
			'2',
			'3',
			'31'
		]);
	});
});

describe('toPlayerView awards', () => {
	it('shows the count, the name and the seasons joined', () => {
		expect(view().sections.awards).toEqual([
			{ count: '2×', name: 'NBA Most Valuable Player', seasons: '2024-25 · 2025-26' },
			{ count: '3×', name: 'All-NBA First Team', seasons: '2022-23 · 2023-24 · 2024-25' }
		]);
	});
});

describe('toPlayerView in Spanish', () => {
	it('translates the copy', () => {
		preferLanguages(['es']);
		const source = liveFeed(3, null);
		source.injury = { status: 'out', comment: null, updatedAt: '2026-10-07T19:15:00Z' };
		const result = view(source);
		expect(result.tabs.map((tab) => tab.label)).toEqual([
			'Perfil',
			'Promedios',
			'Temporadas',
			'Hitos',
			'Registro de partidos',
			'Premios'
		]);
		expect(result.header.stats?.cells[1]?.sub).toBe('41.º en la NBA');
		expect(result.header.injury?.updated).toBe('Actualizado 7 oct · 15:15 ET');
		expect(result.sections.profile.cells[5]?.value).toBe('2018 · Ronda 1 · Elección 11');
		expect(result.sections.profile.live?.clock).toBe('C3 · 4:12');
	});
});
