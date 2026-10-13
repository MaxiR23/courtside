// web/tests/lib/components/GroupCard.test.ts
//
// Tests for the GroupCard component.
//
// Tested:
// - The title and the meta; the draw list with no numbers when there are no rows
// - The table when there are rows; More columns calls its callback and reflects aria-pressed
//
// What is covered:
// - A group with rows and a drawn group without, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/GroupCard.test.ts
//
// SEE: web/src/lib/components/GroupCard.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { CupFeed } from '../../../src/lib/contract/cup';
import { toCupView } from '../../../src/lib/feed/cup-props';
import { preferLanguages } from '../../prefer-languages';
import GroupCard from '../../../src/lib/components/GroupCard.svelte';
const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;

const feed = (): CupFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'cup.json'), 'utf8')
	) as CupFeed;
const view = (source: CupFeed = feed()) => toCupView(source);

afterEach(() => {
	vi.restoreAllMocks();
});

const show = (index: number, extra: Record<string, unknown> = {}) =>
	render(GroupCard, {
		props: {
			group: view().groups[index]!,
			wide: false,
			onToggleColumns: () => {},
			layout: 'desktop' as const,
			teamHref,
			...extra
		}
	});

describe('GroupCard', () => {
	it('shows the title and the meta', () => {
		show(0);
		expect(screen.getByRole('heading', { level: 3, name: 'East Group A' })).toBeTruthy();
		expect(screen.getByText('6 of 10 games')).toBeTruthy();
	});

	it('shows the table and the More columns button when there are rows', () => {
		const { container } = show(0);
		expect(screen.getByRole('table')).toBeTruthy();
		expect(container.querySelector('.draw')).toBeNull();
		expect(screen.getByRole('button', { name: 'More columns' })).toBeTruthy();
	});

	it('shows the draw list with the city and name and no numbers when there are no rows', () => {
		const { container } = show(2);
		expect(screen.queryByRole('table')).toBeNull();
		expect(screen.queryByRole('button', { name: 'More columns' })).toBeNull();
		const items = [...container.querySelectorAll('.draw-team')].map((li) =>
			li.textContent?.replace(/\s+/g, ' ').trim()
		);
		expect(items).toHaveLength(5);
		expect(items[0]).toBe('SXA Fairmont Comets');
		expect(container.textContent).not.toMatch(/\d+-\d+/);
		expect(screen.getByText('5 teams')).toBeTruthy();
	});

	it('calls its callback on More columns and reflects aria-pressed', async () => {
		const onToggleColumns = vi.fn();
		const first = show(0, { onToggleColumns });
		const button = screen.getByRole('button', { name: 'More columns' });
		expect(button.getAttribute('aria-pressed')).toBe('false');
		await fireEvent.click(button);
		expect(onToggleColumns).toHaveBeenCalledTimes(1);
		first.unmount();
		show(0, { wide: true });
		expect(screen.getByRole('button', { name: 'More columns' }).getAttribute('aria-pressed')).toBe(
			'true'
		);
		expect(screen.getAllByRole('columnheader')).toHaveLength(11);
	});

	it('shows Spanish copy', () => {
		preferLanguages(['es-ES']);
		show(0);
		expect(screen.getByRole('heading', { level: 3, name: 'Grupo A del Este' })).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Más columnas' })).toBeTruthy();
	});
});
