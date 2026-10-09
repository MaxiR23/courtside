// web/tests/lib/components/LineScore.test.ts
//
// Tests for the LineScore component.
//
// Tested:
// - The header and each team's points per quarter and total
// - A dash for quarters not played yet in a live game
// - An OT column for one overtime, and 2OT for a second
// - The code, and on the detail page the team name, link to the team page
// - The header in Spanish with a Spanish browser preference
// - Detail mode: OT1 and OT2 labels, and the team name next to the code
// - A guest team code and name are plain text
//
// What is covered:
// - Regulation, live and overtime games, plus Spanish
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/LineScore.test.ts
//
// SEE: web/src/lib/components/LineScore.svelte
import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { preferLanguages } from '../../prefer-languages';

import LineScore from '../../../src/lib/components/LineScore.svelte';

afterEach(() => {
	vi.restoreAllMocks();
});

const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;

const rows = (container: HTMLElement) =>
	[...container.querySelectorAll('.line')].map((line) =>
		[...line.children].map((cell) => cell.textContent?.trim())
	);

const regulation = {
	away: { code: 'GSW', periods: [28, 26, 24, 34], total: 112 },
	home: { code: 'LAL', periods: [25, 27, 22, 30], total: 104 }
};

describe('LineScore', () => {
	it("shows the header Team 1 2 3 4 T and each team's points per quarter and total", () => {
		const { container } = render(LineScore, { props: { ...regulation, teamHref } });
		expect(rows(container)).toEqual([
			['Team', '1', '2', '3', '4', 'T'],
			['GSW', '28', '26', '24', '34', '112'],
			['LAL', '25', '27', '22', '30', '104']
		]);
	});

	it('shows – for quarters not played yet in a live game', () => {
		const { container } = render(LineScore, {
			props: {
				teamHref,
				away: { code: 'GSW', periods: [28, 26], total: 54 },
				home: { code: 'LAL', periods: [25, 27], total: 52 }
			}
		});
		expect(rows(container)[1]).toEqual(['GSW', '28', '26', '–', '–', '54']);
	});

	it('adds an OT column for one overtime and 2OT for a second', () => {
		const one = render(LineScore, {
			props: {
				teamHref,
				away: { code: 'GSW', periods: [1, 2, 3, 4, 5], total: 15 },
				home: { code: 'LAL', periods: [1, 2, 3, 4, 6], total: 16 }
			}
		});
		expect(rows(one.container)[0]).toEqual(['Team', '1', '2', '3', '4', 'OT', 'T']);
		one.unmount();
		const two = render(LineScore, {
			props: {
				teamHref,
				away: { code: 'GSW', periods: [1, 2, 3, 4, 5, 6], total: 21 },
				home: { code: 'LAL', periods: [1, 2, 3, 4, 6, 7], total: 23 }
			}
		});
		expect(rows(two.container)[0]).toEqual(['Team', '1', '2', '3', '4', 'OT', '2OT', 'T']);
	});

	it('shows the header in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		const { container } = render(LineScore, {
			props: {
				teamHref,
				away: { code: 'GSW', periods: [1, 2, 3, 4, 5], total: 15 },
				home: { code: 'LAL', periods: [1, 2, 3, 4, 6], total: 16 }
			}
		});
		expect(rows(container)[0]).toEqual(['Equipo', '1', '2', '3', '4', 'PR', 'T']);
	});

	it('labels overtime columns OT1 and OT2 on the detail page', () => {
		const { container } = render(LineScore, {
			props: {
				teamHref,
				detail: true,
				away: { code: 'GSW', periods: [1, 2, 3, 4, 5, 6], total: 21 },
				home: { code: 'LAL', periods: [1, 2, 3, 4, 6, 7], total: 23 }
			}
		});
		expect(rows(container)[0]).toEqual(['Team', '1', '2', '3', '4', 'OT1', 'OT2', 'T']);
	});

	it('shows the team name next to the code on the detail page', () => {
		const { container } = render(LineScore, {
			props: {
				teamHref,
				detail: true,
				away: { code: 'GSW', name: 'Warriors', periods: [28], total: 28 },
				home: { code: 'LAL', name: 'Lakers', periods: [25], total: 25 }
			}
		});
		const names = [...container.querySelectorAll('.team-name')].map((e) => e.textContent);
		expect(names).toEqual(['Warriors', 'Lakers']);
		expect(container.querySelector('.line-score')?.classList.contains('detail')).toBe(true);
	});

	it('links the code to the team page, and the name on the detail page', () => {
		render(LineScore, {
			props: {
				detail: true,
				teamHref,
				away: { code: 'GSW', name: 'Warriors', periods: [28], total: 28 },
				home: { code: 'LAL', name: 'Lakers', periods: [25], total: 25 }
			}
		});
		for (const name of ['GSW', 'Warriors']) {
			expect(screen.getByRole('link', { name }).getAttribute('href')).toBe('/team/gsw');
		}
		for (const name of ['LAL', 'Lakers']) {
			expect(screen.getByRole('link', { name }).getAttribute('href')).toBe('/team/lal');
		}
	});
});

describe('LineScore with a guest team', () => {
	it('does not link the guest code or name and links the league ones', () => {
		const { container } = render(LineScore, {
			props: {
				teamHref,
				detail: true,
				away: { code: 'HCM', name: 'Mariners', guest: true, periods: [28, 26, 24, 34], total: 112 },
				home: { ...regulation.home, name: 'Lakers' }
			}
		});
		const links = [...container.querySelectorAll('a')].map((a) => a.textContent);
		expect(links).toEqual(['LAL', 'Lakers']);
		expect(container.textContent).toContain('HCM');
		expect(container.textContent).toContain('Mariners');
	});
});
