// web/tests/lib/components/PageHeader.test.ts
//
// Tests for the PageHeader component.
//
// Tested:
// - Renders the nav row with the page's props: the current link, the mobile class, the home extras
// - Wraps the first line in .first-line inside the lead column, the body after it
// - Draws the desktop select (not full) in the side column before the aside, and calls onChange
// - On mobile draws the select full width as the last row, after the wide rows or the band's rows
// - With columnsMin and a side column, takes the desktop select out of the side column so it stays on the first line when the columns wrap
// - Draws no select without the prop, and no side column with neither select nor aside
// - Draws the grid layer with the given size, none with grid null, and inside the band with a band
// - Draws the divider by default and none without it
// - Sets aria-busy only when busy
// - Renders the backdrop before the nav bar and marks the home
// - Sets the side padding, gaps, flex values and sticky nav values as custom properties, and none unless given
// - Raises the nav bar only with a sticky nav, and clips the sides only with clip
// - Sets the nav top, the first-line offset, the side gap and the content width in its rules
//
// What is covered:
// - Every state and option of the component
// - Pixels are not measured: jsdom has no layout, so the rules are read from the source
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PageHeader.test.ts
//
// SEE: web/src/lib/components/PageHeader.svelte
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { describe, expect, it, vi } from 'vitest';

import PageHeader from '../../../src/lib/components/PageHeader.svelte';

const HOME = '/' as ResolvedPathname;
const STANDINGS = '/standings' as ResolvedPathname;
const nav = { page: 'standings' as const, gamesHref: HOME, standingsHref: STANDINGS };
const seasonSelect = {
	seasons: [
		{ season: 2027, seasonLabel: '2026-27' },
		{ season: 2026, seasonLabel: '2025-26' }
	],
	value: 2027,
	onChange: () => {}
};

const snippet = (html: string) => createRawSnippet(() => ({ render: () => html }));

function draw(extra: Record<string, unknown> = {}) {
	return render(PageHeader, { props: { nav, layout: 'desktop' as const, ...extra } });
}

function ruleOf(selector: string): Map<string, string> {
	const source = readFileSync(
		join(import.meta.dirname, '../../../src/lib/components/PageHeader.svelte'),
		'utf8'
	);
	const style = (source.match(/<style[^>]*>([\s\S]*?)<\/style>/)?.[1] ?? '').replace(
		/\/\*[\s\S]*?\*\//g,
		''
	);
	const declarations = new Map<string, string>();
	for (const match of style.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
		const selectors = (match[1] ?? '').split(',').map((part) => part.trim());
		if (!selectors.includes(selector)) continue;
		for (const part of (match[2] ?? '').split(';')) {
			const index = part.indexOf(':');
			if (index > 0) declarations.set(part.slice(0, index).trim(), part.slice(index + 1).trim());
		}
	}
	return declarations;
}

describe('PageHeader nav', () => {
	it('renders the nav row and marks the current page link', () => {
		const { container } = draw();
		expect(container.querySelector('header nav.nav-row')).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Standings' }).getAttribute('aria-current')).toBe(
			'page'
		);
	});

	it('gives the nav row the mobile layout', () => {
		const { container } = draw({ layout: 'mobile' });
		expect(container.querySelector('header.mobile nav.nav-row.mobile')).toBeTruthy();
	});

	it('shows the home extras only with nav.home, and marks the home header', () => {
		const home = {
			today: new Date(2027, 1, 14),
			spoilerFree: false,
			onSpoilerFreeToggle: () => {}
		};
		const plain = draw();
		expect(plain.container.querySelector('header.home')).toBeNull();
		expect(screen.queryByText('Spoiler-free')).toBeNull();
		plain.unmount();
		const { container } = draw({ nav: { ...nav, page: 'home', home } });
		expect(container.querySelector('header.home')).toBeTruthy();
		expect(screen.getByText('Spoiler-free')).toBeTruthy();
	});
});

describe('PageHeader rows', () => {
	it('wraps the first line in .first-line inside the lead column, with the body after it', () => {
		const { container } = draw({
			first: snippet('<h1>Title</h1>'),
			body: snippet('<p>Body</p>')
		});
		const lead = container.querySelector('.lead');
		const first = lead?.querySelector('.first-line');
		expect(first?.querySelector('h1')?.textContent).toBe('Title');
		const body = screen.getByText('Body');
		expect(lead?.contains(body)).toBe(true);
		expect(first?.contains(body)).toBe(false);
		expect(first?.compareDocumentPosition(body)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
	});

	it('renders no .first-line without a first snippet', () => {
		const { container } = draw({ body: snippet('<p>Body</p>') });
		expect(container.querySelector('.first-line')).toBeNull();
	});

	it('renders the wide rows after the columns', () => {
		const { container } = draw({
			first: snippet('<h1>Title</h1>'),
			wide: snippet('<p>Wide</p>')
		});
		const main = container.querySelector('.main');
		const wide = screen.getByText('Wide');
		expect(main?.contains(wide)).toBe(false);
		expect(main?.compareDocumentPosition(wide)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
	});

	it('renders the backdrop before the nav bar', () => {
		const { container } = draw({ backdrop: snippet('<div class="backdrop"></div>') });
		const backdrop = container.querySelector('.backdrop');
		const bar = container.querySelector('.nav-bar');
		expect(backdrop?.compareDocumentPosition(bar as Node)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
	});
});

describe('PageHeader season select', () => {
	it('draws the select in the side column on desktop, before the aside, not full', () => {
		const { container } = draw({ seasonSelect, aside: snippet('<p>Aside</p>') });
		const side = container.querySelector('.side');
		const select = side?.querySelector('.season-select select');
		expect(select).toBeTruthy();
		expect(select?.classList.contains('full')).toBe(false);
		expect(container.querySelectorAll('select')).toHaveLength(1);
		expect(side?.querySelector('.aside')?.textContent).toBe('Aside');
		const selectBox = side?.querySelector('.season-select') as Node;
		const asideBox = side?.querySelector('.aside') as Node;
		expect(selectBox.compareDocumentPosition(asideBox)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
	});

	it('calls onChange with the end year', async () => {
		const onChange = vi.fn();
		draw({ seasonSelect: { ...seasonSelect, onChange } });
		await fireEvent.change(screen.getByRole('combobox', { name: 'Season' }), {
			target: { value: '2026' }
		});
		expect(onChange).toHaveBeenCalledWith(2026);
	});

	it('draws the select full width as the last row on mobile, after the wide rows, and none in the side column', () => {
		const { container } = draw({
			layout: 'mobile',
			seasonSelect,
			wide: snippet('<p>Wide</p>')
		});
		expect(container.querySelector('.side')).toBeNull();
		const row = container.querySelector('.season-row');
		expect(row?.querySelector('select.full')).toBeTruthy();
		expect(container.querySelectorAll('select')).toHaveLength(1);
		expect(screen.getByText('Wide').compareDocumentPosition(row as Node)).toBe(
			Node.DOCUMENT_POSITION_FOLLOWING
		);
	});

	it('takes the select out of the side column with columnsMin and an aside, before it wraps', () => {
		const columnsMin = 'calc(var(--detail-column-min) * 2)';
		const { container } = draw({ seasonSelect, columnsMin, aside: snippet('<p>Aside</p>') });
		const main = container.querySelector('.main');
		expect(main?.classList.contains('float-select')).toBe(true);
		expect(container.querySelector('.side select')).toBeNull();
		expect(main?.querySelector(':scope > .season-select.floating select')).toBeTruthy();
		expect(container.querySelectorAll('select')).toHaveLength(1);
		expect(ruleOf('.main').get('position')).toBe('relative');
		const floating = ruleOf('.floating');
		expect(floating.get('position')).toBe('absolute');
		expect(floating.get('top')).toBe('0');
		expect(floating.get('right')).toBe('0');
		const pad = ruleOf('.float-select .side').get('padding-top') ?? '';
		expect(pad).toContain('var(--page-header-columns-min)');
		expect(pad).toContain('var(--past-select-height) + var(--game-list-gap)');
	});

	it('floats the select with a side flex and no aside, and keeps it in the column without columnsMin or a side', () => {
		const flexed = draw({ seasonSelect, columnsMin: '880px', sideFlex: '1 1 440px' });
		expect(flexed.container.querySelector('.season-select.floating')).toBeTruthy();
		flexed.unmount();
		const plain = draw({ seasonSelect, aside: snippet('<p>Aside</p>') });
		expect(plain.container.querySelector('.side .season-select')).toBeTruthy();
		expect(plain.container.querySelector('.floating')).toBeNull();
		plain.unmount();
		const bare = draw({ seasonSelect, columnsMin: '880px' });
		expect(bare.container.querySelector('.side .season-select')).toBeTruthy();
		bare.unmount();
		const mobile = draw({
			layout: 'mobile',
			seasonSelect,
			columnsMin: '880px',
			sideFlex: '1 1 440px'
		});
		expect(mobile.container.querySelector('.floating')).toBeNull();
	});

	it('draws no select without the prop', () => {
		const { container } = draw();
		expect(container.querySelector('select')).toBeNull();
		const mobile = draw({ layout: 'mobile' });
		expect(mobile.container.querySelector('select')).toBeNull();
	});

	it('draws no side column with neither a select nor an aside', () => {
		const { container } = draw({ first: snippet('<h1>Title</h1>') });
		expect(container.querySelector('.side')).toBeNull();
		const withAside = draw({ aside: snippet('<p>Aside</p>') });
		expect(withAside.container.querySelector('.side .aside')).toBeTruthy();
		expect(withAside.container.querySelector('.season-select')).toBeNull();
	});
});

describe('PageHeader grid, band and divider', () => {
	it('draws the grid layer with the given size', () => {
		const { container } = draw({ grid: 'var(--cup-header-grid-size)' });
		const header = container.querySelector<HTMLElement>('header');
		expect(header?.querySelector(':scope > .grid-bg')).toBeTruthy();
		expect(header?.style.getPropertyValue('--page-header-grid-size')).toBe(
			'var(--cup-header-grid-size)'
		);
	});

	it('draws the hero grid by default and none with grid null', () => {
		const { container } = draw();
		expect(
			container.querySelector('header')?.style.getPropertyValue('--page-header-grid-size')
		).toBe('var(--hero-grid-size)');
		const none = draw({ grid: null });
		expect(none.container.querySelector('.grid-bg')).toBeNull();
	});

	it('draws the grid inside the band with a band, and the after rows below it', () => {
		const { container } = draw({
			band: 'var(--playoffs-hero-padding-bottom)',
			first: snippet('<p>First</p>'),
			after: snippet('<p>After</p>')
		});
		const band = container.querySelector('.band');
		expect(band?.querySelector('.grid-bg')).toBeTruthy();
		expect(container.querySelectorAll('.grid-bg')).toHaveLength(1);
		expect(
			container.querySelector('header')?.style.getPropertyValue('--page-header-band-padding')
		).toBe('var(--playoffs-hero-padding-bottom)');
		const after = screen.getByText('After');
		expect(band?.contains(after)).toBe(false);
		expect(container.querySelector('.after-inner')?.contains(after)).toBe(true);
	});

	it('draws the select last, after the band rows, on mobile', () => {
		const { container } = draw({
			layout: 'mobile',
			seasonSelect,
			band: 'var(--playoffs-hero-padding-bottom)',
			after: snippet('<p>After</p>')
		});
		const row = container.querySelector('.after-inner .season-row');
		expect(row?.querySelector('select.full')).toBeTruthy();
		expect(screen.getByText('After').compareDocumentPosition(row as Node)).toBe(
			Node.DOCUMENT_POSITION_FOLLOWING
		);
	});

	it('draws the divider by default and none with divider false', () => {
		const { container } = draw();
		expect(container.querySelector('header')?.classList.contains('divider')).toBe(true);
		expect(ruleOf('.divider').get('border-bottom')).toBe(
			'var(--hairline) solid var(--color-divider)'
		);
		const none = draw({ divider: false });
		expect(none.container.querySelector('header')?.classList.contains('divider')).toBe(false);
	});

	it('sets aria-busy only when busy', () => {
		const { container } = draw({ busy: true });
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
		const idle = draw();
		expect(idle.container.querySelector('header')?.hasAttribute('aria-busy')).toBe(false);
	});
});

describe('PageHeader options', () => {
	it('sets the layout options as custom properties, and none unless given', () => {
		const plain = draw().container.querySelector<HTMLElement>('header');
		for (const name of [
			'--page-header-side-padding',
			'--page-header-gap',
			'--page-header-main-gap',
			'--page-header-lead-flex',
			'--page-header-side-flex',
			'--page-header-columns-min',
			'--page-header-band-padding',
			'--page-header-nav-height',
			'--page-header-nav-bg'
		]) {
			expect(plain?.style.getPropertyValue(name), name).toBe('');
		}
		const set = draw({
			sidePadding: 'var(--allstar-side-padding-mobile)',
			gap: 'var(--cup-header-gap)',
			mainGap: 'var(--hero-gap)',
			leadFlex: '1 1 var(--detail-column-min)',
			sideFlex: '1 1 var(--detail-column-min)',
			columnsMin: 'calc(var(--detail-column-min) * 2)',
			stickyNav: { height: 'var(--allstar-header-height)', background: 'var(--allstar-header-bg)' }
		}).container.querySelector<HTMLElement>('header');
		expect(set?.style.getPropertyValue('--page-header-side-padding')).toBe(
			'var(--allstar-side-padding-mobile)'
		);
		expect(set?.style.getPropertyValue('--page-header-gap')).toBe('var(--cup-header-gap)');
		expect(set?.style.getPropertyValue('--page-header-main-gap')).toBe('var(--hero-gap)');
		expect(set?.style.getPropertyValue('--page-header-lead-flex')).toBe(
			'1 1 var(--detail-column-min)'
		);
		expect(set?.style.getPropertyValue('--page-header-side-flex')).toBe(
			'1 1 var(--detail-column-min)'
		);
		expect(set?.style.getPropertyValue('--page-header-columns-min')).toBe(
			'calc(var(--detail-column-min) * 2)'
		);
		expect(set?.style.getPropertyValue('--page-header-nav-height')).toBe(
			'var(--allstar-header-height)'
		);
		expect(set?.style.getPropertyValue('--page-header-nav-bg')).toBe('var(--allstar-header-bg)');
	});

	it('clips the sides only with clip, without a scroll container', () => {
		const plain = draw().container.querySelector('header');
		expect(plain?.classList.contains('clip')).toBe(false);
		const clipped = draw({ clip: true }).container.querySelector('header');
		expect(clipped?.classList.contains('clip')).toBe(true);
		expect(ruleOf('.clip').get('overflow-x')).toBe('clip');
		expect(ruleOf('.page-header').has('overflow-x')).toBe(false);
	});

	it('raises the nav bar only with a sticky nav', () => {
		const plain = draw().container.querySelector('.nav-bar');
		expect(plain?.classList.contains('raised')).toBe(false);
		const raised = draw({
			stickyNav: { height: 'var(--allstar-header-height)', background: 'var(--allstar-header-bg)' }
		}).container.querySelector('.nav-bar');
		expect(raised?.classList.contains('raised')).toBe(true);
	});
});

describe('PageHeader rules', () => {
	it('puts the nav row at the hero top', () => {
		expect(ruleOf('.nav-inner').get('padding-top')).toBe('var(--identity-hero-pad-top)');
	});

	it('puts the first line at the first-line offset, and at the mobile offset on mobile', () => {
		expect(ruleOf('.main-inner').get('padding-top')).toBe('var(--header-first-line-offset)');
		expect(ruleOf('.mobile .main-inner').get('padding-top')).toBe(
			'var(--header-first-line-offset-mobile)'
		);
	});

	it('keeps the home copy centered: no first-line offset, the hero bottom padding', () => {
		const rule = ruleOf('.home .main-inner');
		expect(rule.get('padding-top')).toBe('0');
		expect(rule.get('padding-bottom')).toBe('var(--identity-hero-pad-bottom)');
	});

	it('starts a right column one gap token below the select, and keeps the select at the edge', () => {
		expect(ruleOf('.side').get('gap')).toBe('var(--game-list-gap)');
		expect(ruleOf('.season-select').get('align-self')).toBe('flex-end');
	});

	it('makes the nav bar sticky on mobile with the given background', () => {
		const rule = ruleOf('.mobile .nav-bar.raised');
		expect(rule.get('position')).toBe('sticky');
		expect(rule.get('background')).toBe('var(--page-header-nav-bg)');
	});

	it('sets the content width on the nav, the main and the after boxes', () => {
		const rule = ruleOf('.nav-inner');
		expect(rule.get('max-width')).toBe('var(--content-max-width)');
		expect(rule.get('padding-inline')).toBe('var(--page-header-side-padding, var(--side-padding))');
		expect(ruleOf('.main-inner').get('padding-top')).toBeTruthy();
		expect(ruleOf('.after-inner').get('max-width')).toBe('var(--content-max-width)');
	});
});
