// web/tests/lib/components/GameVideos.test.ts
//
// Tests for the GameVideos component.
//
// Tested:
// - Every card is an external link with the video href, a new tab and noopener
// - No iframe is rendered, even after a click
// - The thumbnail when present, the grid frame when null
// - Duration and title; the layout class
//
// What is covered:
// - Each state and the click
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/GameVideos.test.ts
//
// SEE: web/src/lib/components/GameVideos.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import type { VideosSection } from '../../../src/lib/game/types';

import GameVideos from '../../../src/lib/components/GameVideos.svelte';

const videos: VideosSection = [
	{ title: 'Curry hits seven threes', duration: '2:14', thumbnail: '/t.svg', href: '/video/1' },
	{ title: 'Full game recap', duration: '5:30', thumbnail: null, href: '/video/2' }
];

describe('GameVideos', () => {
	it('opens every video in a new tab with its href and noopener', () => {
		render(GameVideos, { props: { videos, layout: 'desktop' } });
		const links = screen.getAllByRole('link');
		expect(links.map((a) => a.getAttribute('href'))).toEqual(['/video/1', '/video/2']);
		for (const link of links) {
			expect(link.getAttribute('target')).toBe('_blank');
			expect(link.getAttribute('rel')).toContain('noopener');
		}
	});

	it('never embeds a video, even after a click', async () => {
		const { container } = render(GameVideos, { props: { videos, layout: 'desktop' } });
		await fireEvent.click(screen.getAllByRole('link')[0]);
		expect(container.querySelector('iframe')).toBeNull();
	});

	it('shows the thumbnail when present and the grid frame when null', () => {
		const { container } = render(GameVideos, { props: { videos, layout: 'desktop' } });
		const thumbs = container.querySelectorAll('.thumb');
		expect(thumbs[0].querySelector('img')?.getAttribute('src')).toBe('/t.svg');
		expect(thumbs[1].querySelector('img')).toBeNull();
		expect(thumbs[1].querySelector('.bare-grid')).not.toBeNull();
	});

	it('shows the duration and the title of each video', () => {
		render(GameVideos, { props: { videos, layout: 'desktop' } });
		expect(screen.getByText('2:14')).toBeTruthy();
		expect(screen.getByText('Full game recap')).toBeTruthy();
	});

	it('uses the layout class', () => {
		const { container, unmount } = render(GameVideos, { props: { videos, layout: 'mobile' } });
		expect(container.querySelector('ul')?.classList.contains('mobile')).toBe(true);
		unmount();
		const desktop = render(GameVideos, { props: { videos, layout: 'desktop' } });
		expect(desktop.container.querySelector('ul')?.classList.contains('desktop')).toBe(true);
	});
});
