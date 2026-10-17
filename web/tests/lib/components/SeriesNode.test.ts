// web/tests/lib/components/SeriesNode.test.ts
//
// Tests for the SeriesNode component.
//
// Tested:
// - A decided series: seeds, codes, wins and the team strip colors
// - The loser row is muted
// - A side with an empty seed draws no seed number
// - An undecided side: the slot label and the note, each with its full text as title (ADR 0054); a one-sided series has one team row and one undecided row
// - The framed (mobile) card is dashed for no teams and dashes the empty row for one team
// - The Finals champion class
// - A click opens the series with its id and button; the card is a native button named from the series
// - Focus is reported as true only when the button matches :focus-visible
//
// What is covered:
// - Each state the card shows, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/SeriesNode.test.ts
//
// SEE: web/src/lib/components/SeriesNode.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import SeriesNode from '../../../src/lib/components/SeriesNode.svelte';
import type { PlayoffsFeed } from '../../../src/lib/contract/playoffs';
import { toPlayoffsView } from '../../../src/lib/feed/playoffs-props';
import type { SeriesCardView } from '../../../src/lib/playoffs/types';

const feed = (name: string) =>
	JSON.parse(readFileSync(join(__dirname, '..', 'feed', 'fixtures', name), 'utf8')) as PlayoffsFeed;

const card = (id: string, name = 'playoffs-bracket.json'): SeriesCardView =>
	toPlayoffsView(feed(name), null).bracket.series.find((series) => series.id === id)!;

const show = (series: SeriesCardView, framed = false, onOpen = vi.fn(), onFocusChange = vi.fn()) =>
	render(SeriesNode, { props: { series, framed, onOpen, onFocusChange } });

afterEach(() => {
	vi.restoreAllMocks();
});

describe('SeriesNode decided', () => {
	it('shows seeds, codes and wins of both sides', () => {
		const { container } = show(card('east-r1-2'));
		const rows = [...container.querySelectorAll('.row')];
		expect(rows).toHaveLength(2);
		expect(rows[0].textContent?.replace(/\s+/g, ' ').trim()).toBe('4 QXD 2');
		expect(rows[1].textContent?.replace(/\s+/g, ' ').trim()).toBe('5 QXE 2');
	});

	it('draws the team strip with the two colors', () => {
		const { container } = show(card('east-r1-2'));
		const halves = [...container.querySelectorAll<HTMLElement>('.row:first-child .half')];
		expect(halves.map((half) => half.style.backgroundColor)).toEqual([
			'rgb(90, 42, 130)',
			'rgb(192, 192, 192)'
		]);
	});

	it('mutes the loser row only', () => {
		const { container } = show(card('east-r1-1'));
		const rows = [...container.querySelectorAll('.row')];
		expect(rows.map((row) => row.classList.contains('loser'))).toEqual([false, true]);
	});

	it('writes a dash for missing wins', () => {
		const { container } = show(card('east-r1-4'));
		expect(container.querySelector('.row .wins')?.textContent).toBe('—');
	});
});

describe('SeriesNode undecided', () => {
	it('shows the slot label and the note of each undecided side', () => {
		const { container } = show(card('east-r2-2'));
		const rows = [...container.querySelectorAll('.row')];
		expect(rows.every((row) => row.classList.contains('undecided'))).toBe(true);
		expect(rows[0].querySelector('.slot-label')?.textContent).toBe('Winner of East R1 3');
		expect(rows[0].querySelector('.note')?.textContent).toBe('To be decided');
	});

	it('carries the full text of a slot label and a note as title', () => {
		const { container } = show(card('east-r2-2'));
		const row = container.querySelector('.row') as HTMLElement;
		expect(row.querySelector('.slot-label')?.getAttribute('title')).toBe('Winner of East R1 3');
		expect(row.querySelector('.note')?.getAttribute('title')).toBe('To be decided');
	});

	it('shows one team row and one undecided row for a one-sided series', () => {
		const { container } = show(card('east-r2-1'));
		const rows = [...container.querySelectorAll('.row')];
		expect(rows.map((row) => row.classList.contains('undecided'))).toEqual([false, true]);
		expect(rows[1].querySelector('.slot-label')?.textContent).toBe('Winner of East R1 2');
	});

	it('is dashed when framed with no team, and dashes the empty row with one', () => {
		const none = show(card('east-r2-2'), true);
		expect(none.container.querySelector('.series')?.classList.contains('none')).toBe(true);
		none.unmount();
		const one = show(card('east-r2-1'), true);
		expect(one.container.querySelector('.series')?.classList.contains('one')).toBe(true);
	});
});

describe('SeriesNode champion', () => {
	it('carries the champion class for a complete Finals only', () => {
		const done = show(card('finals', 'playoffs-complete.json'), true);
		expect(done.container.querySelector('.series')?.classList.contains('champion')).toBe(true);
		done.unmount();
		const open = show(card('finals'), true);
		expect(open.container.querySelector('.series')?.classList.contains('champion')).toBe(false);
	});
});

describe('SeriesNode interaction', () => {
	it('is a button named from the series, and a click opens it with its id', async () => {
		const onOpen = vi.fn();
		show(card('east-r1-1'), false, onOpen);
		const button = screen.getByRole('button', { name: 'East · Round 1 · QXA · QXH' });
		await fireEvent.click(button);
		expect(onOpen).toHaveBeenCalledWith('east-r1-1', button);
	});

	it('reports focus and blur, true only for a focus-visible focus', () => {
		const onFocusChange = vi.fn();
		show(card('east-r1-1'), false, vi.fn(), onFocusChange);
		const button = screen.getByRole('button');
		vi.spyOn(button, 'matches').mockImplementation((selector) => selector === ':focus-visible');
		button.focus();
		expect(onFocusChange).toHaveBeenLastCalledWith(true);
		button.blur();
		expect(onFocusChange).toHaveBeenLastCalledWith(false);
	});

	it('reports false when the focus is not focus-visible', () => {
		const onFocusChange = vi.fn();
		show(card('east-r1-1'), false, vi.fn(), onFocusChange);
		const button = screen.getByRole('button');
		vi.spyOn(button, 'matches').mockReturnValue(false);
		button.focus();
		expect(onFocusChange).toHaveBeenLastCalledWith(false);
	});
});

describe('SeriesNode seed', () => {
	it('draws no seed number for an empty seed', () => {
		const series = card('east-r1-2');
		series.top = { ...series.top, seed: '' };
		const { container } = show(series);
		expect(container.querySelector('.row .seed')?.textContent).toBe('');
	});
});
