// web/tests/lib/components/GroupTable.test.ts
//
// Tests for the GroupTable component.
//
// Tested:
// - The seven headers; the five extra headers and cells only when wide
// - The tags y, x and e from the rows; the eliminated row has the eliminated class
// - A — in the cells of a row with nothing; team links to teamHref
// - Spanish headers
//
// What is covered:
// - Both column sets, every tag and a row of nulls, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/GroupTable.test.ts
//
// SEE: web/src/lib/components/GroupTable.svelte
import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { CupFeed } from '../../../src/lib/contract/cup';
import { toCupView } from '../../../src/lib/feed/cup-props';
import { preferLanguages } from '../../prefer-languages';
import GroupTable from '../../../src/lib/components/GroupTable.svelte';

const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;

const feed = (): CupFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'cup.json'), 'utf8')
	) as CupFeed;
const view = (source: CupFeed = feed()) => toCupView(source);

afterEach(() => {
	vi.restoreAllMocks();
});

const rows = () => view().groups[0]!.rows;
const show = (wide = false) =>
	render(GroupTable, { props: { rows: rows(), wide, layout: 'desktop' as const, teamHref } });
const headers = () => screen.getAllByRole('columnheader').map((h) => h.textContent?.trim());

describe('GroupTable', () => {
	it('shows the seven headers', () => {
		show();
		expect(headers()).toEqual(['Pos Team', 'W-L', 'GB', 'Diff/G', 'Diff', 'Strk']);
	});

	it('shows the five extra headers and cells only when wide', () => {
		const narrow = show();
		expect(
			narrow.container.querySelectorAll('.row.body')[0]?.querySelectorAll('.cell')
		).toHaveLength(6);
		narrow.unmount();
		const wide = show(true);
		expect(headers().slice(6)).toEqual(['PF', 'PA', 'Home', 'Away', 'OT']);
		const cells = [
			...(wide.container.querySelectorAll('.row.body')[0]?.querySelectorAll('.cell') ?? [])
		];
		expect(cells.map((c) => c.textContent?.trim()).slice(6)).toEqual([
			'470',
			'420',
			'2-0',
			'2-0',
			'0-0'
		]);
	});

	it('shows the tags y, x and e and none for a row without one', () => {
		const { container } = show();
		const tags = [...container.querySelectorAll('.row.body')].map(
			(row) => row.querySelector('.clinch-tag')?.textContent ?? null
		);
		expect(tags).toEqual(['y', 'x', null, 'e', null]);
	});

	it('marks the eliminated row', () => {
		const { container } = show();
		const flags = [...container.querySelectorAll('.row.body')].map((r) =>
			r.classList.contains('eliminated')
		);
		expect(flags).toEqual([false, false, false, true, false]);
	});

	it('shows a — in the cells of a row with no values', () => {
		const { container } = show(true);
		const last = container.querySelectorAll('.row.body')[4]!;
		const cells = [...last.querySelectorAll('.cell')].map((c) => c.textContent?.trim());
		expect(cells.slice(1)).toEqual(['0-0', '—', '—', '—', '—', '—', '—', '—', '—', '—']);
	});

	it('links each team name to its team page', () => {
		render(GroupTable, { props: { rows: rows(), wide: false, layout: 'desktop', teamHref } });
		expect(screen.getByRole('link', { name: 'Herons' }).getAttribute('href')).toBe('/team/qxa');
	});

	it('shows Spanish headers', () => {
		preferLanguages(['es-ES']);
		show();
		expect(headers()).toEqual(['Pos Equipo', 'G-P', 'DP', 'Dif/P', 'Dif', 'Racha']);
	});
});
