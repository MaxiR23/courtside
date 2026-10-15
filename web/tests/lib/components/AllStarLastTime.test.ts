// web/tests/lib/components/AllStarLastTime.test.ts
//
// Tests for the AllStarLastTime component.
//
// Tested:
// - The champion card: kicker, name, date and venue, score
// - The MVP card: name, league team and summary, linking to the player
// - No MVP card without an MVP
// - The link text and its href /all-star/previous
// - The champion card links to the edition video in a new tab when there is one, and is not a link otherwise
//
// What is covered:
// - Each state the section shows, drawn from the recorded feeds
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/AllStarLastTime.test.ts
//
// SEE: web/src/lib/components/AllStarLastTime.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import AllStarLastTime from '../../../src/lib/components/AllStarLastTime.svelte';
import { playerHref, viewOf } from '../all-star/views';

const lastTime = () => viewOf('before').lastTime!;
const show = (view = lastTime(), layout: 'desktop' | 'mobile' = 'desktop') =>
	render(AllStarLastTime, { props: { lastTime: view, layout, playerHref } });

describe('AllStarLastTime', () => {
	it('draws every frame with the All-Star corner marks', () => {
		const { container } = show();
		const frames = container.querySelectorAll('.blueprint-frame');
		expect(frames.length).toBeGreaterThan(0);
		for (const frame of frames) expect(frame.classList.contains('marks-allstar')).toBe(true);
	});

	it('shows the champion card', () => {
		show();
		expect(screen.getByText('Champions of the day')).toBeTruthy();
		expect(screen.getByText('Team Dunes')).toBeTruthy();
		expect(screen.getByText('Feb 15 · Example Arena')).toBeTruthy();
		expect(screen.getByText('22–20')).toBeTruthy();
	});

	it('shows the MVP card linking to the player', () => {
		const { container } = show();
		const card = container.querySelector('a.mvp-card')!;
		expect(card.getAttribute('href')).toBe('/player/4001');
		expect(card.textContent).toContain('Gus Imagined');
		expect(card.textContent).toContain('RDG');
		expect(card.textContent).toContain('24 PTS · across 2 games');
	});

	it('draws no MVP card without an MVP', () => {
		const { container } = show({ ...lastTime(), mvp: null });
		expect(container.querySelector('.mvp-card')).toBeNull();
		expect(screen.getByText('Team Dunes')).toBeTruthy();
	});

	it('links to the previous edition', () => {
		show();
		const link = screen.getByRole('link', {
			name: 'Every game, box score and highlight from 2026 →'
		});
		expect(link.getAttribute('href')).toBe('/all-star/previous');
	});

	it('adds the mobile class with the mobile layout', () => {
		const { container } = show(lastTime(), 'mobile');
		expect(container.querySelector('.last-time')?.classList.contains('mobile')).toBe(true);
	});
});

describe('AllStarLastTime edition video', () => {
	const URL_ = 'https://video.example.com/embed/last';

	it('links the champion card to the video in a new tab', () => {
		const { container } = show({ ...lastTime(), video: URL_ });
		const card = container.querySelector('a.champion-card')!;
		expect(card.getAttribute('href')).toBe(URL_);
		expect(card.getAttribute('target')).toBe('_blank');
		expect(card.getAttribute('rel')).toContain('noopener');
		expect(card.textContent).toContain('Team Dunes');
		expect(screen.getByRole('link', { name: /Every game/ }).getAttribute('href')).toBe(
			'/all-star/previous'
		);
	});

	it('draws the champion card as a plain block without a video', () => {
		const { container } = show({ ...lastTime(), video: null });
		expect(container.querySelector('a.champion-card')).toBeNull();
		expect(container.querySelector('div.champion-card')?.textContent).toContain('Team Dunes');
		expect(screen.getByRole('link', { name: /Every game/ }).getAttribute('href')).toBe(
			'/all-star/previous'
		);
	});
});
