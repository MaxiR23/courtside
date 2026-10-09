// web/tests/lib/feed/standings-props.test.ts
//
// Tests for the props layer that turns the standings feed into the standings page props.
//
// Tested:
// - Conference groups and rows in the feed's order, with translated names and the team count meta
// - Division groups in the feed's order, with the conference in the meta; conference seed on rows
// - Every column's value as the feed sends it; a — for each null; the streak per language
// - Clinch tones, the eliminated row, the accents and the plain tile for null colors
// - The playoff and play-in lines (lineAfter): repeated seeds, missing seeds, null seeds, feed order
// - The key's seven codes with their labels; the state line, final and regular, singular and plural
//
// What is covered:
// - Pure logic on a recorded feed (tests/lib/feed/fixtures/standings.json); no clock, no network
//
// Run with: cd web && pnpm exec vitest run tests/lib/feed/standings-props.test.ts
//
// SEE: web/src/lib/feed/standings-props.ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { StandingsFeed } from '../../../src/lib/contract/standings';
import { lineAfter, toStandingsView } from '../../../src/lib/feed/standings-props';
import type { StandingsView } from '../../../src/lib/standings/types';
import { preferLanguages } from '../../prefer-languages';

const feed = (): StandingsFeed =>
	JSON.parse(readFileSync(join(__dirname, 'fixtures', 'standings.json'), 'utf8')) as StandingsFeed;

const view = (source: StandingsFeed = feed()): StandingsView => toStandingsView(source);

afterEach(() => {
	vi.restoreAllMocks();
});

describe('toStandingsView groups', () => {
	it('keeps the conference groups and their rows in the feed order, with names and team count', () => {
		const v = view();
		expect(v.conference.map((g) => g.key)).toEqual(['east', 'west']);
		expect(v.conference.map((g) => g.title)).toEqual(['Eastern Conference', 'Western Conference']);
		expect(v.conference.map((g) => g.meta)).toEqual([
			'11 teams · GB vs conference leader',
			'2 teams · GB vs conference leader'
		]);
		expect(v.conference[0]?.rows.map((r) => r.code)).toEqual(
			feed().conferences[0]?.teams.map((t) => t.code)
		);
	});

	it("keeps the division groups in the feed's order, with the conference in the meta", () => {
		const v = view();
		expect(v.division.map((g) => g.title)).toEqual([
			'Atlantic',
			'Southeast',
			'Central',
			'Pacific',
			'Northwest'
		]);
		expect(v.division[0]?.meta).toBe('Eastern Conference · GB vs division leader');
		expect(v.division[3]?.meta).toBe('Western Conference · GB vs division leader');
	});

	it('carries the conference seed on division rows and draws no lines there', () => {
		const rows = view().division[0]?.rows ?? [];
		expect(rows.map((r) => r.seed)).toEqual(['1', '2', '8', '11', '12']);
		expect(rows.every((r) => r.lineAfter === null)).toBe(true);
	});
});

describe('toStandingsView rows', () => {
	it("draws every column's value as the feed sends it", () => {
		expect(view().conference[0]?.rows[0]).toEqual({
			code: 'BOS',
			seed: '1',
			city: 'Boston',
			name: 'Celtics',
			strip: { primary: '#0064c8', secondary: '#ffffff' },
			clinch: { code: '*', tone: 'accent' },
			eliminated: false,
			wins: '60',
			losses: '22',
			pct: '.731',
			gamesBehind: '—',
			streak: { text: 'W3', win: true },
			home: '31-11',
			away: '29-12',
			lastTen: '7-3',
			division: '15-5',
			conference: '40-14',
			pointsFor: '118.0',
			pointsAgainst: '112.0',
			differential: { value: '+5.5', accent: true },
			total: { value: '+451', accent: true },
			lineAfter: null
		});
	});

	it('formats a win streak as W3 and a loss streak as L2, and as G3 / P2 in Spanish', () => {
		const rows = view().conference[0]?.rows ?? [];
		expect([rows[0]?.streak.text, rows[1]?.streak.text]).toEqual(['W3', 'L2']);
		preferLanguages(['es-ES']);
		const es = view().conference[0]?.rows ?? [];
		expect([es[0]?.streak.text, es[1]?.streak.text]).toEqual(['G3', 'P2']);
	});

	it('draws — for a null seed, streak, games behind and pct', () => {
		const source = feed();
		const row = source.conferences[0]!.teams[2]!;
		Object.assign(row, { seed: null, streak: null, gamesBehind: null, pct: null });
		const out = view(source).conference[0]?.rows[2];
		expect(out?.seed).toBe('—');
		expect(out?.streak).toEqual({ text: '—', win: false });
		expect(out?.gamesBehind).toBe('—');
		expect(out?.pct).toBe('—');
	});

	it('maps each clinch code to its tone and a null clinch to no tag', () => {
		const rows = view().conference[0]?.rows ?? [];
		expect(rows.slice(0, 8).map((r) => r.clinch)).toEqual([
			{ code: '*', tone: 'accent' },
			{ code: 'z', tone: 'accent' },
			{ code: 'y', tone: 'accent' },
			{ code: 'x', tone: 'accent' },
			{ code: 'xp', tone: 'ink' },
			{ code: 'pb', tone: 'ink' },
			{ code: 'e', tone: 'muted' },
			null
		]);
	});

	it('marks an eliminated row', () => {
		const rows = view().conference[0]?.rows ?? [];
		expect(rows.filter((r) => r.eliminated).map((r) => r.clinch?.code)).toEqual(['e']);
	});

	it('accents a win streak and a non-negative differential and total, including zero', () => {
		const rows = view().conference[0]?.rows ?? [];
		expect(rows[0]?.streak.win).toBe(true);
		expect(rows[1]?.streak.win).toBe(false);
		expect(rows[7]?.differential).toEqual({ value: '0.0', accent: true });
		expect(rows[7]?.total).toEqual({ value: '0', accent: true });
		expect(rows[6]?.differential.accent).toBe(false);
		expect(rows[6]?.differential.value.startsWith('−')).toBe(true);
		expect(rows[6]?.total.accent).toBe(false);
	});

	it('gives a plain tile to a team with null colors', () => {
		const rows = view().conference[0]?.rows ?? [];
		expect(rows[8]?.strip).toBeNull();
		expect(rows[0]?.strip).not.toBeNull();
	});

	it('puts the playoff line under seed 6 and the play-in line under seed 10 in conference groups only', () => {
		const v = view();
		const lines = v.conference[0]?.rows.map((r) => r.lineAfter);
		expect(lines).toEqual([
			null,
			null,
			null,
			null,
			null,
			'playoff',
			null,
			null,
			null,
			'play-in',
			null
		]);
		expect(v.conference[1]?.rows.every((r) => r.lineAfter === null)).toBe(true);
		expect(v.division.flatMap((g) => g.rows).every((r) => r.lineAfter === null)).toBe(true);
	});
});

describe('lineAfter', () => {
	it('draws the line under the last of repeated seeds', () => {
		expect(lineAfter([1, 2, 3, 4, 5, 6, 6, 7, 8, 9, 10, 10, 11])).toEqual([
			null,
			null,
			null,
			null,
			null,
			null,
			'playoff',
			null,
			null,
			null,
			null,
			'play-in',
			null
		]);
	});

	it('draws no line when no row has seed 6 or 10', () => {
		expect(lineAfter([1, 2, 3, 4, 5])).toEqual([null, null, null, null, null]);
	});

	it('ignores null seeds', () => {
		expect(lineAfter([null, 6, null, 10, null])).toEqual([null, 'playoff', null, 'play-in', null]);
	});

	it('keeps a seed above a team with more wins where the feed puts it', () => {
		const source = feed();
		const teams = source.conferences[0]!.teams;
		teams[1]!.wins = 99;
		expect(view(source).conference[0]?.rows.map((r) => r.code)).toEqual(teams.map((t) => t.code));
	});
});

describe('toStandingsView key and header', () => {
	it('lists the seven key codes in order with their labels, in English and Spanish', () => {
		expect(view().key.map((k) => k.clinch.code)).toEqual(['*', 'z', 'y', 'x', 'xp', 'pb', 'e']);
		expect(view().key[0]?.label).toBe('Clinched best record in league');
		expect(view().key[6]).toEqual({
			clinch: { code: 'e', tone: 'muted' },
			label: 'Eliminated'
		});
		preferLanguages(['es-ES']);
		expect(view().key[6]?.label).toBe('Eliminado');
	});

	it('states Final · regular season for a final feed and the games played for a regular one', () => {
		expect(view().header).toEqual({
			season: '2025-26',
			stateLine: 'Regular season · 1180 games played'
		});
		expect(view({ ...feed(), gamesPlayed: 1 }).header.stateLine).toBe(
			'Regular season · 1 game played'
		);
		expect(view({ ...feed(), state: 'final' }).header.stateLine).toBe('Final · regular season');
	});
});
