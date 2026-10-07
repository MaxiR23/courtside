// web/tests/lib/components/TeamStats.test.ts
//
// Tests for the TeamStats component.
//
// Tested:
// - The five stats with away value, label and home value
// - The leading side for FG%, 3P%, rebounds and assists is the higher one
// - The leading side for turnovers is the lower one
// - A tied stat leads no side
// - The bars grow when the panel opens
// - The labels in Spanish with a Spanish browser preference
// - Detail mode: eight stats in order, the leading side from the feed, Spanish labels
//
// What is covered:
// - Each leading case, the tie, the open motion and Spanish
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/TeamStats.test.ts
//
// SEE: web/src/lib/components/TeamStats.svelte
import { render } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { DetailTeamStatLine, StatLeads } from '../../../src/lib/game/types';
import type { TeamStatLine } from '../../../src/lib/schedule/types';
import { preferLanguages } from '../../prefer-languages';

import TeamStats from '../../../src/lib/components/TeamStats.svelte';

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	Reflect.deleteProperty(HTMLElement.prototype, 'animate');
});

const away: TeamStatLine = {
	fieldGoalPct: 0.478,
	threePointPct: 0.391,
	rebounds: 44,
	assists: 27,
	turnovers: 9
};
const home: TeamStatLine = {
	fieldGoalPct: 0.452,
	threePointPct: 0.417,
	rebounds: 41,
	assists: 30,
	turnovers: 14
};

const stats = (container: HTMLElement) => [...container.querySelectorAll('.stat')];
const leads = (stat: Element) => ({
	away: stat.querySelector('.stat-value.away')?.classList.contains('lead'),
	home: stat.querySelector('.stat-value.home')?.classList.contains('lead'),
	awayBar: stat.querySelector('.half.away .bar')?.classList.contains('lead'),
	homeBar: stat.querySelector('.half.home .bar')?.classList.contains('lead')
});

describe('TeamStats', () => {
	it('shows the five stats with away value, label and home value', () => {
		const { container } = render(TeamStats, { props: { away, home, open: true } });
		const text = stats(container).map((s) =>
			[...s.querySelectorAll('.stat-head > span')].map((e) => e.textContent)
		);
		expect(text).toEqual([
			['47.8%', 'FG%', '45.2%'],
			['39.1%', '3P%', '41.7%'],
			['44', 'Rebounds', '41'],
			['27', 'Assists', '30'],
			['9', 'Turnovers', '14']
		]);
	});

	it('marks the higher side as leading for FG%, 3P%, rebounds and assists', () => {
		const { container } = render(TeamStats, { props: { away, home, open: true } });
		const [fg, tp, reb, ast] = stats(container);
		for (const stat of [fg, reb]) {
			expect(leads(stat)).toEqual({ away: true, home: false, awayBar: true, homeBar: false });
		}
		for (const stat of [tp, ast]) {
			expect(leads(stat)).toEqual({ away: false, home: true, awayBar: false, homeBar: true });
		}
	});

	it('marks the side with fewer turnovers as leading', () => {
		const { container } = render(TeamStats, { props: { away, home, open: true } });
		expect(leads(stats(container)[4])).toEqual({
			away: true,
			home: false,
			awayBar: true,
			homeBar: false
		});
	});

	it('marks no side as leading on a tied stat', () => {
		const { container } = render(TeamStats, {
			props: { away, home: { ...home, rebounds: 44 }, open: true }
		});
		expect(leads(stats(container)[2])).toEqual({
			away: false,
			home: false,
			awayBar: false,
			homeBar: false
		});
	});

	it('grows the bars when the panel opens', async () => {
		const animate = vi.fn(() => ({ cancel: vi.fn() }));
		Object.assign(HTMLElement.prototype, { animate });
		vi.stubGlobal('matchMedia', () => ({ matches: false }));
		const { rerender } = render(TeamStats, { props: { away, home, open: false } });
		expect(animate).not.toHaveBeenCalled();
		await rerender({ away, home, open: true });
		expect(animate).toHaveBeenCalledTimes(10);
	});

	it('shows the labels in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		const { container } = render(TeamStats, { props: { away, home, open: true } });
		const labels = [...container.querySelectorAll('.stat-label')].map((e) => e.textContent);
		expect(labels).toEqual(['TC%', 'T3%', 'Rebotes', 'Asistencias', 'Pérdidas']);
		expect(container.querySelector('.stat-value')?.textContent).toMatch(/^47,8\s%$/);
	});

	describe('detail mode', () => {
		const detailAway: DetailTeamStatLine = {
			...away,
			freeThrowPct: 0.8,
			steals: 5,
			blocks: 3
		};
		const detailHome: DetailTeamStatLine = {
			...home,
			freeThrowPct: 0.75,
			steals: 7,
			blocks: 2
		};
		const noLeads: StatLeads = {
			fieldGoalPct: null,
			threePointPct: null,
			freeThrowPct: null,
			rebounds: null,
			assists: null,
			turnovers: null,
			steals: null,
			blocks: null
		};
		const detail = (leads: StatLeads) => ({
			away: detailAway,
			home: detailHome,
			open: true,
			leads
		});

		it('shows the eight detail stats in order with FT%, steals and blocks', () => {
			const { container } = render(TeamStats, { props: detail(noLeads) });
			const text = stats(container).map((s) =>
				[...s.querySelectorAll('.stat-head > span')].map((e) => e.textContent)
			);
			expect(text).toEqual([
				['47.8%', 'FG%', '45.2%'],
				['39.1%', '3P%', '41.7%'],
				['80.0%', 'FT%', '75.0%'],
				['44', 'Rebounds', '41'],
				['27', 'Assists', '30'],
				['9', 'Turnovers', '14'],
				['5', 'Steals', '7'],
				['3', 'Blocks', '2']
			]);
		});

		it('marks the leading side the feed sends, even when the values say otherwise', () => {
			// Away has the higher FG% but the feed names home.
			const { container } = render(TeamStats, {
				props: detail({ ...noLeads, fieldGoalPct: 'home', turnovers: 'away' })
			});
			const [fg] = stats(container);
			expect(leads(fg)).toEqual({ away: false, home: true, awayBar: false, homeBar: true });
			expect(leads(stats(container)[5]).away).toBe(true);
		});

		it('marks no side when the feed sends no leader for a stat', () => {
			const { container } = render(TeamStats, { props: detail(noLeads) });
			for (const stat of stats(container)) {
				expect(leads(stat)).toEqual({ away: false, home: false, awayBar: false, homeBar: false });
			}
		});

		it('shows the detail labels in Spanish with a Spanish preference', () => {
			preferLanguages(['es-ES']);
			const { container } = render(TeamStats, { props: detail(noLeads) });
			const labels = [...container.querySelectorAll('.stat-label')].map((e) => e.textContent);
			expect(labels).toEqual([
				'TC%',
				'T3%',
				'TL%',
				'Rebotes',
				'Asistencias',
				'Pérdidas',
				'Robos',
				'Tapones'
			]);
		});
	});
});
