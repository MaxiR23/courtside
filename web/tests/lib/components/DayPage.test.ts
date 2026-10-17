// web/tests/lib/components/DayPage.test.ts
//
// Tests for the DayPage component.
//
// Tested:
// - Ready with games: the header, one card per game, each linking to its game page, no highlights block without a platform name
// - The game list is named "Games on {date}" under a Games kicker, in English and in Spanish
// - With a platform name an open card has the highlights block and plays one video at a time, resetting when a card toggles
// - Ready with no game: the empty-day message
// - Loading: the busy skeleton and no card
// - Unavailable: the data unavailable row, in English and in Spanish
// - The footer in every state
// - A card opens and closes from its toggle, one at a time
//
// What is covered:
// - Each page state, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/DayPage.test.ts
//
// SEE: web/src/lib/components/DayPage.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import DayPage from '../../../src/lib/components/DayPage.svelte';
import type { DayFeed } from '../../../src/lib/contract/days';
import type { DayPageState } from '../../../src/lib/day/types';
import { toDayView } from '../../../src/lib/feed/day-props';
import { preferLanguages } from '../../prefer-languages';

vi.mock('$app/navigation', () => ({ afterNavigate: () => {} }));

const dayFeed = (): DayFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'day.json'), 'utf8')
	) as DayFeed;

const props = (state: DayPageState) => ({
	state,
	allGamesHref: '/' as ResolvedPathname,
	standingsHref: '/standings' as ResolvedPathname,
	previousHref: null,
	nextHref: null,
	calendar: null,
	layout: 'desktop' as const,
	gameHref: (id: string) => `/game/${id}` as ResolvedPathname,
	teamHref: (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname
});

const ready = (feed = dayFeed(), options: { videoPlatformName?: string } = {}): DayPageState => {
	const view = toDayView(feed, options);
	if (!view) throw new Error('The fixture day must be showable');
	return { kind: 'ready', view };
};

afterEach(() => {
	vi.restoreAllMocks();
});

describe('DayPage', () => {
	it('shows the header and one card per game', () => {
		const { container } = render(DayPage, { props: props(ready()) });
		expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('February 6, 1999');
		expect(container.querySelectorAll('ul.games > li')).toHaveLength(2);
		expect(screen.getByRole('contentinfo')).toBeTruthy();
	});

	it('links an open card to its game page and shows no highlights block', async () => {
		const { container } = render(DayPage, { props: props(ready()) });
		const toggle = container.querySelector('button.toggle') as HTMLButtonElement;
		await fireEvent.click(toggle);
		expect(toggle.getAttribute('aria-expanded')).toBe('true');
		const hrefs = container.querySelectorAll('a[href^="/game/"]');
		expect([...hrefs].map((a) => a.getAttribute('href'))).toEqual(['/game/7001', '/game/7002']);
		expect(container.querySelector('.panel-highlights')).toBeNull();
	});

	it('names the game list under a Games kicker', () => {
		const { container } = render(DayPage, { props: props(ready()) });
		expect(screen.getByRole('list', { name: 'Games on February 6, 1999' })).toBeTruthy();
		expect(container.querySelector('.page-section .kicker')?.textContent).toBe('Games');
	});

	it('names the game list in Spanish', () => {
		preferLanguages(['es-ES']);
		const { container } = render(DayPage, { props: props(ready()) });
		expect(screen.getByRole('list', { name: /^Partidos del / })).toBeTruthy();
		expect(container.querySelector('.page-section .kicker')?.textContent).toBe('Partidos');
	});

	it('plays one video at a time and resets when a card toggles', async () => {
		const feed = dayFeed();
		feed.day.games[1].highlights = [
			{
				title: 'Second clip',
				channel: 'League Channel',
				thumbnailUrl: 'https://example.com/thumbs/2.jpg',
				embedUrl: 'https://example.com/embed/2'
			}
		];
		const state = ready(feed, { videoPlatformName: 'Video platform' });
		const { container } = render(DayPage, { props: props(state) });
		const toggles = [...container.querySelectorAll<HTMLButtonElement>('button.toggle')];
		await fireEvent.click(toggles[0]);
		await fireEvent.click(screen.getByRole('button', { name: /Full game highlights/ }));
		expect(container.querySelectorAll('iframe')).toHaveLength(1);
		await fireEvent.click(toggles[1]);
		await fireEvent.click(screen.getByRole('button', { name: /Second clip/ }));
		expect(container.querySelectorAll('iframe')).toHaveLength(1);
		expect(container.querySelector('iframe')?.getAttribute('src')).toContain('/embed/2');
	});

	it('opens one card at a time', async () => {
		const { container } = render(DayPage, { props: props(ready()) });
		const [first, second] = [...container.querySelectorAll<HTMLButtonElement>('button.toggle')];
		await fireEvent.click(first);
		await fireEvent.click(second);
		expect(first.getAttribute('aria-expanded')).toBe('false');
		expect(second.getAttribute('aria-expanded')).toBe('true');
	});

	it('shows the empty-day message for a day with no game', () => {
		const feed = dayFeed();
		feed.day.games = [];
		const { container } = render(DayPage, { props: props(ready(feed)) });
		expect(screen.getByText('No games scheduled for this day.')).toBeTruthy();
		expect(container.querySelector('ul.games')).toBeNull();
	});

	it('shows a busy skeleton and no card while loading', () => {
		const { container } = render(DayPage, { props: props({ kind: 'loading' }) });
		expect(container.querySelector('[aria-busy="true"]')).not.toBeNull();
		expect(container.querySelector('button.toggle')).toBeNull();
		expect(screen.getByRole('contentinfo')).toBeTruthy();
	});

	it('shows the data unavailable row', () => {
		render(DayPage, { props: props({ kind: 'unavailable' }) });
		expect(screen.getByText("Data isn't available right now. Check back later.")).toBeTruthy();
		expect(screen.getByRole('contentinfo')).toBeTruthy();
	});

	it('shows the data unavailable row in Spanish for a Spanish browser', () => {
		preferLanguages(['es-ES']);
		render(DayPage, { props: props({ kind: 'unavailable' }) });
		expect(screen.queryByText("Data isn't available right now. Check back later.")).toBeNull();
		expect(screen.getByText(/disponibles/i)).toBeTruthy();
	});
});
