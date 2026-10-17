// web/tests/lib/components/SeriesSheet.test.ts
//
// Tests for the SeriesSheet component.
//
// Tested:
// - A modal dialog named by the round title, with the series score
// - One row per listed game, a link to the game page only when the game has a detail page
// - The body scroll is locked while open and restored on unmount
// - Focus starts on Close
// - Esc, the scrim and Close call onClose
// - Spanish copy
//
// What is covered:
// - The sheet drawn from props with no fetch; the slide itself is not asserted (jsdom does not animate)
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/SeriesSheet.test.ts
//
// SEE: web/src/lib/components/SeriesSheet.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import SeriesSheet from '../../../src/lib/components/SeriesSheet.svelte';
import type { PlayoffsFeed } from '../../../src/lib/contract/playoffs';
import { toPlayoffsView } from '../../../src/lib/feed/playoffs-props';
import type { SeriesCardView } from '../../../src/lib/playoffs/types';
import { preferLanguages } from '../../prefer-languages';

const gameHref = (id: string) => `/game/${id}` as ResolvedPathname;

const card = (id: string): SeriesCardView =>
	toPlayoffsView(
		JSON.parse(
			readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'playoffs-bracket.json'), 'utf8')
		) as PlayoffsFeed,
		null
	).bracket.series.find((series) => series.id === id)!;

const show = (id = 'east-r1-2', onClose = vi.fn()) =>
	render(SeriesSheet, { props: { series: card(id), gameHref, onClose } });

afterEach(() => {
	vi.restoreAllMocks();
	document.body.style.overflow = '';
});

describe('SeriesSheet', () => {
	it('is a modal dialog named by the round title, with the series score', () => {
		show();
		const dialog = screen.getByRole('dialog', { name: 'East · Round 1' });
		expect(dialog.getAttribute('aria-modal')).toBe('true');
		expect(screen.getByText('Series tied 2–2')).toBeTruthy();
	});

	it('shows both sides with seed, code and wins', () => {
		const { container } = show();
		const sides = [...container.querySelectorAll('.sides > .side')];
		expect(sides.map((side) => side.textContent?.replace(/\s+/g, ' ').trim())).toEqual([
			'4 QXD 2',
			'5 QXE 2'
		]);
	});

	it('lists one row per game and links only the games with a detail page', () => {
		const { container } = show();
		expect(container.querySelectorAll('.game')).toHaveLength(5);
		const links = [...container.querySelectorAll('a')];
		expect(links.map((a) => a.getAttribute('href'))).toEqual([
			'/game/b201',
			'/game/b202',
			'/game/b203',
			'/game/b204'
		]);
	});

	it('lists no row for a series with no games', () => {
		const { container } = show('east-r1-4');
		expect(container.querySelectorAll('.game')).toHaveLength(0);
		expect(container.querySelector('.sides > .score')?.textContent).toBe('—');
	});

	it('shows the slot label of an undecided side', () => {
		show('east-r2-1');
		expect(screen.getByText('Winner of East R1 2')).toBeTruthy();
		expect(screen.getByText('To be decided')).toBeTruthy();
	});

	it('locks the body scroll while open and restores it on unmount', () => {
		document.body.style.overflow = 'auto';
		const { unmount } = show();
		expect(document.body.style.overflow).toBe('hidden');
		unmount();
		expect(document.body.style.overflow).toBe('auto');
	});

	it('starts the focus on Close', () => {
		show();
		expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Close' }));
	});

	it('closes with Esc, the scrim and Close', async () => {
		const onClose = vi.fn();
		const { container } = show('east-r1-2', onClose);
		await fireEvent.keyDown(window, { key: 'Escape' });
		await fireEvent.click(container.querySelector('.scrim')!);
		await fireEvent.click(screen.getByRole('button', { name: 'Close' }));
		expect(onClose).toHaveBeenCalledTimes(3);
	});

	it('keeps the focus inside the sheet on Tab from the last link', () => {
		const { container } = show();
		const links = [...container.querySelectorAll('a')];
		links.at(-1)!.focus();
		const event = new KeyboardEvent('keydown', { key: 'Tab', cancelable: true, bubbles: true });
		window.dispatchEvent(event);
		expect(event.defaultPrevented).toBe(true);
		expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Close' }));
	});

	it('writes the Spanish copy', () => {
		preferLanguages(['es-ES']);
		show();
		expect(screen.getByRole('button', { name: 'Cerrar' })).toBeTruthy();
		expect(screen.getByRole('dialog', { name: 'Este · Ronda 1' })).toBeTruthy();
	});
});
