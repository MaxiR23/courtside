// web/tests/lib/components/WildCardTable.test.ts
//
// Tests for the WildCardTable component.
//
// Tested:
// - The title, the six headers and the rows in order
// - The wild card line right after rank 1 and nowhere else
// - The wild card line is a solid divider rule, with no dash pattern (read from the source)
// - The x tag when present and none otherwise; Spanish copy
//
// What is covered:
// - A table with rows and an empty table, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/WildCardTable.test.ts
//
// SEE: web/src/lib/components/WildCardTable.svelte
import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { CupFeed } from '../../../src/lib/contract/cup';
import { toCupView } from '../../../src/lib/feed/cup-props';
import { preferLanguages } from '../../prefer-languages';
import WildCardTable from '../../../src/lib/components/WildCardTable.svelte';
const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;

const feed = (): CupFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'cup.json'), 'utf8')
	) as CupFeed;
const view = (source: CupFeed = feed()) => toCupView(source);

afterEach(() => {
	vi.restoreAllMocks();
});

const show = (index = 0) =>
	render(WildCardTable, {
		props: { table: view().wildCard[index]!, layout: 'desktop' as const, teamHref }
	});

describe('WildCardTable', () => {
	it('shows the title and the headers', () => {
		show();
		expect(screen.getByRole('heading', { level: 3, name: 'Eastern Conference' })).toBeTruthy();
		expect(screen.getAllByRole('columnheader').map((h) => h.textContent?.trim())).toEqual([
			'Rank Team',
			'Group',
			'W-L',
			'Diff',
			'PF'
		]);
	});

	it('shows the rows in order with their values', () => {
		const { container } = show();
		const rows = [...container.querySelectorAll('.row.body')];
		expect(rows).toHaveLength(3);
		const first = [...rows[0]!.querySelectorAll('.cell')].map((c) => c.textContent?.trim());
		expect(first.slice(1)).toEqual(['East Group A', '3-1', '+16', '440']);
		expect(rows[2]?.textContent).toContain('—');
	});

	it('puts the wild card line right after rank 1 and nowhere else', () => {
		const { container } = show();
		const order = [
			...container.querySelectorAll('.table > div:not(.contents), .table > .contents > div')
		].map((el) =>
			el.classList.contains('line') ? 'line' : el.classList.contains('head') ? 'head' : 'row'
		);
		expect(order).toEqual(['head', 'row', 'line', 'row', 'row']);
		expect(screen.getAllByText('Wild card line')).toHaveLength(1);
	});

	it('shows the x tag only on the tagged row', () => {
		const { container } = show();
		const tags = [...container.querySelectorAll('.row.body')].map(
			(r) => r.querySelector('.clinch-tag')?.textContent ?? null
		);
		expect(tags).toEqual(['x', null, null]);
	});

	it('draws only the header row for an empty table', () => {
		const { container } = show(1);
		expect(container.querySelectorAll('.row.body')).toHaveLength(0);
		expect(container.querySelector('.line')).toBeNull();
	});

	it('shows Spanish copy', () => {
		preferLanguages(['es-ES']);
		show();
		expect(screen.getByRole('heading', { level: 3, name: 'Conferencia Este' })).toBeTruthy();
		expect(screen.getByText('Línea del comodín')).toBeTruthy();
	});

	it('draws the wild card line as a solid divider rule', () => {
		const source = readFileSync(
			join(__dirname, '..', '..', '..', 'src', 'lib', 'components', 'WildCardTable.svelte'),
			'utf8'
		);
		expect(source).toContain('border-top: var(--hairline) solid var(--color-divider)');
		expect(source).not.toMatch(/stroke-dasharray|dashed|dotted|<line\b/);
		const { container } = show();
		expect(container.querySelector('.line .rule')?.getAttribute('aria-hidden')).toBe('true');
		expect(screen.getByText('Wild card line')).toBeTruthy();
	});
});
