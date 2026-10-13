// web/tests/lib/feed/cup-props.test.ts
//
// Tests for the props layer that turns the Cup feed into the Cup page props.
//
// Tested:
// - The state line for each of the six stages, not drawn and a null first game date
// - The champion only when the Cup is complete
// - The four stages: a single date, a range, "TBD", and their status labels
// - The section order per stage (groups first in draw and group play, the bracket first after)
// - Group titles and the three metas; rows in feed order with every column, a — for each null
// - The streak and the accents; tags y, x, e, the eliminated row and no tag for null; the legend
// - The wild card tables: titles, the line only after rank 1, a — for a missing group
// - The games filters in order with the feed's counts, a round filter that drops empty days
// - Loser sides, scores only when set, the four status kinds, linked, not counted
// - Spanish copy of the state line, a group title and a stage label
//
// What is covered:
// - Pure logic on an invented feed (tests/lib/feed/fixtures/cup.json); no clock, no network
//
// Run with: cd web && pnpm exec vitest run tests/lib/feed/cup-props.test.ts
//
// SEE: web/src/lib/feed/cup-props.ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { CupFeed, CupStage } from '../../../src/lib/contract/cup';
import type { CupView } from '../../../src/lib/cup/types';
import { toCupView } from '../../../src/lib/feed/cup-props';
import { preferLanguages } from '../../prefer-languages';

const feed = (): CupFeed =>
	JSON.parse(readFileSync(join(__dirname, 'fixtures', 'cup.json'), 'utf8')) as CupFeed;

const view = (source: CupFeed = feed()): CupView => toCupView(source);

const atStage = (stage: CupStage, change: (f: CupFeed) => void = () => {}): CupView => {
	const f = feed();
	f.stage = stage;
	change(f);
	return view(f);
};

afterEach(() => {
	vi.restoreAllMocks();
});

describe('toCupView header', () => {
	it('writes the state line of group play with the games played', () => {
		const v = view();
		expect(v.header.season).toBe('2026-27');
		expect(v.header.stateLine).toBe('Group play · 16 of 60 games played');
		expect(v.bracketText).toBe(v.header.stateLine);
	});

	it('writes the state line of the draw with the first game date', () => {
		expect(atStage('draw').header.stateLine).toBe('Groups drawn · Play starts November 4');
	});

	it('writes a — for a first game date that is missing', () => {
		const v = atStage('draw', (f) => (f.firstGameDate = null));
		expect(v.header.stateLine).toBe('Groups drawn · Play starts —');
	});

	it('says the groups are not drawn yet before the draw', () => {
		const v = atStage('draw', (f) => (f.drawn = false));
		expect(v.header.stateLine).toBe('Groups not drawn yet');
		expect(v.drawn).toBe(false);
	});

	it('writes the state line of each knockout stage and of the complete Cup', () => {
		expect(atStage('quarterfinals').header.stateLine).toBe('Quarterfinals');
		expect(atStage('semifinals').header.stateLine).toBe('Semifinals');
		expect(atStage('championship').header.stateLine).toBe('Championship');
		expect(atStage('complete').header.stateLine).toBe('Complete');
	});

	it('has a champion only when the Cup is complete and the feed names one', () => {
		const champion = { code: 'QXA', name: 'Herons', city: 'Alderton', guest: false };
		expect(view().header.champion).toBeNull();
		expect(atStage('championship', (f) => (f.champion = champion)).header.champion).toBeNull();
		expect(atStage('complete', (f) => (f.champion = champion)).header.champion).toEqual(champion);
		expect(atStage('complete').header.champion).toBeNull();
	});

	it('keeps a guest champion marked as a guest', () => {
		const guest = { code: null, name: 'Visitors', city: 'Faraway', guest: true };
		const v = atStage('complete', (f) => (f.champion = guest));
		expect(v.header.champion).toEqual(guest);
	});
});

describe('toCupView stages', () => {
	it('keeps the four stages in order with labels, dates and status labels', () => {
		const stages = view().header.stages;
		expect(stages.map((s) => s.key)).toEqual([
			'group',
			'quarterfinals',
			'semifinals',
			'championship'
		]);
		expect(stages.map((s) => s.label)).toEqual([
			'Group play',
			'Quarterfinals',
			'Semifinals',
			'Championship'
		]);
		expect(stages.map((s) => s.statusLabel)).toEqual([
			'In progress',
			'Next',
			'Upcoming',
			'Upcoming'
		]);
		expect(stages.map((s) => s.status)).toEqual(['in_progress', 'next', 'upcoming', 'upcoming']);
	});

	it('writes a range, a single date and TBD', () => {
		expect(view().header.stages.map((s) => s.dates)).toEqual([
			'Nov 4 – Dec 2',
			'Dec 8',
			'TBD',
			'Dec 16'
		]);
	});

	it('writes the complete status label', () => {
		const v = atStage('complete', (f) => (f.stages[0].status = 'complete'));
		expect(v.header.stages[0]?.statusLabel).toBe('Complete');
	});
});

describe('toCupView sections', () => {
	it('draws the groups first in the draw and in group play', () => {
		const order = ['groups', 'wild-card', 'bracket', 'games'];
		expect(atStage('draw').sections).toEqual(order);
		expect(atStage('group').sections).toEqual(order);
	});

	it('draws the bracket first from the quarterfinals on', () => {
		const order = ['bracket', 'groups', 'wild-card', 'games'];
		for (const stage of ['quarterfinals', 'semifinals', 'championship', 'complete'] as const) {
			expect(atStage(stage).sections).toEqual(order);
		}
	});
});

describe('toCupView groups', () => {
	it('keeps the six groups in the feed order with a written title', () => {
		const v = view();
		expect(v.groups.map((g) => g.key)).toEqual([
			'east-a',
			'east-b',
			'east-c',
			'west-a',
			'west-b',
			'west-c'
		]);
		expect(v.groups.map((g) => g.title)).toEqual([
			'East Group A',
			'East Group B',
			'East Group C',
			'West Group A',
			'West Group B',
			'West Group C'
		]);
	});

	it('writes the meta: games played, final, or the team count', () => {
		const v = view();
		expect(v.groups[0]?.meta).toBe('6 of 10 games');
		expect(v.groups[1]?.meta).toBe('Final');
		expect(v.groups[2]?.meta).toBe('5 teams');
	});

	it('writes a singular team count', () => {
		const f = feed();
		f.groups[2].teams = [f.groups[2].teams[0]!];
		expect(view(f).groups[2]?.meta).toBe('1 team');
	});

	it('keeps the draw list for a group without rows and no rows', () => {
		const group = view().groups[2]!;
		expect(group.rows).toEqual([]);
		expect(group.teams).toHaveLength(5);
		expect(group.teams[0]).toEqual({
			code: 'SXA',
			name: 'Comets',
			city: 'Fairmont',
			guest: false
		});
	});

	it('maps every column of a row, in the feed order', () => {
		const rows = view().groups[0]!.rows;
		expect(rows.map((r) => r.team.code)).toEqual(['QXA', 'QXB', 'QXC', 'QXD', 'QXE']);
		expect(rows[0]).toEqual({
			team: { code: 'QXA', name: 'Herons', city: 'Alderton', guest: false },
			position: '1',
			record: '4-0',
			gamesBehind: '—',
			perGame: { value: '+12.5', accent: true },
			total: { value: '+50', accent: true },
			streak: { text: 'W4', win: true },
			pointsFor: '470',
			pointsAgainst: '420',
			home: '2-0',
			away: '2-0',
			overtime: '0-0',
			tag: { code: 'y', tone: 'accent' },
			eliminated: false
		});
	});

	it('marks a negative differential and a loss streak without accent', () => {
		const row = view().groups[0]!.rows[3]!;
		expect(row.perGame).toEqual({ value: '−9.0', accent: false });
		expect(row.total).toEqual({ value: '−36', accent: false });
		expect(row.streak).toEqual({ text: 'L4', win: false });
	});

	it('writes a — for every null of a row', () => {
		const row = view().groups[0]!.rows[4]!;
		expect(row).toMatchObject({
			position: '—',
			gamesBehind: '—',
			perGame: { value: '—', accent: false },
			total: { value: '—', accent: false },
			streak: { text: '—', win: false },
			pointsFor: '—',
			pointsAgainst: '—',
			home: '—',
			away: '—',
			overtime: '—',
			tag: null,
			eliminated: false
		});
	});

	it('maps the tags y, x and e, and the eliminated row', () => {
		const rows = view().groups[0]!.rows;
		expect(rows.map((r) => r.tag)).toEqual([
			{ code: 'y', tone: 'accent' },
			{ code: 'x', tone: 'accent' },
			null,
			{ code: 'e', tone: 'muted' },
			null
		]);
		expect(rows.map((r) => r.eliminated)).toEqual([false, false, false, true, false]);
	});

	it('lists the three tags in the legend', () => {
		expect(view().legend).toEqual([
			{ clinch: { code: 'y', tone: 'accent' }, label: 'Won group' },
			{ clinch: { code: 'x', tone: 'accent' }, label: 'Wild card' },
			{ clinch: { code: 'e', tone: 'muted' }, label: 'Eliminated' }
		]);
	});
});

describe('toCupView wild card', () => {
	it('keeps East then West with a conference title', () => {
		const v = view();
		expect(v.wildCard.map((t) => t.key)).toEqual(['east', 'west']);
		expect(v.wildCard.map((t) => t.title)).toEqual(['Eastern Conference', 'Western Conference']);
		expect(v.wildCard[1]?.rows).toEqual([]);
	});

	it('maps the rows and puts the line only after rank 1', () => {
		const rows = view().wildCard[0]!.rows;
		expect(rows.map((r) => r.rank)).toEqual(['1', '2', '3']);
		expect(rows.map((r) => r.lineAfter)).toEqual([true, false, false]);
		expect(rows[0]).toMatchObject({
			group: 'East Group A',
			record: '3-1',
			total: { value: '+16', accent: true },
			pointsFor: '440',
			tag: { code: 'x', tone: 'accent' }
		});
	});

	it('writes a — for a missing group, total and points', () => {
		expect(view().wildCard[0]!.rows[2]).toMatchObject({
			group: '—',
			total: { value: '—', accent: false },
			pointsFor: '—',
			tag: null
		});
	});
});

describe('toCupView games', () => {
	it('has one filter per key in order, with the feed counts', () => {
		const filters = view().filters;
		expect(filters.map((f) => f.key)).toEqual([
			'all',
			'group',
			'quarterfinals',
			'semifinals',
			'championship'
		]);
		expect(filters.map((f) => f.label)).toEqual([
			'All',
			'Group play',
			'Quarterfinals',
			'Semifinals',
			'Championship'
		]);
		expect(filters.map((f) => f.count)).toEqual(['6', '5', '0', '0', '1']);
	});

	it('keeps every day under All, with a long day heading', () => {
		const all = view().filters[0]!;
		expect(all.days.map((d) => d.key)).toEqual(['2026-11-04', '2026-11-07', '2026-12-16']);
		expect(all.days.map((d) => d.label)).toEqual([
			'Wednesday, November 4',
			'Saturday, November 7',
			'Wednesday, December 16'
		]);
		expect(all.days.map((d) => d.games.length)).toEqual([2, 3, 1]);
	});

	it('keeps only the games of a round and drops the days left empty', () => {
		const filters = view().filters;
		expect(filters[1]?.days.map((d) => d.key)).toEqual(['2026-11-04', '2026-11-07']);
		expect(filters[4]?.days.map((d) => d.key)).toEqual(['2026-12-16']);
		expect(filters[2]?.days).toEqual([]);
	});

	it('maps a final game: scores, the loser dimmed, linked and the stage label', () => {
		const game = view().filters[0]!.days[0]!.games[0]!;
		expect(game).toMatchObject({
			gameId: '9000001',
			linked: true,
			stageLabel: 'Group play',
			status: { kind: 'status', status: 'final' },
			broadcast: 'Courtside TV',
			notCounted: false
		});
		expect(game.away).toMatchObject({ score: '98', loser: true });
		expect(game.home).toMatchObject({ score: '110', loser: false });
	});

	it('maps a live game with no scores and no loser', () => {
		const game = view().filters[0]!.days[0]!.games[1]!;
		expect(game.status).toEqual({ kind: 'live' });
		expect(game.away).toMatchObject({ score: null, loser: false });
		expect(game.home).toMatchObject({ score: null, loser: false });
		expect(game.broadcast).toBeNull();
	});

	it('maps a scheduled game to its Eastern tip time, with and without broadcast', () => {
		const games = view().filters[0]!.days[1]!.games;
		expect(games[0]?.status).toEqual({ kind: 'time', text: '7:00 PM ET' });
		expect(games[0]?.broadcast).toBe('Courtside TV');
		expect(games[0]?.linked).toBe(false);
		expect(games[1]?.status).toEqual({ kind: 'time', text: '9:30 PM ET' });
		expect(games[1]?.broadcast).toBeNull();
	});

	it('maps a postponed game to its status', () => {
		const game = view().filters[0]!.days[1]!.games[2]!;
		expect(game.status).toEqual({ kind: 'status', status: 'postponed' });
	});

	it('maps delayed and canceled games to their status', () => {
		const f = feed();
		f.games.days[0]!.games[1]!.status = 'delayed';
		f.games.days[0]!.games[0]!.status = 'canceled';
		const games = view(f).filters[0]!.days[0]!.games;
		expect(games.map((g) => g.status)).toEqual([
			{ kind: 'status', status: 'canceled' },
			{ kind: 'status', status: 'delayed' }
		]);
	});

	it('marks the championship as not counted in standings', () => {
		const game = view().filters[4]!.days[0]!.games[0]!;
		expect(game.notCounted).toBe(true);
		expect(game.stageLabel).toBe('Championship');
	});

	it('has no days when the feed has no games', () => {
		const f = feed();
		f.games = {
			days: [],
			counts: { all: 0, group: 0, quarterfinals: 0, semifinals: 0, championship: 0 }
		};
		expect(view(f).filters.every((x) => x.days.length === 0 && x.count === '0')).toBe(true);
	});
});

describe('toCupView in Spanish', () => {
	it('writes the state line, a group title and a stage label in Spanish', () => {
		preferLanguages(['es']);
		const v = view();
		expect(v.header.stateLine).toBe('Fase de grupos · 16 de 60 partidos jugados');
		expect(v.groups[0]?.title).toBe('Grupo A del Este');
		expect(v.groups[0]?.meta).toBe('6 de 10 partidos');
		expect(v.header.stages[2]?.dates).toBe('Por definir');
		expect(v.legend[0]?.label).toBe('Ganó el grupo');
	});
});
