// web/tests/lib/components/SeriesNode.test.ts
//
// Tests for the SeriesNode component.
//
// Tested:
// - A decided series: seeds, codes and wins; 4 segments per row, one filled per win in the side's resolved color
// - The loser row is muted; a side with an empty seed draws no seed number
// - The Finals card, the tree (mobile) card and the selected card carry their classes; the selected card is pressed
// - An undecided series is not a button: the slot label and the note, each with its full text as title (ADR 0054); a one-sided series has one team row and one dashed row
// - A click calls onTap with the id and the button; the card is a native button named from the series
// - The team logos: before the code of a decided side, none for an undecided one
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
import { describe, expect, it, vi } from 'vitest';

import SeriesNode from '../../../src/lib/components/SeriesNode.svelte';
import type { PlayoffsFeed } from '../../../src/lib/contract/playoffs';
import { toPlayoffsView } from '../../../src/lib/feed/playoffs-props';
import type { SeriesCardView } from '../../../src/lib/playoffs/types';
import type { RowLayout } from '../../../src/lib/schedule/types';

const feed = (name: string) =>
	JSON.parse(readFileSync(join(__dirname, '..', 'feed', 'fixtures', name), 'utf8')) as PlayoffsFeed;

const card = (id: string, name = 'playoffs-bracket.json'): SeriesCardView =>
	toPlayoffsView(feed(name), null).bracket.series.find((series) => series.id === id)!;

const show = (
	series: SeriesCardView,
	options: { layout?: RowLayout; selected?: boolean; onTap?: () => void } = {}
) =>
	render(SeriesNode, {
		props: {
			series,
			layout: options.layout ?? 'desktop',
			selected: options.selected ?? false,
			onTap: options.onTap ?? vi.fn()
		}
	});

const filled = (row: Element) =>
	[...row.querySelectorAll('.segment')].map((segment) => segment.classList.contains('filled'));

describe('SeriesNode decided', () => {
	it('shows seeds, codes and wins of both sides', () => {
		const { container } = show(card('east-r1-2'));
		const rows = [...container.querySelectorAll('.team')];
		expect(rows).toHaveLength(2);
		expect(rows.map((row) => row.querySelector('.seed')?.textContent)).toEqual(['4', '5']);
		expect(rows.map((row) => row.querySelector('.code')?.textContent)).toEqual(['QXD', 'QXE']);
		expect(rows.map((row) => row.querySelector('.wins')?.textContent)).toEqual(['2', '2']);
	});

	it('draws 4 segments per row with one filled per win', () => {
		const { container } = show(card('east-r1-1'));
		const rows = [...container.querySelectorAll('.team')];
		expect(filled(rows[0])).toEqual([true, true, true, true]);
		expect(filled(rows[1])).toEqual([true, false, false, false]);
	});

	it('draws no filled segment for missing wins', () => {
		const { container } = show(card('east-r1-4'));
		const rows = [...container.querySelectorAll('.team')];
		expect(container.querySelector('.wins')?.textContent).toBe('—');
		expect(rows.map(filled)).toEqual([
			[false, false, false, false],
			[false, false, false, false]
		]);
	});

	it("fills the segments in the side's resolved color, else the neutral accent", () => {
		const series = card('east-r1-2');
		series.top = { ...series.top, accent: '#112233' };
		const { container } = show(series);
		const segments = [...container.querySelectorAll<HTMLElement>('.segments')];
		expect(segments[0].style.getPropertyValue('--side-accent')).toBe('#112233');
		expect(segments[1].style.getPropertyValue('--side-accent')).toBe(
			'var(--identity-neutral-accent)'
		);
	});

	it('mutes the loser row only', () => {
		const { container } = show(card('east-r1-1'));
		const rows = [...container.querySelectorAll('.team')];
		expect(rows.map((row) => row.classList.contains('loser'))).toEqual([false, true]);
	});

	it('draws no seed number for an empty seed', () => {
		const series = card('east-r1-2');
		series.top = { ...series.top, seed: '' };
		const { container } = show(series);
		expect(container.querySelector('.team .seed')?.textContent).toBe('');
	});
});

describe('SeriesNode classes', () => {
	it('marks the Finals card', () => {
		const finals = show(card('finals', 'playoffs-complete.json'));
		expect(finals.container.querySelector('.series')?.classList.contains('finals')).toBe(true);
		finals.unmount();
		const other = show(card('east-r1-1'));
		expect(other.container.querySelector('.series')?.classList.contains('finals')).toBe(false);
	});

	it('marks the tree card on the phone layout', () => {
		const tree = show(card('east-r1-1'), { layout: 'mobile' });
		expect(tree.container.querySelector('.series')?.classList.contains('tree')).toBe(true);
		tree.unmount();
		const map = show(card('east-r1-1'));
		expect(map.container.querySelector('.series')?.classList.contains('tree')).toBe(false);
	});

	it('drops the seed from the tree card and keeps code and wins', () => {
		const tree = show(card('east-r1-2'), { layout: 'mobile' });
		expect(tree.container.querySelector('.seed')).toBeNull();
		expect([...tree.container.querySelectorAll('.code')].map((code) => code.textContent)).toEqual([
			'QXD',
			'QXE'
		]);
		expect([...tree.container.querySelectorAll('.wins')].map((wins) => wins.textContent)).toEqual([
			'2',
			'2'
		]);
	});

	it('presses and marks the selected card', () => {
		const picked = show(card('east-r1-1'), { selected: true });
		const button = screen.getByRole('button');
		expect(button.getAttribute('aria-pressed')).toBe('true');
		expect(button.classList.contains('selected')).toBe(true);
		picked.unmount();
		show(card('east-r1-1'));
		expect(screen.getByRole('button').getAttribute('aria-pressed')).toBe('false');
	});
});

describe('SeriesNode undecided', () => {
	it('is not a button, and shows the slot label and the note of each side', () => {
		const { container } = show(card('east-r2-2'));
		expect(screen.queryByRole('button')).toBeNull();
		const rows = [...container.querySelectorAll('.row')];
		expect(rows.every((row) => row.classList.contains('undecided'))).toBe(true);
		expect(rows[0].querySelector('.slot-label')?.textContent).toBe('Winner of East R1 3');
		expect(rows[0].querySelector('.note')?.textContent).toBe('To be decided');
		expect(container.querySelector('.series')?.classList.contains('none')).toBe(true);
	});

	it('carries the full text of a slot label and a note as title', () => {
		const { container } = show(card('east-r2-2'));
		const row = container.querySelector('.row') as HTMLElement;
		expect(row.querySelector('.slot-label')?.getAttribute('title')).toBe('Winner of East R1 3');
		expect(row.querySelector('.note')?.getAttribute('title')).toBe('To be decided');
	});

	it('shows one team row and one dashed row for a one-sided series', () => {
		const { container } = show(card('east-r2-1'));
		expect(container.querySelectorAll('.team')).toHaveLength(1);
		const undecided = container.querySelectorAll('.row.undecided');
		expect(undecided).toHaveLength(1);
		expect(undecided[0].querySelector('.slot-label')?.textContent).toBe('Winner of East R1 2');
		expect(container.querySelector('.series')?.classList.contains('one')).toBe(true);
	});
});

describe('SeriesNode interaction', () => {
	it('is a button named from the series, and a click taps it with its id and button', async () => {
		const onTap = vi.fn();
		show(card('east-r1-1'), { onTap });
		const button = screen.getByRole('button', { name: 'East · Round 1 · QXA · QXH' });
		await fireEvent.click(button);
		expect(onTap).toHaveBeenCalledWith('east-r1-1', button);
	});
});

describe('SeriesNode logos', () => {
	it('draws the logo before the code of a decided side, and none for an undecided one', () => {
		const series = card('east-r1-2');
		series.top.team!.logo = {
			light: 'https://example.com/x-light.svg',
			dark: 'https://example.com/x-dark.svg'
		};
		const { container } = show(series);
		const marks = [...container.querySelectorAll('.logo .team-monogram')];
		expect(marks[0]!.querySelector('img')?.getAttribute('src')).toBe(
			'https://example.com/x-dark.svg'
		);
		expect(marks[1]!.querySelector('img')).toBeNull();
		const undecided = show(card('east-r2-2'));
		expect(undecided.container.querySelectorAll('.team-monogram')).toHaveLength(0);
	});
});
