// web/tests/lib/feed/cup-props.test.ts
//
// Tests for the props layer that turns the Cup feed into the Cup page props.
//
// Tested:
// - The state line for each of the six stages, not drawn and a null first game date
// - The header team: the champion when complete, else the defending champion; label, accent, bar and outline; null without a team
// - The stage notes: group and quarterfinal texts, the semifinal and championship city
// - The four stages: a single date, a range, "TBD", and their status labels
// - The section order per stage (groups first in draw and group play, the bracket first after)
// - Group rows are drawn by position whatever the feed order; a null position goes after the numbered rows in feed order
// - Group titles and the three metas; rows in feed order with every column, a — for each null
// - The streak and the accents; tags y, x, e, the eliminated row and no tag for null; the legend
// - The wild card tables: titles, the line only after rank 1, a — for a missing group
// - The games filters in order with the feed's counts, a round filter that drops empty days
// - Loser sides, scores only when set, the four status kinds, linked, not counted
// - The bracket: 7 nodes in feed order, West mirrored, only the final marked final
// - Undecided sides: To be decided, label, rule and the Currently line only with a projection
// - slotLabel: the seed and wild card labels, and null for a seed label with no seed (ADR 0054)
// - Known sides: name, meta of seed, group and record, scores and winner on the right side, a missing standing leaves meta null
// - The known map mirrors the feed; the champion's name only when complete
// - The season tag: null on the current season, "Season 2026-27" on a past one, in both languages
// - Spanish copy of the state line, a group title, a stage label, the notes and the defending champion label
// - The header team carries the feed's logo; a null logo leaves the key out
// - The mobile tree: the kicker year from the season, the row labels with the first city, the node gameLink and the winner's rule accent
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

import type { CupFeed, CupGame, CupStage, Opponent } from '../../../src/lib/contract/cup';
import type { CupView } from '../../../src/lib/cup/types';
import { slotLabel, toCupView } from '../../../src/lib/feed/cup-props';
import { preferLanguages } from '../../prefer-languages';

const feed = (): CupFeed =>
	JSON.parse(readFileSync(join(__dirname, 'fixtures', 'cup.json'), 'utf8')) as CupFeed;

const complete = (): CupFeed =>
	JSON.parse(readFileSync(join(__dirname, 'fixtures', 'cup-complete.json'), 'utf8')) as CupFeed;

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

	it('has no header team without a defending champion before the Cup is complete', () => {
		expect(view().header.team).toBeNull();
		expect(atStage('complete').header.team).toBeNull();
	});

	it('uses the defending champion at each stage before complete', () => {
		for (const stage of ['draw', 'group', 'quarterfinals', 'semifinals', 'championship'] as const) {
			const v = atStage(stage, (f) => {
				f.defendingChampion = club();
				f.defendingChampionAccent = '#123456';
			});
			expect(v.header.team?.label).toBe('Defending champion');
			expect(v.header.team?.accent).toBe('#123456');
			expect(v.header.team?.outline).toBe('QXA');
		}
	});

	it('draws the defending champion, not the champion, before complete', () => {
		const v = atStage('championship', (f) => {
			f.champion = club({ code: 'ZZZ', name: 'Other' });
			f.defendingChampion = club();
		});
		expect(v.header.team?.team.code).toBe('QXA');
		expect(v.header.team?.label).toBe('Defending champion');
	});

	it('uses the champion with its accent when the Cup is complete', () => {
		const v = atStage('complete', (f) => {
			f.champion = club({ code: 'ZZZ', name: 'Other' });
			f.championAccent = '#abcdef';
			f.defendingChampion = club();
			f.defendingChampionAccent = '#123456';
		});
		expect(v.header.team?.team.code).toBe('ZZZ');
		expect(v.header.team?.label).toBe('Champion');
		expect(v.header.team?.accent).toBe('#abcdef');
	});

	it('does not fall back to the defending champion when complete with no champion', () => {
		expect(atStage('complete', (f) => (f.defendingChampion = club())).header.team).toBeNull();
	});

	it('keeps a null accent null', () => {
		expect(atStage('group', (f) => (f.defendingChampion = club())).header.team?.accent).toBeNull();
	});

	it('gives the bar only with both colors and a current team', () => {
		const strip = (change: Partial<Opponent>) =>
			atStage('group', (f) => (f.defendingChampion = club(change))).header.team?.strip;
		const colors = { primary: '#111111', secondary: '#222222' } as Opponent['colors'];
		expect(strip({ colors })).toEqual({ primary: '#111111', secondary: '#222222' });
		expect(strip({ colors: null })).toBeNull();
		expect(
			strip({ colors: { primary: '#111111', secondary: null } as Opponent['colors'] })
		).toBeNull();
		expect(strip({ colors, historical: true })).toBeNull();
	});

	it('keeps a guest champion marked as a guest, with the initials as the outline', () => {
		const v = atStage('complete', (f) => {
			f.champion = club({ code: null, name: 'Visitors', city: 'Faraway', guest: true });
		});
		expect(v.header.team?.team).toEqual({
			code: null,
			name: 'Visitors',
			city: 'Faraway',
			guest: true
		});
		expect(v.header.team?.outline).toBe('FV');
	});

	it('carries the feed logo into the team, and no key for a null logo', () => {
		const logo = { light: 'https://example.com/a-light.svg', dark: null };
		const withLogo = atStage('group', (f) => (f.defendingChampion = club({ logo })));
		expect(withLogo.header.team?.team.logo).toEqual(logo);
		const without = atStage('group', (f) => (f.defendingChampion = club()));
		expect('logo' in without.header.team!.team).toBe(false);
	});
});

const club = (change: Partial<Opponent> = {}): Opponent => ({
	code: 'QXA',
	name: 'Herons',
	city: 'Alderton',
	guest: false,
	seasonCode: null,
	historical: false,
	logo: null,
	colors: null,
	...change
});

const gameIn = (city: string | null): CupGame => ({ ...complete().games.days[0]!.games[0]!, city });

describe('toCupView stage notes', () => {
	const notes = (change: (f: CupFeed) => void = () => {}) =>
		atStage('group', change).header.stages.map((stage) => stage.note);

	it('writes the group and quarterfinal notes and leaves the others empty', () => {
		expect(notes()).toEqual(['4 games per team', 'Higher seed hosts', null, null]);
	});

	it('uses the semifinal city, the East one first', () => {
		expect(notes((f) => (f.bracket[2].game = gameIn('Example City')))[2]).toBe('Example City');
		expect(
			notes((f) => {
				f.bracket[2].game = gameIn('East City');
				f.bracket[4].game = gameIn('West City');
			})[2]
		).toBe('East City');
	});

	it('uses the West semifinal city when only it has one', () => {
		expect(notes((f) => (f.bracket[4].game = gameIn('West City')))[2]).toBe('West City');
	});

	it('leaves the note empty for a game with no city', () => {
		expect(notes((f) => (f.bracket[2].game = gameIn(null)))[2]).toBeNull();
	});

	it('uses the final city for the championship', () => {
		expect(notes((f) => (f.bracket[3].game = gameIn('Final City')))[3]).toBe('Final City');
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

	it('draws the group rows by position whatever the feed order, null positions last in feed order', () => {
		const source = feed();
		const rows = source.groups[0]!.rows;
		const shuffled = [rows[2]!, rows[0]!, rows[4]!, rows[1]!, rows[3]!];
		shuffled[0] = { ...shuffled[0]!, position: 3 };
		shuffled[1] = { ...shuffled[1]!, position: 1 };
		shuffled[2] = { ...shuffled[2]!, position: null };
		shuffled[3] = { ...shuffled[3]!, position: 2 };
		shuffled[4] = { ...shuffled[4]!, position: null };
		source.groups[0]!.rows = shuffled as typeof rows;
		const drawn = view(source).groups[0]!.rows;
		expect(drawn.map((r) => r.position)).toEqual(['1', '2', '3', '—', '—']);
		expect(drawn.slice(3).map((r) => r.team.code)).toEqual([
			shuffled[2]!.team.code,
			shuffled[4]!.team.code
		]);
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

	it('maps a scheduled game to its tip time in the viewer zone, with and without broadcast', () => {
		const games = view().filters[0]!.days[1]!.games;
		expect(games[0]?.status).toEqual({ kind: 'time', text: '7:00 PM' });
		expect(games[0]?.broadcast).toBe('Courtside TV');
		expect(games[0]?.linked).toBe(false);
		expect(games[1]?.status).toEqual({ kind: 'time', text: '9:30 PM' });
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

describe('toCupView bracket', () => {
	const node = (v: CupView, id: string) => {
		const found = v.bracket.nodes.find((n) => n.id === id);
		if (!found) throw new Error(`no node ${id}`);
		return found;
	};

	it('has the 7 nodes in the feed order, the West mirrored and only the final marked final', () => {
		const v = view();
		expect(v.bracket.nodes.map((n) => n.id)).toEqual([
			'east-qf-1',
			'east-qf-2',
			'east-sf',
			'final',
			'west-sf',
			'west-qf-1',
			'west-qf-2'
		]);
		expect(v.bracket.nodes.filter((n) => n.mirrored).map((n) => n.id)).toEqual([
			'west-sf',
			'west-qf-1',
			'west-qf-2'
		]);
		expect(v.bracket.nodes.filter((n) => n.final).map((n) => n.id)).toEqual(['final']);
		expect(node(v, 'east-sf').roundLabel).toBe('Semifinals');
		expect(node(v, 'final').roundLabel).toBe('Championship');
	});

	it('writes To be decided, the label and the rule for an undecided side', () => {
		const side = node(view(), 'west-qf-1').top;
		expect(side.team).toBeNull();
		expect(side.name).toBe('To be decided');
		expect(side.label).toBe('West #1 seed');
		expect(side.rule).toBe('Best group winner');
		expect([side.meta, side.score, side.winner]).toEqual([null, null, false]);
		const n = node(view(), 'west-qf-1');
		expect([n.date, n.venue, n.broadcast, n.neutral]).toEqual([null, null, null, false]);
	});

	it('writes every label and rule text', () => {
		const v = view();
		expect(node(v, 'east-qf-1').bottom.label).toBe('East wild card');
		expect(node(v, 'east-qf-1').bottom.rule).toBe('Best team that did not win its group');
		expect(node(v, 'east-qf-2').bottom.rule).toBe('Third-best group winner');
		expect(node(v, 'east-qf-2').top.rule).toBe('Second-best group winner');
		expect(node(v, 'east-sf').bottom.label).toBe('Winner of East QF 2');
		expect(node(v, 'east-sf').top.rule).toBe('Advances from the quarterfinal');
		expect(node(v, 'final').bottom.label).toBe('Winner of West SF');
		expect(node(v, 'final').bottom.rule).toBe('Advances from the semifinal');
	});

	it('writes the Currently line only from a projection', () => {
		const v = view();
		expect(node(v, 'east-qf-1').top.currently).toBe('Currently QXA (4-0)');
		expect(node(v, 'east-qf-1').bottom.currently).toBe('Currently QXB (3-1)');
		expect(node(v, 'west-qf-1').top.currently).toBeNull();
		expect(node(v, 'final').top.currently).toBeNull();
	});

	it('writes the name, meta, scores and winner of a decided node', () => {
		const final = node(view(complete()), 'final');
		expect(final.top.team?.code).toBe('QXA');
		expect(final.top.name).toBe('Herons');
		expect(final.top.meta).toBe('#1 seed · East Group A · 4-0');
		// The top team is the home team: the score is the feed's home score.
		expect([final.top.score, final.top.winner]).toEqual(['124', true]);
		expect([final.bottom.score, final.bottom.winner]).toEqual(['120', false]);
		expect(final.date).toBe('Dec 16');
		expect([final.venue, final.broadcast, final.neutral]).toEqual([
			'Harbor Arena',
			'Courtside TV',
			true
		]);
		expect(final.bottom.meta).toBe('#1 seed · West Group B · 4-0');
	});

	it('takes the away score for a side that is the away team', () => {
		const qf = node(view(complete()), 'east-qf-1');
		expect([qf.top.score, qf.top.winner]).toEqual(['110', true]);
		expect([qf.bottom.score, qf.bottom.winner]).toEqual(['98', false]);
		const f = complete();
		const slot = f.bracket[0];
		if (!slot?.game) throw new Error('fixture');
		[slot.top, slot.bottom] = [slot.bottom, slot.top];
		const swapped = node(view(f), 'east-qf-1');
		expect([swapped.top.score, swapped.top.winner]).toEqual(['98', false]);
		expect([swapped.bottom.score, swapped.bottom.winner]).toEqual(['110', true]);
	});

	it('leaves out the parts of the meta with no value and the meta itself with no standing', () => {
		const f = complete();
		const slot = f.bracket[0];
		if (!slot?.top.standing) throw new Error('fixture');
		slot.top.standing.seed = null;
		slot.top.standing.group = null;
		expect(node(view(f), 'east-qf-1').top.meta).toBe('4-0');
		slot.top.standing = null;
		expect(node(view(f), 'east-qf-1').top.meta).toBeNull();
	});

	it('writes the round labels of the columns', () => {
		expect(view().bracket.rounds).toEqual({
			quarterfinals: 'Quarterfinals',
			semifinals: 'Semifinals',
			championship: 'Championship'
		});
	});

	it('writes the kicker from the first year of the season', () => {
		expect(view().bracket.kicker).toBe('2026 NBA Cup');
		preferLanguages(['es']);
		expect(view().bracket.kicker).toBe('Copa NBA 2026');
	});

	it('writes the tree labels without a city when no game has one', () => {
		expect(view().bracket.treeLabels).toEqual({
			quarterfinals: 'Quarterfinals',
			semifinals: 'Semifinals',
			championship: 'Championship'
		});
	});

	it('writes the tree labels with the city of the round', () => {
		expect(view(complete()).bracket.treeLabels).toEqual({
			quarterfinals: 'Quarterfinals',
			semifinals: 'Semifinals · Alderton',
			championship: 'Championship · Alderton'
		});
	});

	it('takes the city of the first semifinal that has one, in feed order', () => {
		const f = complete();
		f.bracket[2]!.game!.city = null;
		f.bracket[4]!.game!.city = 'Example Bay';
		expect(view(f).bracket.treeLabels.semifinals).toBe('Semifinals · Example Bay');
		f.bracket[4]!.game!.city = null;
		expect(view(f).bracket.treeLabels.semifinals).toBe('Semifinals');
	});

	it('writes the tree labels in Spanish', () => {
		preferLanguages(['es']);
		const labels = view(complete()).bracket.treeLabels;
		expect(labels.championship).toBe('Final · Alderton');
		expect(labels.semifinals).toBe('Semifinales · Alderton');
	});

	it('gives the node a game link only when it has a game', () => {
		expect(view().bracket.nodes.every((n) => n.gameLink === null)).toBe(true);
		const f = complete();
		expect(node(view(f), 'final').gameLink).toEqual({ gameId: '9100004', linked: true });
		f.bracket[3]!.game!.detailAvailable = false;
		expect(node(view(f), 'final').gameLink).toEqual({ gameId: '9100004', linked: false });
	});

	it('gives the winner line the accent of the side that won', () => {
		expect(view().bracket.nodes.every((n) => n.rule === null)).toBe(true);
		const f = complete();
		for (const slot of f.bracket) slot.accent = { top: '#123456', bottom: '#654321' };
		const v = view(f);
		// The top side won the final; the bottom side (away) won the West semifinal.
		expect(node(v, 'final').rule).toEqual({ accent: '#123456' });
		expect(node(v, 'west-sf').rule).toEqual({ accent: '#654321' });
	});

	it('gives the winner line a null accent without a resolved color', () => {
		expect(node(view(complete()), 'final').rule).toEqual({ accent: null });
		const f = complete();
		f.bracket[3]!.accent = { top: null, bottom: '#654321' };
		expect(node(view(f), 'final').rule).toEqual({ accent: null });
	});

	it('gives no winner line to a game with no winner', () => {
		const f = complete();
		f.bracket[3]!.game!.winner = null;
		expect(node(view(f), 'final').rule).toBeNull();
	});

	it('mirrors the known flags of the feed', () => {
		const none = view().bracket.known;
		expect(Object.keys(none)).toHaveLength(14);
		expect(Object.values(none).some(Boolean)).toBe(false);
		const all = view(complete()).bracket.known;
		expect(Object.values(all).every(Boolean)).toBe(true);
		expect(all['east-sf:top']).toBe(true);
	});

	it('names the champion only when the Cup is complete', () => {
		expect(view().bracket.champion).toBeNull();
		expect(view(complete()).bracket.champion).toBe('Herons');
		const f = complete();
		f.champion = null;
		expect(view(f).bracket.champion).toBeNull();
	});

	it('writes the bracket in Spanish', () => {
		preferLanguages(['es']);
		const v = view(complete());
		expect(node(v, 'east-qf-1').roundLabel).toBe('Cuartos de final');
		expect(node(v, 'east-qf-1').top.meta).toBe('Preclasificado 1 · Grupo A del Este · 4-0');
		const open = view();
		expect(node(open, 'east-qf-1').top.name).toBe('Por decidir');
		expect(node(open, 'east-qf-1').top.currently).toBe('Actualmente QXA (4-0)');
		expect(node(open, 'east-sf').top.label).toBe('Ganador de cuartos 1 del Este');
		expect(node(open, 'east-qf-1').top.rule).toBe('Mejor ganador de grupo');
	});
});

describe('slotLabel', () => {
	it('writes a seed label and the other slot labels', () => {
		expect(slotLabel({ key: 'seed', conference: 'east', seed: 1, quarterfinal: null })).toBe(
			'East #1 seed'
		);
		expect(
			slotLabel({ key: 'wild_card', conference: 'west', seed: null, quarterfinal: null })
		).toBe('West wild card');
	});

	it('gives null for a seed label with no seed, never a seed 0', () => {
		expect(
			slotLabel({ key: 'seed', conference: 'east', seed: null, quarterfinal: null })
		).toBeNull();
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
		expect(v.header.stages[0]?.note).toBe('4 partidos por equipo');
		expect(v.header.stages[1]?.note).toBe('Local el mejor sembrado');
		const team = atStage('group', (f) => (f.defendingChampion = club())).header.team;
		expect(team?.label).toBe('Campeón vigente');
	});
});

describe('toCupView season tag', () => {
	it('has no tag on the current season', () => {
		expect(view().header.tag).toBeNull();
	});

	it('writes the season tag on a past season', () => {
		expect(toCupView(feed(), { past: true }).header.tag).toBe('Season 2026-27');
	});

	it('writes the season tag in Spanish', () => {
		preferLanguages(['es']);
		expect(toCupView(feed(), { past: true }).header.tag).toBe('Temporada 2026-27');
	});
});
