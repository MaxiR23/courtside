// web/tests/lib/components/NamesTimeline.test.ts
//
// Tests for the NamesTimeline component.
//
// Tested:
// - Four runs in order with the years, the name and the code
// - The current run is not a link and has aria-current
// - Each past run links to seasonHref of its last season
// - The mobile layout has the scroll class; the desktop layout does not
// - The title in English and in Spanish
// - The runs take their sizes from tokens in the source
//
// What is covered:
// - Structure and classes; jsdom does no layout, so scroll-snap and sizes are asserted in the source
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/NamesTimeline.test.ts
//
// SEE: web/src/lib/components/NamesTimeline.svelte
import { render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import NamesTimeline from '../../../src/lib/components/NamesTimeline.svelte';
import type { NameRunView } from '../../../src/lib/team/types';
import { preferLanguages } from '../../prefer-languages';

const runs: NameRunView[] = [
	{ key: '1994', years: '1994–2001', name: 'Lakeview Pilots', code: 'LKV', season: 2001 },
	{ key: '2002', years: '2002–2008', name: 'Harbor City Mariners', code: 'HCM', season: 2008 },
	{ key: '2009', years: '2009–2014', name: 'Harbor City Harbors', code: 'HCH', season: 2014 },
	{ key: '2015', years: '2015–', name: 'Harbor City Skippers', code: 'OKC', season: null }
];

const seasonHref = (season: number) => `/team/okc?season=${season}`;

const show = (layout: 'desktop' | 'mobile' = 'desktop') =>
	render(NamesTimeline, { props: { runs, layout, seasonHref } });

afterEach(() => {
	vi.restoreAllMocks();
});

describe('NamesTimeline', () => {
	it('draws the four runs in order with years, name and code', () => {
		const { container } = show();
		const items = [...container.querySelectorAll('li')];
		expect(items.map((item) => item.textContent?.replace(/\s+/g, ' ').trim())).toEqual([
			'1994–2001 Lakeview Pilots LKV',
			'2002–2008 Harbor City Mariners HCM',
			'2009–2014 Harbor City Harbors HCH',
			'2015– Harbor City Skippers OKC'
		]);
	});

	it('draws the current run as a marked element, not a link', () => {
		const { container } = show();
		const current = container.querySelector('[aria-current="true"]');
		expect(current?.tagName).toBe('DIV');
		expect(current?.textContent).toContain('Harbor City Skippers');
		expect(container.querySelectorAll('a')).toHaveLength(3);
	});

	it('links each past run to the last season of the run', () => {
		const { container } = show();
		expect([...container.querySelectorAll('a')].map((a) => a.getAttribute('href'))).toEqual([
			'/team/okc?season=2001',
			'/team/okc?season=2008',
			'/team/okc?season=2014'
		]);
	});

	it('scrolls on mobile only', () => {
		const mobile = show('mobile');
		expect(mobile.container.querySelector('ol')?.classList.contains('scroll')).toBe(true);
		mobile.unmount();
		const desktop = show('desktop');
		expect(desktop.container.querySelector('ol')?.classList.contains('scroll')).toBe(false);
	});

	it('is titled Names, and Nombres in Spanish', () => {
		const { unmount } = show();
		expect(screen.getByText('Names')).toBeTruthy();
		unmount();
		preferLanguages(['es']);
		show();
		expect(screen.getByText('Nombres')).toBeTruthy();
	});

	it('takes its scroll snap, hit target and sizes from the source', () => {
		const source = readFileSync(
			join(__dirname, '..', '..', '..', 'src', 'lib', 'components', 'NamesTimeline.svelte'),
			'utf8'
		);
		expect(source).toContain('scroll-snap-type: x mandatory');
		expect(source).toContain('scroll-snap-align: start');
		expect(source).toContain('min-height: var(--hit-target-size)');
		expect(source).toContain('font-size: var(--past-names-year-size)');
		expect(source).toContain('font-size: var(--past-names-name-size)');
	});
});
