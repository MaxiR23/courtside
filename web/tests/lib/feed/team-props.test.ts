// web/tests/lib/feed/team-props.test.ts
//
// Tests for the props layer that turns the team feed into the team page props.
//
// Tested:
// - The header: record, win percentage, conference line and its four cells; the Streak cell
//   left out with a null streak, the Playoffs cell with a null playoff; Play-in and Out
// - The tabs in order and the mini text; sections without data leave with their tab
// - The overview: arena, coach line (singular and plural, and none without seasons), colors, the next game (tag, ET date,
//   "@ DEN", place and time lines, links) and a null next game
// - The record rows: large cells, detail cells, points and the signed differential
// - The leaders: order, a null number, a skipped null leader, a null section with three nulls
// - The roster: formatting, rookie, UTC birth date, null details, status tones, an empty roster
// - The injuries line with a missing number or position
// - The schedule: group labels, default group, played and upcoming rows, the next row, links,
//   every game tag; a null schedule
// - Spanish copy
//
// What is covered:
// - Pure logic on a recorded feed (tests/lib/feed/fixtures/team.json); no clock, no network
//
// Run with: cd web && pnpm exec vitest run tests/lib/feed/team-props.test.ts
//
// SEE: web/src/lib/feed/team-props.ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { GameTag, TeamFeed } from '../../../src/lib/contract/team';
import { gameTagLabel, toTeamView } from '../../../src/lib/feed/team-props';
import type { TeamView } from '../../../src/lib/team/types';
import { preferLanguages } from '../../prefer-languages';

const feed = (): TeamFeed =>
	JSON.parse(readFileSync(join(__dirname, 'fixtures', 'team.json'), 'utf8')) as TeamFeed;

const view = (source: TeamFeed = feed()): TeamView => toTeamView(source);

afterEach(() => {
	vi.restoreAllMocks();
});

describe('toTeamView header', () => {
	it('formats the record, win percentage, conference line and colors', () => {
		const { header } = view();
		expect(header.code).toBe('OKC');
		expect(header.city).toBe('Oklahoma City');
		expect(header.name).toBe('Thunder');
		expect(header.record).toBe('57–25');
		expect(header.winPct).toBe('69.5%');
		expect(header.conferenceLine).toBe('Western Conference · Northwest Division');
		expect(header.colors).toEqual({ primary: '#007AC1', secondary: '#EF3B24' });
	});

	it('has the Conference, Streak, Last 10 and Playoffs cells', () => {
		expect(view().header.cells).toEqual([
			{ label: 'Conference', value: '1st West', sub: null },
			{ label: 'Streak', value: 'W3', sub: null },
			{ label: 'Last 10', value: '8–2', sub: null },
			{ label: 'Playoffs', value: '1st seed', sub: null }
		]);
	});

	it('uses L for a losing streak and the eastern names', () => {
		const source = feed();
		source.conference = 'east';
		source.record.streak = { kind: 'loss', count: 2 };
		const { header } = view(source);
		expect(header.cells[1]?.value).toBe('L2');
		expect(header.conferenceLine).toBe('Eastern Conference · Northwest Division');
		expect(header.cells[0]?.value).toBe('1st East');
	});

	it('leaves out the Streak cell with a null streak and the Playoffs cell with a null playoff', () => {
		const source = feed();
		source.record.streak = null;
		source.record.playoff = null;
		expect(view(source).header.cells.map((cell) => cell.label)).toEqual(['Conference', 'Last 10']);
	});

	it('shows Play-in and Out', () => {
		const source = feed();
		source.record.playoff = { status: 'playin', seed: 8 };
		expect(view(source).header.cells.at(-1)?.value).toBe('Play-in');
		source.record.playoff = { status: 'out', seed: 12 };
		expect(view(source).header.cells.at(-1)?.value).toBe('Out');
	});
});

describe('toTeamView tabs', () => {
	it('lists every tab in order and the mini text', () => {
		const result = view();
		expect(result.tabs.map((tab) => tab.id)).toEqual([
			'overview',
			'record',
			'leaders',
			'roster',
			'injuries',
			'schedule'
		]);
		expect(result.tabs.map((tab) => tab.label)).toEqual([
			'Overview',
			'Record',
			'Leaders',
			'Roster',
			'Injuries',
			'Schedule'
		]);
		expect(result.mini).toBe('OKC 57–25');
	});

	it('hides the leaders, roster and schedule tabs with their sections', () => {
		const source = feed();
		source.leaders = { season: '2025-26', points: null, rebounds: null, assists: null };
		source.roster = [];
		source.schedule = null;
		const result = view(source);
		expect(result.tabs.map((tab) => tab.id)).toEqual(['overview', 'record', 'injuries']);
		expect(result.sections.leaders).toBeNull();
		expect(result.sections.roster).toBeNull();
		expect(result.sections.schedule).toBeNull();
	});
});

describe('toTeamView overview', () => {
	it('has the arena, coach and colors', () => {
		const { overview } = view().sections;
		expect(overview.arena).toEqual({
			name: 'Paycom Center',
			city: 'Oklahoma City, OK',
			photo: 'https://example.com/arena/okc.jpg'
		});
		expect(overview.coach).toEqual({
			label: 'Head coach',
			value: 'Mark Daigneault',
			sub: '6 seasons as NBA head coach'
		});
		expect(overview.colors).toEqual([{ hex: '#007AC1' }, { hex: '#EF3B24' }]);
	});

	it('uses the singular for one season and hides a null coach', () => {
		const source = feed();
		source.coach = { name: 'Mark Daigneault', seasons: 1 };
		expect(view(source).sections.overview.coach?.sub).toBe('1 season as NBA head coach');
		source.coach = null;
		expect(view(source).sections.overview.coach).toBeNull();
	});

	it('gives the coach name alone when the seasons are null', () => {
		const source = feed();
		source.coach = { name: 'Jordan Sample', seasons: null };
		expect(view(source).sections.overview.coach).toEqual({
			label: 'Head coach',
			value: 'Jordan Sample',
			sub: null
		});
	});

	it('keeps the arena fields the feed leaves null', () => {
		const source = feed();
		source.arena = { name: 'Paycom Center', city: null, photoUrl: null };
		expect(view(source).sections.overview.arena).toEqual({
			name: 'Paycom Center',
			city: null,
			photo: null
		});
	});

	it('builds the next game card from the feed', () => {
		expect(view().sections.overview.nextGame).toEqual({
			gameId: 'g-next',
			linked: false,
			tag: 'NBA Cup',
			date: 'Wednesday, October 7',
			opponent: '@ DEN',
			place: 'Ball Arena · Denver, CO',
			time: '7:30 PM ET · Courtside TV'
		});
	});

	it('shows the arena alone, the time alone and a link when the game has detail', () => {
		const source = feed();
		const next = source.nextGame!;
		source.nextGame = {
			...next,
			city: null,
			broadcast: null,
			isHome: true,
			tag: null,
			detailAvailable: true
		};
		expect(view(source).sections.overview.nextGame).toMatchObject({
			linked: true,
			tag: null,
			opponent: 'vs DEN',
			place: 'Ball Arena',
			time: '7:30 PM ET'
		});
	});

	it('has no next game when the season is over', () => {
		const source = feed();
		source.nextGame = null;
		expect(view(source).sections.overview.nextGame).toBeNull();
	});
});

describe('toTeamView record', () => {
	it('has the large row with the win percentages', () => {
		expect(view().sections.record.large).toEqual([
			{ label: 'Overall', value: '57–25', sub: '69.5%' },
			{ label: 'Home', value: '32–9', sub: '78.0%' },
			{ label: 'Away', value: '25–16', sub: '61.0%' },
			{ label: 'Last 10', value: '8–2', sub: '80.0%' }
		]);
	});

	it('has the detail row', () => {
		expect(view().sections.record.detail).toEqual([
			{ label: 'Streak', value: 'W3', sub: null },
			{ label: 'Games behind', value: '0', sub: null },
			{ label: 'Playoff position', value: '1st seed', sub: null },
			{ label: 'Conference', value: '1st West', sub: null },
			{ label: 'Division', value: '1st Northwest', sub: null },
			{ label: 'Points for', value: '118.3', sub: '9,701' },
			{ label: 'Points against', value: '109.9', sub: '9,012' },
			{ label: 'Differential', value: '+8.4', sub: '+689' }
		]);
	});

	it('leaves out the streak and playoff position cells and keeps a negative differential', () => {
		const source = feed();
		source.record.streak = null;
		source.record.playoff = null;
		source.record.gamesBehind = 2.5;
		source.record.differential = { perGame: -3.25, total: -267 };
		const { detail } = view(source).sections.record;
		expect(detail.map((cell) => cell.label)).not.toContain('Streak');
		expect(detail.map((cell) => cell.label)).not.toContain('Playoff position');
		expect(detail.find((cell) => cell.label === 'Games behind')?.value).toBe('2.5');
		const differential = detail.find((cell) => cell.label === 'Differential');
		expect(differential?.value).toMatch(/^-3\.[23]/);
		expect(differential?.sub).toBe('-267');
	});
});

describe('toTeamView leaders', () => {
	it('lists points, rebounds and assists with one decimal', () => {
		const leaders = view().sections.leaders;
		expect(leaders?.meta).toBe('2025-26 · per game');
		expect(leaders?.cards).toEqual([
			{
				playerId: 'p-sga',
				label: 'Points',
				value: '31.8',
				name: 'Shai Gilgeous-Alexander',
				line: '#2 · Guard',
				photo: 'https://example.com/players/sga.png'
			},
			{
				playerId: 'p-holmgren',
				label: 'Rebounds',
				value: '8.9',
				name: 'Chet Holmgren',
				line: 'Forward-Center',
				photo: null
			},
			{
				playerId: 'p-sga',
				label: 'Assists',
				value: '6.4',
				name: 'Shai Gilgeous-Alexander',
				line: '#2 · Guard',
				photo: 'https://example.com/players/sga.png'
			}
		]);
	});

	it('skips a null leader', () => {
		const source = feed();
		source.leaders.rebounds = null;
		expect(view(source).sections.leaders?.cards.map((card) => card.label)).toEqual([
			'Points',
			'Assists'
		]);
	});
});

describe('toTeamView roster', () => {
	it('formats a full player', () => {
		expect(view().sections.roster?.[0]).toEqual({
			id: 'p-sga',
			name: 'Shai Gilgeous-Alexander',
			photo: 'https://example.com/players/sga.png',
			number: '2',
			position: 'G',
			height: '6-6',
			weight: '195',
			age: '27',
			born: 'Jul 12, 1998',
			birthplace: 'Toronto, Canada',
			college: 'Kentucky',
			experience: '7',
			status: { label: 'Active', tone: 'muted' }
		});
	});

	it('keeps the feed order, shows R for a rookie and maps the status tones', () => {
		const roster = view().sections.roster ?? [];
		expect(roster.map((row) => row.id)).toEqual(['p-sga', 'p-holmgren', 'p-rookie', 'p-unknown']);
		expect(roster[2]?.experience).toBe('R');
		expect(roster[1]?.status).toEqual({ label: 'Out', tone: 'out' });
		expect(roster[2]?.status).toEqual({ label: 'Questionable', tone: 'ink' });
	});

	it('maps every injury status to a tone', () => {
		const source = feed();
		const base = source.roster[0]!;
		source.roster = (['doubtful', 'probable', 'day-to-day'] as const).map((status) => ({
			...base,
			status
		}));
		expect((view(source).sections.roster ?? []).map((row) => row.status.tone)).toEqual([
			'ink',
			'muted',
			'muted'
		]);
	});

	it('keeps null details null', () => {
		expect(view().sections.roster?.[3]).toMatchObject({
			photo: null,
			number: null,
			position: null,
			height: null,
			weight: null,
			age: null,
			born: null,
			birthplace: null,
			college: null,
			experience: null
		});
	});
});

describe('toTeamView injuries', () => {
	it('builds the line from the number and position, with either missing', () => {
		const injuries = view().sections.injuries;
		expect(injuries[0]).toEqual({
			name: 'Chet Holmgren',
			line: '#7 · F-C',
			status: 'out',
			comment: 'Hip, out for the season'
		});
		expect(injuries[1]).toEqual({
			name: 'Nikola Rookie',
			line: 'G',
			status: 'questionable',
			comment: null
		});
	});

	it('has no line with neither a number nor a position, and an empty list stays empty', () => {
		const source = feed();
		source.injuries = [{ ...source.injuries[0]!, number: null, position: null }];
		expect(view(source).sections.injuries[0]?.line).toBeNull();
		source.injuries = [];
		expect(view(source).sections.injuries).toEqual([]);
	});
});

describe('toTeamView schedule', () => {
	it('labels the groups and takes the default from the feed', () => {
		const schedule = view().sections.schedule;
		expect(schedule?.groups.map((group) => [group.key, group.label])).toEqual([
			['2025-10', 'Oct'],
			['2025-11', 'Nov'],
			['playoffs', 'Playoffs']
		]);
		expect(schedule?.defaultKey).toBe('2025-11');
	});

	it('shows a played win with its score and side, linked from detailAvailable', () => {
		const row = view().sections.schedule?.groups[0]?.rows[0];
		expect(row).toEqual({
			gameId: 'g-won',
			linked: true,
			weekday: 'Thu',
			date: 'Oct 23',
			opponent: 'vs HOU',
			tags: [],
			next: false,
			outcome: {
				kind: 'played',
				result: 'win',
				resultLabel: 'W',
				score: '118–104',
				side: 'Home'
			}
		});
	});

	it('shows a played loss unlinked, and upcoming rows with the time and broadcast', () => {
		const rows = view().sections.schedule?.groups[1]?.rows ?? [];
		expect(rows[0]).toMatchObject({
			linked: false,
			opponent: '@ DEN',
			outcome: { kind: 'played', result: 'loss', resultLabel: 'L', score: '99–104', side: 'Away' }
		});
		expect(rows[1]?.outcome).toEqual({
			kind: 'upcoming',
			time: '7:30 PM ET',
			broadcast: 'Courtside TV'
		});
		expect(rows[2]?.outcome).toEqual({ kind: 'upcoming', time: '8:00 PM ET', broadcast: null });
	});

	it('marks the next row and tags it after the game tag', () => {
		const rows = view().sections.schedule?.groups[1]?.rows ?? [];
		expect(rows.map((row) => row.next)).toEqual([false, true, false]);
		expect(rows[1]?.tags).toEqual(['NBA Cup', 'Next']);
		expect(rows[0]?.tags).toEqual([]);
	});

	it('tags a playoff game with its conference, round and game', () => {
		expect(view().sections.schedule?.groups[2]?.rows[0]?.tags).toEqual(['West R1 · G3']);
	});

	it('shows only the result when a played game has a null score', () => {
		const source = feed();
		const game = source.schedule?.groups[0]?.games[0];
		if (game) game.opponentScore = null;
		const row = view(source).sections.schedule?.groups[0]?.rows[0];
		expect(row?.outcome).toMatchObject({
			kind: 'played',
			result: 'win',
			resultLabel: 'W',
			score: null
		});
	});

	it('is null without a schedule', () => {
		const source = feed();
		source.schedule = null;
		expect(view(source).sections.schedule).toBeNull();
	});
});

describe('gameTagLabel', () => {
	const tag = (partial: Partial<GameTag>): GameTag => ({
		kind: 'playoffs',
		conference: null,
		round: null,
		game: null,
		...partial
	});

	it.each([
		[{ kind: 'cup' }, 'NBA Cup'],
		[{ kind: 'allstar' }, 'All-Star'],
		[{ kind: 'playoffs', conference: 'west', round: 1, game: 4 }, 'West R1 · G4'],
		[{ kind: 'playoffs', conference: 'east', round: 3 }, 'East R3'],
		[{ kind: 'playoffs', round: 4, game: 2 }, 'Finals · G2'],
		[{ kind: 'playoffs' }, 'Playoffs'],
		[{ kind: 'playoffs', game: 1 }, 'Playoffs · G1']
	] as [Partial<GameTag>, string][])('labels %j as %s', (partial, label) => {
		expect(gameTagLabel(tag(partial))).toBe(label);
	});
});

describe('toTeamView in Spanish', () => {
	it('translates the copy', () => {
		preferLanguages(['es']);
		const source = feed();
		source.nextGame = null;
		const result = view(source);
		expect(result.header.conferenceLine).toBe('Conferencia Oeste · División Northwest');
		expect(result.header.cells[0]?.value).toBe('1.º Oeste');
		expect(result.header.cells[1]?.value).toBe('G3');
		expect(result.header.cells[3]?.value).toBe('1.º puesto');
		expect(result.sections.overview.nextGame).toBeNull();
		expect(result.sections.leaders?.meta).toBe('2025-26 · por partido');
		expect(result.sections.schedule?.groups[2]?.rows[0]?.tags).toEqual(['Oeste R1 · P3']);
		expect(result.tabs[0]?.label).toBe('Resumen');
		expect(result.sections.overview.coach?.sub).toBe(
			'6 temporadas como entrenador principal en la NBA'
		);
	});

	it('translates the cup tag', () => {
		preferLanguages(['es']);
		expect(gameTagLabel({ kind: 'cup', conference: null, round: null, game: null })).toBe(
			'Copa NBA'
		);
	});
});
