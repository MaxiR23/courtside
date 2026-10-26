// web/tests/lib/feed/power-ranking-props.test.ts
//
// Tests for the props layer that turns the power ranking feed into the section's view.
//
// Tested:
// - An available feed gives 30 rows in the feed's order, every text as sent
// - A tied rank reads T3 on both tied teams; an untied rank is its number
// - ratingNegative and playoffsLow drive the muted flags, never the text
// - titleShare is carried unchanged
// - A team with a null name, city and logo keeps null name and city and no logo key
// - The toggle labels read "Show all 30 teams" and "Show top 10"
// - An unavailable feed and an available feed with no teams give null
// - Spanish copy
//
// What is covered:
// - Pure logic on a recorded feed (tests/lib/feed/fixtures/power-ranking.json); no clock, no network
//
// Run with: cd web && pnpm exec vitest run tests/lib/feed/power-ranking-props.test.ts
//
// SEE: web/src/lib/feed/power-ranking-props.ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { PowerRankingFeed } from '../../../src/lib/contract/power-ranking';
import { toPowerRankingView } from '../../../src/lib/feed/power-ranking-props';
import type { PowerRankingView } from '../../../src/lib/standings/types';
import { preferLanguages } from '../../prefer-languages';

const feed = (): PowerRankingFeed =>
	JSON.parse(
		readFileSync(join(__dirname, 'fixtures', 'power-ranking.json'), 'utf8')
	) as PowerRankingFeed;

const view = (source: PowerRankingFeed = feed()): PowerRankingView =>
	toPowerRankingView(source) as PowerRankingView;

afterEach(() => {
	vi.restoreAllMocks();
});

describe('toPowerRankingView', () => {
	it('maps an available feed to 30 rows in the feed order, every text as sent', () => {
		const source = feed();
		const v = view(source);
		expect(v.teams).toHaveLength(30);
		expect(v.teams.map((t) => t.code)).toEqual(source.teams.map((t) => t.team.code));
		const first = v.teams[0];
		const sent = source.teams[0];
		expect(first.rank).toBe('1');
		expect(first.record).toBe(sent.record);
		expect(first.rating).toBe('+11.2');
		expect(first.offense).toBe('+8.0');
		expect(sent.offense).toBe('+8.0');
		expect(first.defense).toBe('−7.0');
		expect(sent.defense).toBe('−7.0');
		expect(first.projected).toBe(sent.projected);
		expect(first.playoffs).toBe('>99.9%');
		expect(first.title).toBe('31.0%');
		expect(first.team.logo).toEqual(sent.team.logo);
		expect(v.teams[27].rating).toBe('−2.1');
	});

	it('shows a tied rank as T3 on both tied teams and an untied rank as its number', () => {
		const v = view();
		expect(v.teams.map((t) => t.rank).slice(0, 5)).toEqual(['1', '2', 'T3', 'T3', '5']);
		expect(v.teams.map((t) => t.tied).slice(0, 5)).toEqual([false, false, true, true, false]);
	});

	it('carries the flags to the muted fields and never derives them from the text', () => {
		const v = view();
		expect(v.teams[27].ratingMuted).toBe(true);
		expect(v.teams[0].ratingMuted).toBe(false);
		expect(v.teams[28].playoffsMuted).toBe(true);
		expect(v.teams[0].playoffsMuted).toBe(false);
		const source = feed();
		source.teams[27].ratingNegative = false;
		source.teams[28].playoffsLow = false;
		const copy = view(source);
		expect(copy.teams[27].rating).toBe('−2.1');
		expect(copy.teams[27].ratingMuted).toBe(false);
		expect(copy.teams[28].playoffs).toBe('<0.1%');
		expect(copy.teams[28].playoffsMuted).toBe(false);
	});

	it('carries titleShare unchanged', () => {
		const v = view();
		expect(v.teams[0].titleShare).toBe(1);
		expect(v.teams[3].titleShare).toBe(0.42);
		expect(v.teams[28].titleShare).toBe(0);
	});

	it('keeps a null name and city and leaves the logo key out for a null logo', () => {
		const last = view().teams[29];
		expect(last.team.name).toBeNull();
		expect(last.team.city).toBeNull();
		expect('logo' in last.team).toBe(false);
	});

	it('labels the toggle with the team count and the top 10', () => {
		const v = view();
		expect(v.showAllLabel).toBe('Show all 30 teams');
		expect(v.showTopLabel).toBe('Show top 10');
	});

	it('returns null for an unavailable feed and for an available feed with no teams', () => {
		expect(toPowerRankingView({ season: '2026-27', state: 'unavailable', teams: [] })).toBeNull();
		expect(toPowerRankingView({ ...feed(), teams: [] })).toBeNull();
	});

	it('speaks Spanish', () => {
		preferLanguages(['es']);
		const v = view();
		expect(v.teams[2].rank).toBe('E3');
		expect(v.showAllLabel).toBe('Ver los 30 equipos');
		expect(v.showTopLabel).toBe('Ver los 10 primeros');
	});
});
