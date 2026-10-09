// web/tests/lib/components/SearchOverlay.test.ts
//
// Tests for the SearchOverlay component, the dialog that searches players and teams.
//
// Tested:
// - Dialog: role, aria-modal, label; the input is focused on mount; the body scroll is locked and restored
// - Closing: Esc, the Esc button, a backdrop click and Cancel (mobile) call onClose; each layout has its own button
// - Empty input: only the input row, no labels, no lines, no clear button
// - Typing: teams first, then players, with their counts; rows link to /team and /player pages; clear empties the input
// - No results: the no-match line, with the input still focused
// - Cap: 8 players on desktop and 6 on mobile with "Show all N players", which lifts the cap
// - Keyboard: the first row is active, ArrowDown and ArrowUp wrap, Enter clicks the active link, hover sets the active row, Tab wraps to the input
// - Loading: no results until the index arrives; a 503, a rejected load and a missing URL show the unavailable line
// - Typing never loads again
// - Spanish: labels, buttons, the no-results line and the unavailable line
//
// What is covered:
// - Every state and interaction; the loader is a mock that reads the recorded fixture, no real network
// - jsdom does not animate or lay out: the motion and the sheet layout are judged by eye
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/SearchOverlay.test.ts
//
// SEE: web/src/lib/components/SearchOverlay.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { SearchFeed, SearchPlayer } from '../../../src/lib/contract/search';
import { SearchFeedStore } from '../../../src/lib/search/feed.svelte';
import { preferLanguages } from '../../prefer-languages';

import SearchOverlay from '../../../src/lib/components/SearchOverlay.svelte';

const recorded = (): SearchFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'search.json'), 'utf8')
	) as SearchFeed;

const manyPlayers = (): SearchFeed => {
	const feed = recorded();
	const extra: SearchPlayer[] = Array.from({ length: 10 }, (_, i) => ({
		id: `t${i}`,
		name: `Tester ${String.fromCharCode(65 + i)}`,
		shortName: `T. ${String.fromCharCode(65 + i)}`,
		number: null,
		position: null,
		positionAbbr: null,
		photoUrl: null,
		injury: null,
		team: { code: 'OKC', primary: null }
	}));
	return { ...feed, players: [...feed.players, ...extra] };
};

const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;
const playerHref = (id: string) => `/player/${id}` as ResolvedPathname;

function mount(
	load: (() => Promise<SearchFeed>) | null = () => Promise.resolve(recorded()),
	layout: 'desktop' | 'mobile' = 'desktop'
) {
	const onClose = vi.fn();
	const feed = new SearchFeedStore(load ?? undefined);
	const result = render(SearchOverlay, {
		props: { feed, layout, teamHref, playerHref, onClose }
	});
	return { ...result, onClose, feed };
}

const input = () => screen.getByRole('textbox') as HTMLInputElement;
async function type(text: string) {
	await fireEvent.input(input(), { target: { value: text } });
}
const isActive = (el: HTMLElement) => el.getAttribute('aria-current') === 'true';

afterEach(() => {
	vi.restoreAllMocks();
	document.body.style.overflow = '';
});

describe('dialog', () => {
	it('is a labelled modal dialog with the input focused', () => {
		mount();
		const dialog = screen.getByRole('dialog', { name: 'Search' });
		expect(dialog.getAttribute('aria-modal')).toBe('true');
		expect(document.activeElement).toBe(input());
		expect(input().placeholder).toBe('Search player or team');
	});

	it('locks the body scroll and restores it on unmount', () => {
		document.body.style.overflow = 'auto';
		const { unmount } = mount();
		expect(document.body.style.overflow).toBe('hidden');
		unmount();
		expect(document.body.style.overflow).toBe('auto');
	});
});

describe('closing', () => {
	it('closes on Esc', async () => {
		const { onClose } = mount();
		await fireEvent.keyDown(input(), { key: 'Escape' });
		await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
	});

	it('closes on the Esc button, not on Cancel, on desktop', async () => {
		const { onClose } = mount();
		expect(screen.queryByRole('button', { name: 'Cancel' })).toBeNull();
		await fireEvent.click(screen.getByRole('button', { name: 'Esc' }));
		await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
	});

	it('closes on a backdrop click', async () => {
		const { container, onClose } = mount();
		await fireEvent.click(container.ownerDocument.querySelector('.backdrop') as HTMLElement);
		await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
	});

	it('closes on Cancel, not on the Esc button, on mobile', async () => {
		const { onClose } = mount(null, 'mobile');
		expect(screen.queryByRole('button', { name: 'Esc' })).toBeNull();
		await fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
		await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
	});

	it('calls onClose once when closing is asked twice', async () => {
		const { onClose } = mount();
		await fireEvent.keyDown(input(), { key: 'Escape' });
		await fireEvent.keyDown(input(), { key: 'Escape' });
		await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
	});
});

describe('results', () => {
	it('shows only the input row with an empty input', async () => {
		const { feed } = mount();
		await waitFor(() => expect(feed.index).not.toBeNull());
		expect(screen.queryAllByRole('heading')).toHaveLength(0);
		expect(screen.queryAllByRole('link')).toHaveLength(0);
		expect(screen.queryByRole('button', { name: 'Clear' })).toBeNull();
	});

	it('shows teams first, then players, with their counts and links', async () => {
		mount();
		await type('okc');
		const headings = await screen.findAllByRole('heading');
		expect(headings.map((h) => h.textContent)).toEqual(['Teams · 1', 'Players · 2']);
		const links = screen.getAllByRole('link');
		expect(links.map((l) => l.getAttribute('href'))).toEqual([
			'/team/okc',
			'/player/1628983',
			'/player/1641000'
		]);
	});

	it('empties the input with the clear button and hides the results', async () => {
		mount();
		await type('okc');
		await screen.findAllByRole('link');
		await fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
		expect(input().value).toBe('');
		expect(screen.queryAllByRole('link')).toHaveLength(0);
		expect(document.activeElement).toBe(input());
	});

	it('shows the no-results line and keeps the input focused', async () => {
		mount();
		await type('zzz');
		expect(await screen.findByText('No players or teams match "zzz".')).toBeTruthy();
		expect(document.activeElement).toBe(input());
	});

	it('caps the players at 8 on desktop and lifts the cap with Show all', async () => {
		mount(() => Promise.resolve(manyPlayers()));
		await type('tester');
		await screen.findByRole('heading', { name: 'Players · 10' });
		expect(screen.getAllByRole('link')).toHaveLength(8);
		await fireEvent.click(screen.getByRole('button', { name: 'Show all 10 players' }));
		expect(screen.getAllByRole('link')).toHaveLength(10);
		expect(screen.queryByRole('button', { name: /Show all/ })).toBeNull();
	});

	it('caps the players at 6 on mobile', async () => {
		mount(() => Promise.resolve(manyPlayers()), 'mobile');
		await type('tester');
		await screen.findByRole('heading', { name: 'Players · 10' });
		expect(screen.getAllByRole('link')).toHaveLength(6);
		expect(screen.getByRole('button', { name: 'Show all 10 players' })).toBeTruthy();
	});

	it('closes at once when a row is opened', async () => {
		const { onClose } = mount();
		await type('okc');
		const [team] = await screen.findAllByRole('link');
		team.addEventListener('click', (e) => e.preventDefault());
		await fireEvent.click(team);
		expect(onClose).toHaveBeenCalledTimes(1);
	});
});

describe('keyboard', () => {
	it('starts on the first row and moves with ArrowDown and ArrowUp, wrapping at both ends', async () => {
		mount();
		await type('okc');
		const links = await screen.findAllByRole('link');
		expect(links.map(isActive)).toEqual([true, false, false]);
		await fireEvent.keyDown(input(), { key: 'ArrowDown' });
		expect(links.map(isActive)).toEqual([false, true, false]);
		await fireEvent.keyDown(input(), { key: 'ArrowUp' });
		await fireEvent.keyDown(input(), { key: 'ArrowUp' });
		expect(links.map(isActive)).toEqual([false, false, true]);
		await fireEvent.keyDown(input(), { key: 'ArrowDown' });
		expect(links.map(isActive)).toEqual([true, false, false]);
	});

	it('clicks the active link on Enter', async () => {
		mount();
		await type('okc');
		const links = await screen.findAllByRole('link');
		const clicked = vi.fn((e: Event) => e.preventDefault());
		links[1].addEventListener('click', clicked);
		await fireEvent.keyDown(input(), { key: 'ArrowDown' });
		await fireEvent.keyDown(input(), { key: 'Enter' });
		expect(clicked).toHaveBeenCalledTimes(1);
	});

	it('does nothing on Enter without rows', async () => {
		const { onClose } = mount();
		await type('zzz');
		await screen.findByText(/No players or teams match/);
		await fireEvent.keyDown(input(), { key: 'Enter' });
		expect(onClose).not.toHaveBeenCalled();
	});

	it('makes a hovered row active', async () => {
		mount();
		await type('okc');
		const links = await screen.findAllByRole('link');
		await fireEvent.mouseEnter(links[2]);
		expect(links.map(isActive)).toEqual([false, false, true]);
	});

	it('wraps Tab from the last control to the input', async () => {
		mount();
		await type('okc');
		const links = await screen.findAllByRole('link');
		const last = links[links.length - 1];
		last.focus();
		await fireEvent.keyDown(last, { key: 'Tab' });
		expect(document.activeElement).toBe(screen.getByRole('textbox'));
	});

	it('keeps Esc, arrows and Tab working once the focus sits on the dialog itself', async () => {
		const { onClose } = mount();
		await type('okc');
		const links = await screen.findAllByRole('link');
		const dialog = screen.getByRole('dialog');
		expect(dialog.getAttribute('tabindex')).toBe('-1');
		dialog.focus();
		expect(document.activeElement).toBe(dialog);
		await fireEvent.keyDown(dialog, { key: 'ArrowDown' });
		expect(links.map(isActive)).toEqual([false, true, false]);
		links[links.length - 1].focus();
		await fireEvent.keyDown(dialog, { key: 'Tab' });
		expect(document.activeElement).toBe(input());
		dialog.focus();
		await fireEvent.keyDown(dialog, { key: 'Escape' });
		await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
	});

	it('moves the Show all row into the navigation and clicks it on Enter', async () => {
		mount(() => Promise.resolve(manyPlayers()));
		await type('tester');
		await screen.findByRole('heading', { name: 'Players · 10' });
		await fireEvent.keyDown(input(), { key: 'ArrowUp' });
		expect(isActive(screen.getByRole('button', { name: 'Show all 10 players' }))).toBe(true);
		await fireEvent.keyDown(input(), { key: 'Enter' });
		expect(screen.getAllByRole('link')).toHaveLength(10);
	});
});

describe('loading and failure', () => {
	it('shows no results until the index arrives', async () => {
		let resolve: (feed: SearchFeed) => void = () => {};
		mount(() => new Promise<SearchFeed>((r) => (resolve = r)));
		await type('okc');
		expect(screen.queryAllByRole('link')).toHaveLength(0);
		expect(screen.queryByText(/No players or teams match/)).toBeNull();
		resolve(recorded());
		expect(await screen.findAllByRole('link')).toHaveLength(3);
	});

	it('shows the unavailable line on a rejected load', async () => {
		mount(() => Promise.reject(new Error('503')));
		expect(
			await screen.findByText("Data isn't available right now. Check back later.")
		).toBeTruthy();
	});

	it('shows the unavailable line without a feed URL', () => {
		mount(null);
		expect(screen.getByText("Data isn't available right now. Check back later.")).toBeTruthy();
	});

	it('loads once however much is typed', async () => {
		const load = vi.fn(() => Promise.resolve(recorded()));
		mount(load);
		for (const text of ['o', 'ok', 'okc', 'okc ', 'okc t']) await type(text);
		await screen.findAllByRole('link');
		expect(load).toHaveBeenCalledTimes(1);
	});
});

describe('Spanish', () => {
	it('shows the labels, buttons and lines in Spanish', async () => {
		preferLanguages(['es-ES']);
		mount(() => Promise.resolve(manyPlayers()));
		await type('tester');
		expect(await screen.findByRole('heading', { name: 'Jugadores · 10' })).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Ver los 10 jugadores' })).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Borrar' })).toBeTruthy();
		await type('okc');
		expect(await screen.findByRole('heading', { name: 'Equipos · 1' })).toBeTruthy();
		await type('zzz');
		expect(await screen.findByText('Ningún jugador ni equipo coincide con "zzz".')).toBeTruthy();
	});

	it('shows Cancelar on mobile and the unavailable line in Spanish', async () => {
		preferLanguages(['es-ES']);
		mount(() => Promise.reject(new Error('503')), 'mobile');
		expect(screen.getByRole('button', { name: 'Cancelar' })).toBeTruthy();
		expect(await screen.findByText(/Los datos no están disponibles/)).toBeTruthy();
	});
});
