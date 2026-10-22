// web/tests/lib/feed/search-props.test.ts
//
// Tests for the props layer that turns search feed entries into overlay rows.
//
// Tested:
// - Team meta with the ordinal in English and Spanish; a null rank drops the division part
// - The strip is set only with both colors
// - The long position in Spanish (ADR 0054)
// - Player line and short line; a null number, position or abbreviation drops its part
// - The team mark of both rows: the feed's logo, a null logo leaving the key out
// - Injury status, team color and photo pass through
//
// What is covered:
// - Pure logic on the recorded fixture (tests/lib/feed/fixtures/search.json); no clock, no network
//
// Run with: cd web && pnpm exec vitest run tests/lib/feed/search-props.test.ts
//
// SEE: web/src/lib/feed/search-props.ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { SearchFeed, SearchPlayer, SearchTeam } from '../../../src/lib/contract/search';
import { toSearchPlayerRow, toSearchTeamRow } from '../../../src/lib/feed/search-props';
import { preferLanguages } from '../../prefer-languages';

const feed = (): SearchFeed =>
	JSON.parse(readFileSync(join(__dirname, 'fixtures', 'search.json'), 'utf8')) as SearchFeed;

const team = (code: string): SearchTeam => feed().teams.find((t) => t.code === code) as SearchTeam;
const player = (id: string): SearchPlayer =>
	feed().players.find((p) => p.id === id) as SearchPlayer;

afterEach(() => {
	vi.restoreAllMocks();
});

describe('toSearchTeamRow', () => {
	it('builds the row from the team', () => {
		const row = toSearchTeamRow(team('OKC'));
		expect(row).toMatchObject({ code: 'OKC', city: 'Oklahoma City', name: 'Thunder' });
		expect(row.record).toBe(team('OKC').record);
		expect(row.meta).toBe('OKC · 1st in Northwest');
	});

	it('writes the ordinal for ranks 1 to 5', () => {
		const metas = [1, 2, 3, 4, 5].map(
			(divisionRank) => toSearchTeamRow({ ...team('OKC'), divisionRank }).meta
		);
		expect(metas).toEqual([
			'OKC · 1st in Northwest',
			'OKC · 2nd in Northwest',
			'OKC · 3rd in Northwest',
			'OKC · 4th in Northwest',
			'OKC · 5th in Northwest'
		]);
	});

	it('writes the ordinal in Spanish', () => {
		preferLanguages(['es-ES']);
		expect(toSearchTeamRow(team('OKC')).meta).toBe('OKC · 1.º en Northwest');
	});

	it('drops the division part for a null rank', () => {
		expect(toSearchTeamRow(team('SAS')).meta).toBe('SAS');
	});

	it('sets the strip only with both colors', () => {
		expect(toSearchTeamRow(team('OKC')).strip).toEqual({
			primary: team('OKC').colors.primary,
			secondary: team('OKC').colors.secondary
		});
		expect(toSearchTeamRow(team('SAS')).strip).toBeNull();
		const half = { ...team('OKC'), colors: { primary: '#007ac1', secondary: null } };
		expect(toSearchTeamRow(half).strip).toBeNull();
	});
});

describe('toSearchPlayerRow', () => {
	it('builds the long and short lines', () => {
		const row = toSearchPlayerRow(player('1628983'));
		expect(row.line).toBe('#2 · Guard (G)');
		expect(row.lineShort).toBe('#2 · G');
		expect(row.name).toBe('Shai Gilgeous-Alexander');
		expect(row.shortName).toBe('S. Gilgeous-Alexander');
		expect(row.photo).toBe('https://cdn.example.com/players/1628983.png');
	});

	it('drops each null part', () => {
		const base = player('1628983');
		const noNumber = toSearchPlayerRow({ ...base, number: null });
		expect([noNumber.line, noNumber.lineShort]).toEqual(['Guard (G)', 'G']);
		const noPosition = toSearchPlayerRow({ ...base, position: null });
		expect([noPosition.line, noPosition.lineShort]).toEqual(['#2 · G', '#2 · G']);
		const noAbbr = toSearchPlayerRow({ ...base, positionAbbr: null });
		expect([noAbbr.line, noAbbr.lineShort]).toEqual(['#2 · Guard', '#2']);
	});

	it('gives empty lines when number, position and abbreviation are null', () => {
		const row = toSearchPlayerRow(player('1641000'));
		expect(row.line).toBe('');
		expect(row.lineShort).toBe('');
		expect(row.photo).toBeNull();
	});

	it('passes the injury status, or null', () => {
		expect(toSearchPlayerRow(player('1630162')).injury).toBe('out');
		expect(toSearchPlayerRow(player('1628983')).injury).toBeNull();
	});

	it('passes the team color through, including null', () => {
		expect(toSearchPlayerRow(player('1628983'))).toMatchObject({
			teamCode: 'OKC',
			teamColor: '#007ac1'
		});
		expect(toSearchPlayerRow(player('1628368')).teamColor).toBeNull();
	});
});

describe('toSearchPlayerRow position', () => {
	it('writes the long position in Spanish and keeps the abbreviation', () => {
		preferLanguages(['es-ES']);
		const row = toSearchPlayerRow({ ...player('1628983'), position: 'Guard', positionAbbr: 'G' });
		expect(row.line).toContain('Escolta (G)');
		expect(row.lineShort).toContain('G');
	});
});

describe('search team marks', () => {
	it("carries the feed's logo to the team row and the player row", () => {
		const source = feed();
		const logo = { light: 'https://example.com/okc-light.svg', dark: null };
		source.teams[0]!.logo = logo;
		source.players[0]!.team.logo = logo;
		expect(toSearchTeamRow(source.teams[0]!).team.logo).toEqual(logo);
		expect(toSearchPlayerRow(source.players[0]!).team.logo).toEqual(logo);
	});

	it('leaves the key out for a null logo and builds the player mark from the code', () => {
		const source = feed();
		source.teams[0]!.logo = null;
		source.players[0]!.team.logo = null;
		const teamRow = toSearchTeamRow(source.teams[0]!);
		expect('logo' in teamRow.team).toBe(false);
		expect(teamRow.team.code).toBe(source.teams[0]!.code);
		const playerRow = toSearchPlayerRow(source.players[0]!);
		expect('logo' in playerRow.team).toBe(false);
		expect(playerRow.team).toEqual({
			code: source.players[0]!.team.code,
			name: null,
			city: null,
			guest: false
		});
	});
});
