// web/tests/lib/feed/cup-matchup-props.test.ts
//
// Tests for the props layer that turns the Cup matchup feed into the matchup panel props.
//
// Tested:
// - The header: round with its conference, date, venue, broadcast, the neutral flag and the game link
// - The status: Final, Final/OT, vs for a scheduled game or none, and a live or postponed game
// - Scores on the right side when the top team is the home team
// - A slot with no game: the round alone for the final, vs, no link, no scores
// - The path rows: W/L, opponent, score, links only where the game page exists
// - The injuries and none; the roster order, starters, leaders, a — for null averages, the injury in place of the position
// - The player card fields: photo kept null, rookie, weight in pounds, hometown
// - The note only for the championship; a side with no team has empty blocks
// - Spanish copy
//
// What is covered:
// - Pure logic on an invented feed (tests/lib/feed/fixtures/cup-matchup.json); no clock, no network
//
// Run with: cd web && pnpm exec vitest run tests/lib/feed/cup-matchup-props.test.ts
//
// SEE: web/src/lib/feed/cup-matchup-props.ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { CupMatchupFeed } from '../../../src/lib/contract/cup-matchup';
import type { MatchupView } from '../../../src/lib/cup/types';
import { toMatchupView } from '../../../src/lib/feed/cup-matchup-props';
import { preferLanguages } from '../../prefer-languages';

const feed = (): CupMatchupFeed =>
	JSON.parse(
		readFileSync(join(__dirname, 'fixtures', 'cup-matchup.json'), 'utf8')
	) as CupMatchupFeed;

const view = (source: CupMatchupFeed = feed()): MatchupView => toMatchupView(source);

const withGame = (change: (game: NonNullable<CupMatchupFeed['game']>) => void): MatchupView => {
	const f = feed();
	if (!f.game) throw new Error('fixture');
	change(f.game);
	return view(f);
};

afterEach(() => {
	vi.restoreAllMocks();
});

describe('toMatchupView header and status', () => {
	it('writes the round alone for the final, with the game facts and its link', () => {
		const { header } = view();
		expect(header.round).toBe('Championship');
		expect(header.date).toBe('Dec 16');
		expect(header.venue).toBe('Harbor Arena');
		expect(header.broadcast).toBe('Courtside TV');
		expect(header.neutral).toBe(true);
		expect(header.gameLink).toEqual({ gameId: '9100004', linked: true });
	});

	it('writes the conference before the round of a conference slot', () => {
		const f = feed();
		f.round = 'semifinals';
		f.conference = 'west';
		expect(view(f).header.round).toBe('West · Semifinals');
	});

	it('says Final/OT from the fifth period and Final before it', () => {
		expect(view().status).toEqual({ kind: 'final', text: 'Final/OT' });
		expect(withGame((g) => (g.period = 4)).status).toEqual({ kind: 'final', text: 'Final' });
		expect(withGame((g) => (g.period = null)).status).toEqual({ kind: 'final', text: 'Final' });
	});

	it('says vs for a scheduled game and passes any other status on', () => {
		expect(withGame((g) => (g.status = 'scheduled')).status).toEqual({ kind: 'vs' });
		expect(withGame((g) => (g.status = 'live')).status).toEqual({ kind: 'status', status: 'live' });
		expect(withGame((g) => (g.status = 'postponed')).status).toEqual({
			kind: 'status',
			status: 'postponed'
		});
	});

	it('puts the scores on the sides by team, the home team being the top one here', () => {
		const { sides } = view();
		expect(sides[0].score).toBe('124');
		expect(sides[1].score).toBe('120');
		expect(withGame((g) => (g.score = null)).sides.map((s) => s.score)).toEqual([null, null]);
	});

	it('has no date, link or scores without a game, and says vs', () => {
		const f = feed();
		f.game = null;
		const v = view(f);
		expect(v.header).toMatchObject({
			date: null,
			venue: null,
			broadcast: null,
			neutral: false,
			gameLink: null
		});
		expect(v.status).toEqual({ kind: 'vs' });
		expect(v.sides.map((s) => s.score)).toEqual([null, null]);
	});

	it('shows the note only for the championship', () => {
		expect(view().note).toBe(true);
		const f = feed();
		f.round = 'semifinals';
		expect(view(f).note).toBe(false);
	});
});

describe('toMatchupView sides', () => {
	it('writes the name and slot label of each side', () => {
		const { sides } = view();
		expect(sides[0].team?.code).toBe('QXA');
		expect(sides[0].name).toBe('Herons');
		expect(sides[0].label).toBe('Winner of East SF');
		expect(sides[1].label).toBe('Winner of West SF');
	});

	it('lists the path with W or L, the opponent, the score and the link only where there is a page', () => {
		const path = view().sides[0].path;
		expect(path.map((p) => p.result)).toEqual(['W', 'L', 'W']);
		expect(path.map((p) => p.score)).toEqual(['110-98', '118-112', '124-120']);
		expect(path.map((p) => p.opponent.code)).toEqual(['UXA', 'RXA', 'UXA']);
		expect(path.map((p) => p.linked)).toEqual([true, false, true]);
		expect(path[0]).toMatchObject({ gameId: '9100001', isHome: true });
	});

	it('leaves the result and score of a game that is not final empty', () => {
		const f = feed();
		const game = f.top.details?.path[2];
		if (!game) throw new Error('fixture');
		Object.assign(game, {
			status: 'scheduled',
			result: null,
			teamScore: null,
			opponentScore: null
		});
		expect(view(f).sides[0].path[2]).toMatchObject({ result: null, score: null });
	});

	it('lists the injuries of a side and none for the other', () => {
		const { sides } = view();
		expect(sides[0].injuries).toEqual([
			{ name: 'Cal Duran', line: '#11 · C', status: 'out', comment: 'Ankle sprain' }
		]);
		expect(sides[1].injuries).toEqual([]);
	});

	it('has empty blocks for a side with no team', () => {
		const f = feed();
		f.bottom.team = null;
		f.bottom.details = null;
		const side = view(f).sides[1];
		expect(side.team).toBeNull();
		expect(side.name).toBe('To be decided');
		expect([side.path, side.injuries, side.roster, side.score]).toEqual([[], [], [], null]);
	});
});

describe('toMatchupView roster', () => {
	it('keeps the roster order and writes the averages with one decimal', () => {
		const roster = view().sides[0].roster;
		expect(roster.map((p) => p.name)).toEqual([
			'Ari Vance',
			'Bo Keller',
			'Cal Duran',
			'Dev Okoro',
			'Eli Ross'
		]);
		expect(roster[0]).toMatchObject({ points: '27.4', rebounds: '5.1', assists: '7.9' });
		expect(roster[4]).toMatchObject({ points: '11.2' });
	});

	it('writes a — for the averages of a player with none', () => {
		const row = view().sides[0].roster[3];
		expect([row.points, row.rebounds, row.assists]).toEqual(['—', '—', '—']);
	});

	it('marks the starters and the leaders of the feed', () => {
		const roster = view().sides[0].roster;
		expect(roster.filter((p) => p.starter).map((p) => p.id)).toEqual(['p101', 'p102']);
		expect(roster[0].leader).toEqual({ points: true, rebounds: false, assists: true });
		expect(roster[1].leader).toEqual({ points: false, rebounds: true, assists: false });
	});

	it('shows the injury status in place of the position for a player who is not active', () => {
		const roster = view().sides[0].roster;
		expect(roster[2]).toMatchObject({ position: 'C', injury: 'out' });
		expect(roster[0].injury).toBeNull();
	});
});

describe('toMatchupView player card', () => {
	it('carries every field of the card', () => {
		const card = view().sides[0].roster[0].card;
		expect(card).toEqual({
			id: 'p101',
			name: 'Ari Vance',
			photo: 'https://example.com/photos/p101.png',
			team: 'Herons',
			number: '#2',
			position: 'G',
			injury: null,
			points: '27.4',
			rebounds: '5.1',
			assists: '7.9',
			height: '6-4',
			weight: '200 lb',
			age: '26',
			hometown: 'Alderton, OH',
			college: 'Northfield',
			experience: '4'
		});
	});

	it('keeps a missing photo null and writes the rookie mark for zero years', () => {
		const roster = view().sides[0].roster;
		expect(roster[2].card.photo).toBeNull();
		expect(roster[1].card.experience).toBe('R');
		expect(roster[1].card.college).toBeNull();
	});

	it('carries the injury status on the card', () => {
		expect(view().sides[0].roster[2].card.injury).toBe('out');
	});
});

describe('toMatchupView in Spanish', () => {
	it('writes the status, the labels and the card in Spanish', () => {
		preferLanguages(['es']);
		const v = view();
		expect(v.status).toEqual({ kind: 'final', text: 'Final/TE' });
		expect(v.sides[0].label).toBe('Ganador de la semifinal del Este');
		expect(v.sides[0].roster[1].card.experience).toBe('N');
		expect(v.header.round).toBe('Final');
	});
});
