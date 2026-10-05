// web/tests/routes/preview/Preview.test.ts
//
// Tests for the development-only component preview content.
//
// Tested:
// - Shows every base component in each of its variants
// - Shows the hero in its three states and the footer
// - Shows the day strip, every game card state on both rows, and the schedule
// - Shows an expanded card for a scheduled, a live, a final and an overtime game
// - Shows a final game with highlights and one with highlights pending, and plays a placeholder
// - Uses no external URL for images, players or links
//
// What is covered:
// - The only state it has (static sample content)
//
// Run with: cd web && pnpm exec vitest run tests/routes/preview/Preview.test.ts
//
// SEE: web/src/routes/preview/Preview.svelte
import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import Preview from '../../../src/routes/preview/Preview.svelte';

function sectionOf(name: string): HTMLElement {
	const section = screen.getByRole('heading', { level: 2, name }).closest('section');
	if (!section) throw new Error(`No section for ${name}`);
	return section;
}

describe('component preview', () => {
	it('shows every base component in each of its variants', () => {
		render(Preview);
		for (const name of [
			'BlueprintFrame',
			'Button',
			'LiveBadge',
			'StatusTag',
			'Kicker',
			'TeamMonogram'
		]) {
			expect(screen.getByRole('heading', { level: 2, name })).toBeTruthy();
		}
		expect(screen.getByRole('button', { name: 'Primary action' })).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Secondary link' })).toBeTruthy();
		expect(within(sectionOf('LiveBadge')).getByText('LIVE')).toBeTruthy();
		for (const label of ['Tonight', 'Live now', 'Final']) {
			expect(screen.getAllByText(label).length).toBeGreaterThanOrEqual(1);
		}
		expect(screen.getAllByText('10:30 PM ET · Chase Center').length).toBeTruthy();
		const monograms = sectionOf('TeamMonogram');
		expect(monograms.querySelectorAll('.team-monogram.large')).toHaveLength(1);
		expect(monograms.querySelectorAll('.team-monogram.small')).toHaveLength(1);
	});

	it('shows every game card state on the desktop and mobile rows', () => {
		render(Preview);
		for (const [name, row] of [
			['GameCard: desktop row', '.row.desktop'],
			['GameCard: mobile row', '.row.mobile']
		] as const) {
			const section = sectionOf(name);
			expect(section.querySelectorAll(row)).toHaveLength(3);
			expect(within(section).getByText('LIVE')).toBeTruthy();
			expect(within(section).getByText('Final')).toBeTruthy();
			expect(section.textContent).toContain('9:00');
		}
	});

	it('shows the schedule and a day with no games', () => {
		render(Preview);
		const schedule = sectionOf('Schedule');
		expect(schedule.querySelectorAll('.games > li')).toHaveLength(3);
		const empty = sectionOf('Schedule: day with no games');
		expect(within(empty).getAllByText('0 games').length).toBeGreaterThanOrEqual(1);
		expect(empty.querySelectorAll('.games > li')).toHaveLength(0);
	});

	it('shows an expanded card for a scheduled, a live, a final and an overtime game', () => {
		render(Preview);
		const sections = [
			'GameCard: expanded scheduled',
			'GameCard: expanded live',
			'GameCard: expanded final',
			'GameCard: expanded overtime'
		].map(sectionOf);
		for (const section of sections) {
			expect(section.querySelector('[aria-expanded="true"]')).not.toBeNull();
		}
		const [scheduled, live, final, overtime] = sections;
		expect(within(scheduled).getByText('Players to watch')).toBeTruthy();
		expect(
			within(live).getByText('Highlights will appear here after the final buzzer.')
		).toBeTruthy();
		expect(
			within(final).queryByText('Highlights will appear here after the final buzzer.')
		).toBeNull();
		expect(within(overtime).getByText('OT')).toBeTruthy();
		expect(within(overtime).getByText('2OT')).toBeTruthy();
	});

	it('shows the day strip on desktop and compact', () => {
		render(Preview);
		const strips = sectionOf('DayStrip').querySelectorAll('.day-strip');
		expect(strips).toHaveLength(2);
		expect(strips[0].querySelector('.count')?.textContent?.trim()).toBe('1 game');
		expect(strips[1].querySelector('.count')?.textContent?.trim()).toBe('1');
	});

	it('shows the hero in its Tonight, Live now and Final states', () => {
		const { container } = render(Preview);
		for (const name of ['Hero: Tonight', 'Hero: Live now', 'Hero: Final']) {
			expect(screen.getByRole('heading', { level: 2, name })).toBeTruthy();
		}
		expect(container.querySelectorAll('.hero')).toHaveLength(3);
	});

	it('shows the footer', () => {
		render(Preview);
		expect(screen.getByRole('heading', { level: 2, name: 'SiteFooter' })).toBeTruthy();
		expect(screen.getByText('Personal project. Not affiliated with the NBA.')).toBeTruthy();
	});

	it('shows a final game with highlights and one with highlights pending', () => {
		render(Preview);
		const final = sectionOf('GameCard: expanded final');
		expect(within(final).getByText('Highlights')).toBeTruthy();
		expect(within(final).getByText('Video platform')).toBeTruthy();
		expect(within(final).getByText('Nuggets at Suns: full game highlights')).toBeTruthy();
		expect(within(final).getByText('Every three from the fourth quarter')).toBeTruthy();
		const pending = sectionOf('GameCard: expanded final, highlights pending');
		expect(
			within(pending).getByText("Highlights aren't in yet. They'll appear here automatically.")
		).toBeTruthy();
		expect(
			within(pending).getByRole('link', { name: 'Search highlights on Video platform' })
		).toBeTruthy();
	});

	it('plays the placeholder player in place when a preview highlight is clicked', async () => {
		render(Preview);
		const final = sectionOf('GameCard: expanded final');
		expect(final.querySelector('iframe')).toBeNull();
		await fireEvent.click(
			within(final).getByRole('button', { name: 'Play Nuggets at Suns: full game highlights' })
		);
		expect(final.querySelectorAll('iframe')).toHaveLength(1);
	});

	it('uses no external URL for images, players or links', async () => {
		const { container } = render(Preview);
		await fireEvent.click(
			within(sectionOf('GameCard: expanded final')).getByRole('button', {
				name: 'Play Nuggets at Suns: full game highlights'
			})
		);
		const images = container.querySelectorAll('img');
		const frames = container.querySelectorAll('iframe');
		expect(images.length).toBeGreaterThan(0);
		expect(frames.length).toBeGreaterThan(0);
		for (const el of container.querySelectorAll('img[src], iframe[src], a[href]')) {
			expect(el.getAttribute('src') ?? el.getAttribute('href') ?? '').not.toMatch(
				/^(https?:)?\/\//
			);
		}
	});
});
