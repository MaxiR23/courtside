// web/tests/lib/components/Highlights.test.ts
//
// Tests for the Highlights component.
//
// Tested:
// - The kicker with the platform name, one card per video, the pending state
// - Play buttons, the in-place autoplaying player and its removal
// - Focus moves to the player when a thumbnail starts it, and is not taken on a playing render
// - The pending message and the external search link
// - Spanish copy with a Spanish browser preference
// - Only the URLs and platform name received as props are rendered
//
// What is covered:
// - Both states (videos, pending), playing and not playing, plus interaction
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/Highlights.test.ts
//
// SEE: web/src/lib/components/Highlights.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { preferLanguages } from '../../prefer-languages';

import Highlights from '../../../src/lib/components/Highlights.svelte';

const videos = [
	{
		id: 'v1',
		title: 'First clip',
		channel: 'Channel one',
		thumbnail: '/thumb-1.svg',
		embedUrl: '/embed/1'
	},
	{
		id: 'v2',
		title: 'Second clip',
		channel: 'Channel two',
		thumbnail: '/thumb-2.svg',
		embedUrl: '/embed/2'
	}
];
const props = { platform: 'Test platform', searchUrl: '/search?q=x', videos };
const pending = { ...props, videos: [] };

afterEach(() => {
	vi.restoreAllMocks();
});

describe('Highlights', () => {
	it('shows the HIGHLIGHTS kicker with the platform name on the right', () => {
		const { container } = render(Highlights, { props });
		expect(container.querySelector('.kicker')?.textContent).toBe('Highlights');
		expect(container.querySelector('.platform')?.textContent).toBe('Test platform');
	});

	it('shows one card per video with its thumbnail, title and channel', () => {
		const { container } = render(Highlights, { props });
		const images = [...container.querySelectorAll('img')];
		expect(images.map((i) => i.getAttribute('src'))).toEqual(['/thumb-1.svg', '/thumb-2.svg']);
		for (const img of images) {
			expect(img.getAttribute('loading')).toBe('lazy');
			expect(img.getAttribute('alt')).toBe('');
		}
		for (const text of ['First clip', 'Second clip', 'Channel one', 'Channel two']) {
			expect(screen.getByText(text)).toBeTruthy();
		}
		expect(container.querySelectorAll('.blueprint-frame')).toHaveLength(2);
	});

	it('labels each thumbnail button "Play {title}" and shows no player until one is playing', () => {
		const { container } = render(Highlights, { props });
		expect(screen.getByRole('button', { name: 'Play First clip' })).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Play Second clip' })).toBeTruthy();
		expect(container.querySelector('iframe')).toBeNull();
	});

	it('calls onPlay with the video id when a thumbnail is clicked', async () => {
		const onPlay = vi.fn();
		render(Highlights, { props: { ...props, onPlay } });
		await fireEvent.click(screen.getByRole('button', { name: 'Play First clip' }));
		expect(onPlay).toHaveBeenCalledTimes(1);
		expect(onPlay).toHaveBeenCalledWith('v1');
	});

	it("replaces the playing video's thumbnail with the autoplaying embedded player", () => {
		const { container } = render(Highlights, { props: { ...props, playingId: 'v1' } });
		const frames = container.querySelectorAll('iframe');
		expect(frames).toHaveLength(1);
		expect(frames[0].getAttribute('src')).toBe('/embed/1');
		expect(frames[0].getAttribute('title')).toBe('First clip');
		expect(frames[0].getAttribute('allow')).toContain('autoplay');
		const [first, second] = container.querySelectorAll('li');
		expect(first.querySelector('img')).toBeNull();
		expect(first.querySelector('button')).toBeNull();
		expect(second.querySelector('img')?.getAttribute('src')).toBe('/thumb-2.svg');
	});

	it('moves focus to the player when a thumbnail starts it', async () => {
		const { container, rerender } = render(Highlights, { props });
		const button = screen.getByRole('button', { name: 'Play First clip' });
		button.focus();
		await rerender({ ...props, onPlay: () => rerender({ ...props, playingId: 'v1' }) });
		await fireEvent.click(screen.getByRole('button', { name: 'Play First clip' }));
		await tick();
		const frame = container.querySelector('iframe');
		expect(frame).not.toBeNull();
		expect(document.activeElement).toBe(frame);
	});

	it('does not take focus when rendered already playing', async () => {
		render(Highlights, { props: { ...props, playingId: 'v1' } });
		await tick();
		expect(document.activeElement).toBe(document.body);
	});

	it('removes the player when playingId goes back to null', async () => {
		const { container, rerender } = render(Highlights, { props: { ...props, playingId: 'v1' } });
		expect(container.querySelector('iframe')).not.toBeNull();
		await rerender({ ...props, playingId: null });
		expect(container.querySelector('iframe')).toBeNull();
		expect(container.querySelectorAll('img')).toHaveLength(2);
	});

	it('shows the pending message and the search link when there are no videos', () => {
		const { container } = render(Highlights, { props: pending });
		expect(
			screen.getByText("Highlights aren't in yet. They'll appear here automatically.")
		).toBeTruthy();
		expect(container.querySelector('ul, img, iframe')).toBeNull();
		const link = screen.getByRole('link', { name: 'Search highlights on Test platform' });
		expect(link.getAttribute('href')).toBe('/search?q=x');
		expect(link.getAttribute('target')).toBe('_blank');
		const rel = link.getAttribute('rel') ?? '';
		for (const token of ['external', 'noopener', 'noreferrer']) expect(rel).toContain(token);
	});

	it('shows its copy in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		const withVideos = render(Highlights, { props });
		expect(withVideos.container.querySelector('.kicker')?.textContent).toBe('Resúmenes');
		expect(screen.getByRole('button', { name: 'Reproducir First clip' })).toBeTruthy();
		withVideos.unmount();

		render(Highlights, { props: pending });
		expect(
			screen.getByText('Los resúmenes todavía no están. Aparecerán aquí automáticamente.')
		).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Buscar resúmenes en Test platform' })).toBeTruthy();
	});

	it('renders only the URLs and platform name it receives', () => {
		const given = new Set(['/thumb-1.svg', '/thumb-2.svg', '/embed/1', '/embed/2', '/search?q=x']);
		const playing = render(Highlights, { props: { ...props, playingId: 'v2' } });
		for (const el of playing.container.querySelectorAll('[src], [href]')) {
			expect(given.has(el.getAttribute('src') ?? el.getAttribute('href') ?? '')).toBe(true);
		}
		expect(playing.container.querySelector('.platform')?.textContent).toBe('Test platform');
		playing.unmount();

		const empty = render(Highlights, { props: pending });
		for (const el of empty.container.querySelectorAll('[src], [href]')) {
			expect(given.has(el.getAttribute('src') ?? el.getAttribute('href') ?? '')).toBe(true);
		}
	});
});
