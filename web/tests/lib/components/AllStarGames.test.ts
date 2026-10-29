// web/tests/lib/components/AllStarGames.test.ts
//
// Tests for the AllStarGames component.
//
// Tested:
// - The kicker, the heading and the format line; one card per game with the default one selected
// - Clicking a card updates the detail and resets the box score tab to the first team
// - The embed with a stored highlight: a thumbnail that plays an iframe
// - A past edition with no highlights and no edition video (the 2024-25 shape) draws the media frame with the unavailable placeholder, not muted, on both layouts, even for a game that was not final
// - The placeholder texts for a final game without highlights and a live game
// - The venue strip, the Top 5, the scoreboard and the team statistics
// - A scheduled game shows the one centered card and no box score
// - The leaders on desktop and none on mobile; the strip class on mobile; the cards row stays in its container on mobile (ADR 0054)
// - The status is re-read on each tick
// - The edition video replaces the game's media, plays on a click, is kept across a game change and has a caption; without it the placeholder shows
// - No game card holds a video, a thumbnail or a highlight label
// - The kicker is drawn inside SectionHead, before the title and the format line
//
// What is covered:
// - Each state the section shows, drawn from the recorded feeds with a real selection and tick
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/AllStarGames.test.ts
//
// SEE: web/src/lib/components/AllStarGames.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { tick as flush } from 'svelte';
import { describe, expect, it } from 'vitest';

import type { HighlightVideo } from '../../../src/lib/schedule/types';

import { LiveTick } from '../../../src/lib/all-star/live-tick.svelte';
import { GameSelection } from '../../../src/lib/all-star/selection.svelte';
import AllStarGames from '../../../src/lib/components/AllStarGames.svelte';
import { toAllStarView } from '../../../src/lib/feed/all-star-props';
import { feedOf, playerHref, teamHref, viewOf } from '../all-star/views';

const EDITION: HighlightVideo = {
	id: 'https://video.example.com/embed/edition',
	title: 'Edition recap',
	channel: 'Example Channel',
	thumbnail: 'https://video.example.com/thumb/edition.jpg',
	embedUrl: 'https://video.example.com/embed/edition?autoplay=1'
};

function show(
	name: 'live' | 'after' = 'after',
	layout: 'desktop' | 'mobile' = 'desktop',
	selection = new GameSelection(),
	tick = new LiveTick(),
	editionVideo: HighlightVideo | null = null
) {
	const view = { ...viewOf(name), editionVideo };
	const result = render(AllStarGames, {
		props: { view, kicker: view.header.tag, selection, tick, layout, teamHref, playerHref }
	});
	return { ...result, selection, tick, view };
}

const pressed = (container: HTMLElement) =>
	[...container.querySelectorAll('.game-card')].map((c) => c.getAttribute('aria-pressed'));

describe('AllStarGames in a past edition with no highlights', () => {
	it.each(['desktop', 'mobile'] as const)(
		'draws the media frame with the unavailable placeholder on %s',
		(layout) => {
			const view = toAllStarView(feedOf('live'), 'current', { pastLabel: '2024-25' })!;
			view.editionVideo = null;
			const { container } = render(AllStarGames, {
				props: {
					view,
					kicker: view.header.tag,
					selection: new GameSelection(),
					tick: new LiveTick(),
					layout,
					teamHref,
					playerHref
				}
			});
			const placeholder = container.querySelector('.media .placeholder');
			expect(placeholder?.textContent).toContain('Highlights not available');
			expect(placeholder?.classList.contains('muted')).toBe(false);
			expect(container.querySelector('.scheduled')).toBeNull();
			expect(screen.queryByText('Highlights post after the final buzzer')).toBeNull();
		}
	);
});

describe('AllStarGames', () => {
	it('draws every frame with the All-Star corner marks', () => {
		const { container } = show();
		const frames = container.querySelectorAll('.blueprint-frame');
		expect(frames.length).toBeGreaterThan(0);
		for (const frame of frames) expect(frame.classList.contains('marks-allstar')).toBe(true);
	});

	it('draws the kicker inside SectionHead, before the title and its format line', () => {
		const { container } = show();
		const titled = container.querySelector('.titled');
		expect(titled?.children[0]?.textContent).toBe('All-Star 2027');
		expect(titled?.querySelector('.section-head h2')?.textContent?.trim()).toBe('Games');
		expect(titled?.querySelector('.section-head .meta')?.textContent).toBe('1 period · 12 min');
	});

	it('has the kicker, the heading, the format line and a card per game', () => {
		const { container } = show();
		expect(screen.getByText('All-Star 2027')).toBeTruthy();
		expect(screen.getByRole('heading', { level: 2, name: 'Games' })).toBeTruthy();
		expect(screen.getByText('1 period · 12 min')).toBeTruthy();
		expect(container.querySelectorAll('.game-card')).toHaveLength(4);
	});

	it('selects the default game of the feed', () => {
		expect(pressed(show().container)).toEqual(['false', 'false', 'false', 'true']);
		expect(pressed(show('live').container)).toEqual(['false', 'true', 'false']);
	});

	it('updates the detail on a click and resets the box score tab to the first team', async () => {
		const { container, selection } = show();
		selection.showBox('home');
		await flush();
		expect(container.querySelector('[role=tab][aria-selected=true]')?.textContent?.trim()).toBe(
			'WAV'
		);
		await fireEvent.click(container.querySelectorAll('.game-card')[1]);
		expect(pressed(container)).toEqual(['false', 'true', 'false', 'false']);
		expect(container.querySelector('[role=tab][aria-selected=true]')?.textContent?.trim()).toBe(
			'PKS'
		);
		expect(container.querySelector('.score-status')?.textContent).toBe('Final · OT');
	});

	it('plays the stored highlight in an iframe after the thumbnail is pressed', async () => {
		const { container } = show();
		expect(container.querySelector('iframe')).toBeNull();
		await fireEvent.click(screen.getByRole('button', { name: 'Play Example highlights' }));
		expect(container.querySelector('iframe')?.getAttribute('src')).toBe(
			'https://example.com/embed/g?autoplay=1'
		);
	});

	it('shows the placeholder text of a final game with no highlights', async () => {
		const { container } = show();
		await fireEvent.click(container.querySelectorAll('.game-card')[0]);
		expect(screen.getByText('Highlights not available')).toBeTruthy();
		expect(container.querySelector('.placeholder')?.classList.contains('muted')).toBe(false);
	});

	it('shows the after-the-buzzer text with a muted button for a live game', () => {
		const { container } = show('live');
		expect(screen.getByText('Highlights post after the final buzzer')).toBeTruthy();
		expect(container.querySelector('.placeholder')?.classList.contains('muted')).toBe(true);
	});

	it('shows the venue strip, the Top 5, the scoreboard and the statistics', () => {
		const { container } = show();
		expect([...container.querySelectorAll('.venue-item dt')].map((d) => d.textContent)).toEqual([
			'Venue',
			'Attendance',
			'Broadcast',
			'Tip-off'
		]);
		expect(screen.getByRole('heading', { level: 3, name: 'Top 5' })).toBeTruthy();
		expect(container.querySelectorAll('.top5 li')).toHaveLength(4);
		expect([...container.querySelectorAll('.score-value')].map((s) => s.textContent)).toEqual([
			'25',
			'23'
		]);
		expect(container.querySelectorAll('.team-stats .stat')).toHaveLength(6);
	});

	it('shows the one centered card and no box score for a scheduled game', async () => {
		const { container } = show('live');
		await fireEvent.click(container.querySelectorAll('.game-card')[2]);
		expect(screen.getByText('Tip-off · 8:20 PM')).toBeTruthy();
		expect(
			screen.getByText('Box score, leaders and highlights appear once the game starts.')
		).toBeTruthy();
		expect(container.querySelector('.detail')).toBeNull();
		expect(container.querySelector('[role=table]')).toBeNull();
	});

	it('draws the leaders on desktop and none on mobile', () => {
		expect(show().container.querySelector('.leaders')).not.toBeNull();
		expect(show('after', 'mobile').container.querySelector('.leaders')).toBeNull();
	});

	it('draws no team mark before the leaders codes', () => {
		const { container } = show();
		expect(container.querySelectorAll('.leaders .leader-code').length).toBeGreaterThan(0);
		expect(container.querySelectorAll('.leader-code .team-monogram').length).toBe(0);
	});

	it('keeps the cards row in its scrolling container on mobile', () => {
		const { container } = show('after', 'mobile');
		const cards = container.querySelector('.all-star-games.mobile .cards');
		expect(cards).not.toBeNull();
		expect(cards?.getAttribute('role')).toBe('group');
	});

	it('lays the cards out as a strip on mobile', () => {
		const { container } = show('after', 'mobile');
		expect(container.querySelector('.all-star-games')?.classList.contains('mobile')).toBe(true);
		expect(container.querySelector('.detail')?.classList.contains('mobile')).toBe(true);
	});

	it('re-reads the live status on each tick and never counts down', async () => {
		const { container, tick } = show('live');
		expect(container.querySelector('.score-status')?.textContent).toBe('Live · Q1 · 5:12');
		tick.tick += 1;
		await flush();
		expect(container.querySelector('.score-status')?.textContent).toBe('Live · Q1 · 5:12');
	});

	it('keeps the picked game when the section is shown again', async () => {
		const { container, selection } = show();
		await fireEvent.click(container.querySelectorAll('.game-card')[0]);
		expect(selection.selected).toBe('g1');
	});
});

describe('AllStarGames edition video', () => {
	it('shows the edition play button and caption in place of the placeholder, and plays on a click', async () => {
		const { container } = show('after', 'desktop', new GameSelection(), new LiveTick(), EDITION);
		expect(container.querySelector('.placeholder')).toBeNull();
		expect(screen.getByText('Edition highlights')).toBeTruthy();
		expect(container.querySelector('iframe')).toBeNull();
		await fireEvent.click(screen.getByRole('button', { name: 'Play Edition recap' }));
		expect(container.querySelector('iframe')?.getAttribute('src')).toBe(EDITION.embedUrl);
	});

	it('keeps the edition frame, playing, when another game is selected', async () => {
		const { container } = show('after', 'desktop', new GameSelection(), new LiveTick(), EDITION);
		await fireEvent.click(screen.getByRole('button', { name: 'Play Edition recap' }));
		await fireEvent.click(container.querySelectorAll('.game-card')[0]);
		expect(container.querySelector('iframe')?.getAttribute('src')).toBe(EDITION.embedUrl);
		expect(screen.getByText('Edition highlights')).toBeTruthy();
	});

	it('shows the placeholder and no caption without an edition video', async () => {
		const { container } = show();
		await fireEvent.click(container.querySelectorAll('.game-card')[0]);
		expect(screen.getByText('Highlights not available')).toBeTruthy();
		expect(screen.queryByText('Edition highlights')).toBeNull();
	});

	it('draws no video, thumbnail or highlight label on the game cards', () => {
		const { container } = show('after', 'desktop', new GameSelection(), new LiveTick(), EDITION);
		for (const card of container.querySelectorAll('.game-card')) {
			expect(card.querySelector('iframe, video, img, button.thumb')).toBeNull();
			expect(card.textContent?.toLowerCase()).not.toContain('highlight');
		}
	});
});
