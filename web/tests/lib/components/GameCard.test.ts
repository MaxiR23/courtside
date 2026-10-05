// web/tests/lib/components/GameCard.test.ts
//
// Tests for the GameCard component.
//
// Tested:
// - Scheduled, live and final games on the desktop and the mobile row
// - The losing team of a final game is dimmed; ties and live games dim no one
// - Monogram sizes per row layout, decorative chevron
// - Spanish live badge with a Spanish browser preference
//
// What is covered:
// - Each card state on each row layout
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/GameCard.test.ts
//
// SEE: web/src/components/GameCard.svelte
import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ScheduleGame } from '../../../src/lib/schedule/types';
import { preferLanguages } from '../../prefer-languages';

import GameCard from '../../../src/lib/components/GameCard.svelte';

const away = { code: 'GSW', name: 'Warriors', city: 'Golden State' };
const home = { code: 'LAL', name: 'Lakers', city: 'Los Angeles' };
const scheduled: ScheduleGame = {
	id: 's',
	away,
	home,
	status: { state: 'scheduled', tipTime: '9:00', tipSuffix: 'PM ET', network: 'Prime Video' }
};
const live: ScheduleGame = {
	id: 'l',
	away,
	home,
	status: { state: 'live', period: 'Q3', clock: '4:12', awayScore: 78, homeScore: 74 }
};
const final = (awayScore: number, homeScore: number): ScheduleGame => ({
	id: 'f',
	away,
	home,
	status: { state: 'final', awayScore, homeScore }
});

afterEach(() => {
	vi.restoreAllMocks();
});

const dimmedText = (container: HTMLElement) =>
	[...container.querySelectorAll('.dimmed')].map((e) => e.textContent?.replace(/\s+/g, ' ').trim());

describe('GameCard', () => {
	it('shows the network on the status line and the tip time with its suffix on a scheduled game (desktop)', () => {
		const { container } = render(GameCard, { props: { game: scheduled, layout: 'desktop' } });
		expect(container.querySelector('.status-line')?.textContent?.trim()).toBe('Prime Video');
		expect(container.querySelector('.tip-time')?.textContent).toBe('9:00PM ET');
		expect(container.querySelector('.tip-time .suffix')?.textContent).toBe('PM ET');
		expect(container.querySelector('.score')).toBeNull();
	});

	it('shows "9:00 PM ET · Prime Video" on the status line of a scheduled game (mobile)', () => {
		const { container } = render(GameCard, { props: { game: scheduled, layout: 'mobile' } });
		expect(container.querySelector('.status-line')?.textContent?.trim()).toBe(
			'9:00 PM ET · Prime Video'
		);
		expect(container.querySelector('.score')).toBeNull();
	});

	it.each(['desktop', 'mobile'] as const)(
		'shows the live badge with the period and clock on a live game (%s)',
		(layout) => {
			const { container } = render(GameCard, { props: { game: live, layout } });
			expect(screen.getByText('LIVE')).toBeTruthy();
			expect(container.querySelector('.status-line')?.textContent).toContain('Q3 · 4:12');
			expect([...container.querySelectorAll('.score')].map((e) => e.textContent)).toEqual([
				'78',
				'74'
			]);
		}
	);

	it.each(['desktop', 'mobile'] as const)(
		'shows FINAL and both scores on a final game (%s)',
		(layout) => {
			const { container } = render(GameCard, { props: { game: final(112, 104), layout } });
			expect(container.querySelector('.status-line')?.textContent?.trim()).toBe('Final');
			expect([...container.querySelectorAll('.score')].map((e) => e.textContent)).toEqual([
				'112',
				'104'
			]);
		}
	);

	it('dims the losing team on a final game', () => {
		const desktop = render(GameCard, { props: { game: final(98, 104), layout: 'desktop' } });
		const text = dimmedText(desktop.container);
		expect(text.some((t) => t?.includes('Warriors'))).toBe(true);
		expect(text).toContain('98');
		expect(text.some((t) => t?.includes('Lakers'))).toBe(false);
		expect(text).not.toContain('104');
		desktop.unmount();

		const { container } = render(GameCard, { props: { game: final(112, 104), layout: 'mobile' } });
		const mobile = dimmedText(container);
		expect(mobile.some((t) => t?.includes('Lakers'))).toBe(true);
		expect(mobile).toContain('104');
		expect(mobile.some((t) => t?.includes('Warriors'))).toBe(false);
		expect(mobile).not.toContain('112');
	});

	it('dims neither team when a final game is tied', () => {
		for (const layout of ['desktop', 'mobile'] as const) {
			const { container, unmount } = render(GameCard, {
				props: { game: final(100, 100), layout }
			});
			expect(container.querySelectorAll('.dimmed')).toHaveLength(0);
			unmount();
		}
	});

	it('does not dim a team on a live game', () => {
		const { container } = render(GameCard, { props: { game: live, layout: 'desktop' } });
		expect(container.querySelectorAll('.dimmed')).toHaveLength(0);
	});

	it('uses the large monograms on the desktop row and the small ones on the mobile row', () => {
		const desktop = render(GameCard, { props: { game: scheduled, layout: 'desktop' } });
		expect(desktop.container.querySelectorAll('.team-monogram.large')).toHaveLength(2);
		expect(desktop.container.querySelectorAll('.team-monogram.small')).toHaveLength(0);
		desktop.unmount();
		const { container } = render(GameCard, { props: { game: scheduled, layout: 'mobile' } });
		expect(container.querySelectorAll('.team-monogram.small')).toHaveLength(2);
		expect(container.querySelectorAll('.team-monogram.large')).toHaveLength(0);
	});

	it('shows a decorative chevron', () => {
		for (const layout of ['desktop', 'mobile'] as const) {
			const { container, unmount } = render(GameCard, { props: { game: scheduled, layout } });
			expect(container.querySelector('svg.chevron')?.getAttribute('aria-hidden')).toBe('true');
			unmount();
		}
	});

	it('shows the live badge in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		render(GameCard, { props: { game: live, layout: 'desktop' } });
		expect(screen.getByText('EN VIVO')).toBeTruthy();
	});
});
