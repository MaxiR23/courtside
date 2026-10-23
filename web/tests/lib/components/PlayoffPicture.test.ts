// web/tests/lib/components/PlayoffPicture.test.ts
//
// Tests for the PlayoffPicture component.
//
// Tested:
// - Ten rows in feed order with seed, team, record and GB
// - The Playoffs line after row 6 and the Play-In line after row 10, both solid divider rules, with their captions
// - Clinch tags and the team strip; — cells in the preseason; team links
// - The team logos: the feed logo of a row in its tile, the code for a null logo
//
// What is covered:
// - Each state a table can show, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PlayoffPicture.test.ts
//
// SEE: web/src/lib/components/PlayoffPicture.svelte
import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { PlayoffsFeed } from '../../../src/lib/contract/playoffs';
import { toPlayoffsView } from '../../../src/lib/feed/playoffs-props';
import PlayoffPicture from '../../../src/lib/components/PlayoffPicture.svelte';

const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;
const feed = () =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'playoffs-picture.json'), 'utf8')
	) as PlayoffsFeed;
const show = (source: PlayoffsFeed = feed()) =>
	render(PlayoffPicture, {
		props: {
			table: toPlayoffsView(source, null).picture[0]!,
			layout: 'desktop' as const,
			teamHref
		}
	});

afterEach(() => {
	vi.restoreAllMocks();
});

describe('PlayoffPicture', () => {
	it('draws ten rows in order with seed, record and games behind', () => {
		const { container } = show();
		const rows = [...container.querySelectorAll('.row.body')];
		expect(rows).toHaveLength(10);
		const cells = rows.map((row) =>
			[...row.querySelectorAll('.cell')].map((c) => c.textContent?.trim())
		);
		expect(cells[0]?.[0]).toContain('1');
		expect(cells[0]?.slice(1)).toEqual(['56-26', '—']);
		expect(cells[1]?.slice(1)).toEqual(['52-30', '2.0']);
		expect(
			screen.getAllByRole('columnheader').map((h) => h.textContent?.replace(/\s+/g, ' ').trim())
		).toEqual(['Seed Team', 'Record', 'GB']);
	});

	it('draws the Playoffs line after row 6 and the Play-In line after row 10', () => {
		const { container } = show();
		const lines = [...container.querySelectorAll('.line')];
		expect(
			lines.map((l) => [l.classList.contains('playoffs'), l.classList.contains('playin')])
		).toEqual([
			[true, false],
			[false, true]
		]);
		expect(lines.map((l) => l.textContent?.trim())).toEqual(['Playoffs', 'Play-In']);
		const children = [...(container.querySelector('.table')?.children ?? [])];
		expect(children.indexOf(lines[0]!)).toBe(1 + 6);
		expect(children.indexOf(lines[1]!)).toBe(1 + 10 + 1);
	});

	it('draws clinch tags where the feed sends them and the team strip', () => {
		const { container } = show();
		expect([...container.querySelectorAll('.clinch-tag')].map((t) => t.textContent)).toEqual([
			'z',
			'y',
			'x',
			'pb',
			'e'
		]);
		expect(container.querySelectorAll('.strip')).toHaveLength(10);
	});

	it('writes — in every value and draws no clinch tag in the preseason', () => {
		const source = feed();
		for (const row of source.picture[0].rows) {
			row.seed = null;
			row.wins = null;
			row.losses = null;
			row.gamesBehind = null;
			row.clinch = null;
		}
		const { container } = show(source);
		expect(container.querySelectorAll('.clinch-tag')).toHaveLength(0);
		const first = [...container.querySelectorAll('.row.body')[0]!.querySelectorAll('.cell')].map(
			(c) => c.textContent?.trim()
		);
		expect(first.slice(1)).toEqual(['—', '—']);
		expect(container.querySelectorAll('.line')).toHaveLength(2);
	});

	it('links each team name to its team page', () => {
		show();
		expect(screen.getByRole('link', { name: 'Owls' }).getAttribute('href')).toBe('/team/qxa');
	});
});

describe('PlayoffPicture logos', () => {
	it('draws the logo of a row in its tile and the code for a null logo', () => {
		const source = feed();
		source.picture[0]!.rows[0]!.team.logo = {
			light: 'https://example.com/a-light.svg',
			dark: 'https://example.com/a-dark.svg'
		};
		const { container } = show(source);
		const boxes = [...container.querySelectorAll('.row.body .team-monogram')];
		expect(boxes[0]!.querySelector('img')?.getAttribute('src')).toBe(
			'https://example.com/a-dark.svg'
		);
		expect(boxes[1]!.querySelector('img')).toBeNull();
	});

	it('draws both lines as solid divider rules', () => {
		const source = readFileSync(
			join(__dirname, '..', '..', '..', 'src', 'lib', 'components', 'PlayoffPicture.svelte'),
			'utf8'
		);
		expect(source).toContain('border-top: var(--hairline) solid var(--color-divider)');
		expect(source).not.toMatch(/stroke-dasharray|dashed|dotted|--standings-line-dash|<line\b/);
		const { container } = show();
		const lines = [...container.querySelectorAll('.line')];
		expect(lines).toHaveLength(2);
		for (const line of lines) {
			expect(line.querySelector('.rule')?.getAttribute('aria-hidden')).toBe('true');
		}
	});
});
