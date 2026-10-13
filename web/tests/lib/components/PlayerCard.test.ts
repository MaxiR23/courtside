// web/tests/lib/components/PlayerCard.test.ts
//
// Tests for the PlayerCard component.
//
// Tested:
// - Every field: name, team, number and position, the injury tag, PTS, REB, AST, height, weight, age, hometown, college and experience
// - Initials when there is no photo; a — for a missing value
// - Previous is disabled on the first player and Next on the last, and each calls onIndex
// - Stepping to the first player leaves the focus on Next, and to the last leaves it on Previous
// - Close calls onClose and has the focus on open
// - The link to the player page; the mobile class
// - Spanish copy
//
// What is covered:
// - Each state the card shows, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PlayerCard.test.ts
//
// SEE: web/src/lib/components/PlayerCard.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { tick } from 'svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import PlayerCard from '../../../src/lib/components/PlayerCard.svelte';
import type { CupMatchupFeed } from '../../../src/lib/contract/cup-matchup';
import { toMatchupView } from '../../../src/lib/feed/cup-matchup-props';
import { preferLanguages } from '../../prefer-languages';

const playerHref = (id: string) => `/player/${id}` as ResolvedPathname;

const players = () =>
	toMatchupView(
		JSON.parse(
			readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'cup-matchup.json'), 'utf8')
		) as CupMatchupFeed
	).sides[0].roster.map((row) => row.card);

const show = (index = 0, extra: Record<string, unknown> = {}) =>
	render(PlayerCard, {
		props: {
			players: players(),
			index,
			layout: 'desktop',
			playerHref,
			onIndex: () => {},
			onClose: () => {},
			...extra
		}
	});

afterEach(() => {
	vi.restoreAllMocks();
});

describe('PlayerCard', () => {
	it('is a dialog named for the player', () => {
		show();
		expect(screen.getByRole('dialog', { name: 'Ari Vance' })).toBeTruthy();
	});

	it('shows every field of the card', () => {
		const { container } = show();
		const text = container.textContent ?? '';
		for (const expected of [
			'Ari Vance',
			'Herons',
			'#2 · G',
			'27.4',
			'5.1',
			'7.9',
			'6-4',
			'200 lb',
			'26',
			'Alderton, OH',
			'Northfield',
			'4'
		]) {
			expect(text).toContain(expected);
		}
		for (const label of ['PTS', 'REB', 'AST', 'Height', 'Weight', 'Age', 'Hometown', 'College']) {
			expect(text).toContain(label);
		}
		expect(screen.getByRole('img', { name: 'Ari Vance' }).getAttribute('src')).toBe(
			'https://example.com/photos/p101.png'
		);
		expect(container.querySelector('.injury')).toBeNull();
	});

	it('shows the initials when there is no photo, the injury tag, and a — for a missing value', () => {
		const { container } = show(2);
		expect(screen.getByRole('img', { name: 'Cal Duran' }).textContent).toBe('CD');
		expect(screen.getByText('Out')).toBeTruthy();
		show(3);
		expect(screen.getAllByText('—').length).toBeGreaterThan(0);
		expect(container).toBeTruthy();
	});

	it('links to the player page', () => {
		show(1);
		expect(screen.getByRole('link', { name: 'Player page' }).getAttribute('href')).toBe(
			'/player/p102'
		);
	});

	it('disables Previous on the first player and Next on the last', () => {
		show(0);
		expect(
			(screen.getByRole('button', { name: 'Previous player' }) as HTMLButtonElement).disabled
		).toBe(true);
		expect(
			(screen.getByRole('button', { name: 'Next player' }) as HTMLButtonElement).disabled
		).toBe(false);
		show(4);
		const next = screen.getAllByRole('button', { name: 'Next player' })[1] as HTMLButtonElement;
		expect(next.disabled).toBe(true);
	});

	it('steps to the previous and next player', async () => {
		const onIndex = vi.fn();
		show(2, { onIndex });
		await fireEvent.click(screen.getByRole('button', { name: 'Previous player' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Next player' }));
		expect(onIndex.mock.calls).toEqual([[1], [3]]);
	});

	it('keeps the focus in the card when a step button becomes disabled', async () => {
		const view = show(1);
		const props = { players: players(), layout: 'desktop' as const, playerHref, onClose: () => {} };
		const feed = async (index: number) => {
			await view.rerender({ ...props, index, onIndex: feed });
		};
		await feed(1);
		await fireEvent.click(screen.getByRole('button', { name: 'Previous player' }));
		await tick();
		expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Next player' }));

		await feed(players().length - 2);
		await fireEvent.click(screen.getByRole('button', { name: 'Next player' }));
		await tick();
		expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Previous player' }));
	});

	it('closes from the Close button, which has the focus on open', async () => {
		const onClose = vi.fn();
		show(0, { onClose });
		const close = screen.getByRole('button', { name: 'Close' });
		expect(document.activeElement).toBe(close);
		await fireEvent.click(close);
		expect(onClose).toHaveBeenCalledTimes(1);
	});

	it('takes the mobile class on a phone', () => {
		const { container } = show(0, { layout: 'mobile' });
		expect(container.querySelector('.card.mobile')).not.toBeNull();
	});

	it('draws nothing for an index past the list', () => {
		const { container } = show(9);
		expect(container.querySelector('.card')).toBeNull();
	});

	it('writes the labels in Spanish', () => {
		preferLanguages(['es']);
		show(0);
		expect(screen.getByText('Ciudad natal')).toBeTruthy();
		expect(screen.getByText('Experiencia')).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Página del jugador' })).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Cerrar' })).toBeTruthy();
	});
});
