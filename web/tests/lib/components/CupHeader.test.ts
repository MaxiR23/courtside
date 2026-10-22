// web/tests/lib/components/CupHeader.test.ts
//
// Tests for the CupHeader component.
//
// Tested:
// - The season tag, the state line and the h1 with the stage strip
// - The champion block only when complete, with the team link; a guest champion is not a link
// - The nav with Cup current
// - Only the nav and the h1 without a header; bones and aria-busy while loading
// - The season tag when the header has one; the select on desktop (after the nav) and mobile (full), its onChange; none without the prop
// - Spanish copy
// - The champion logo: in the cup-champion box, the code for a null logo
//
// What is covered:
// - Each state the header shows, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/CupHeader.test.ts
//
// SEE: web/src/lib/components/CupHeader.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { CupFeed } from '../../../src/lib/contract/cup';
import { toCupView } from '../../../src/lib/feed/cup-props';
import { preferLanguages } from '../../prefer-languages';
import CupHeader from '../../../src/lib/components/CupHeader.svelte';
import type { CupHeaderView } from '../../../src/lib/cup/types';

const HOME = '/' as ResolvedPathname;
const STANDINGS = '/standings' as ResolvedPathname;
const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;

const feed = (): CupFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'cup.json'), 'utf8')
	) as CupFeed;
const view = (source: CupFeed = feed()) => toCupView(source);

afterEach(() => {
	vi.restoreAllMocks();
});

const props = (extra: Record<string, unknown> = {}) => ({
	header: view().header as CupHeaderView | null,
	allGamesHref: HOME,
	standingsHref: STANDINGS,
	layout: 'desktop' as const,
	teamHref,
	...extra
});

const complete = (champion: CupFeed['champion']) => {
	const source = feed();
	source.stage = 'complete';
	source.champion = champion;
	return view(source).header;
};

describe('CupHeader', () => {
	it('renders the season tag, the state line, the h1 and the stage strip', () => {
		const { container } = render(CupHeader, { props: props() });
		expect(screen.getByText('2026-27')).toBeTruthy();
		expect(screen.getByText('Group play · 16 of 60 games played')).toBeTruthy();
		expect(screen.getByRole('heading', { level: 1, name: 'NBA Cup' })).toBeTruthy();
		expect(container.querySelectorAll('ol li')).toHaveLength(4);
		expect(container.querySelector('.champion')).toBeNull();
	});

	it('marks Cup current in the nav', async () => {
		render(CupHeader, { props: props() });
		await fireEvent.click(screen.getByRole('button', { name: 'Tournaments' }));
		expect(screen.getByRole('link', { name: 'Cup' }).getAttribute('aria-current')).toBe('page');
		expect(screen.getByRole('link', { name: 'All games' }).getAttribute('href')).toBe('/');
		expect(screen.getByRole('link', { name: 'Standings' }).getAttribute('href')).toBe('/standings');
	});

	it('shows the champion with a link to its team when the Cup is complete', () => {
		const header = complete({
			code: 'QXA',
			name: 'Herons',
			city: 'Alderton',
			guest: false,
			seasonCode: null,
			historical: false,
			logo: null,
			colors: null
		});
		const { container } = render(CupHeader, { props: props({ header }) });
		expect(container.querySelector('.champion-label')?.textContent).toBe('Champion');
		expect(container.querySelector('.city')?.textContent).toBe('Alderton');
		const links = [...container.querySelectorAll('.champion a')].map((a) => a.getAttribute('href'));
		expect(links).toEqual(['/team/qxa', '/team/qxa']);
	});

	it('does not link a guest champion', () => {
		const header = complete({
			code: null,
			name: 'Visitors',
			city: 'Faraway',
			guest: true,
			seasonCode: null,
			historical: false,
			logo: null,
			colors: null
		});
		const { container } = render(CupHeader, { props: props({ header }) });
		expect(container.querySelector('.champion-name')?.textContent?.trim()).toBe('Visitors');
		expect(container.querySelectorAll('.champion a')).toHaveLength(0);
	});

	it('renders only the nav and the h1 without a header', () => {
		const { container } = render(CupHeader, { props: props({ header: null }) });
		expect(screen.getByRole('heading', { level: 1, name: 'NBA Cup' })).toBeTruthy();
		expect(screen.getByRole('link', { name: 'All games' })).toBeTruthy();
		expect(container.querySelector('ol')).toBeNull();
		expect(container.querySelector('.bones')).toBeNull();
	});

	it('shows bones and aria-busy while loading', () => {
		const { container } = render(CupHeader, { props: props({ header: null, loading: true }) });
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('.bones')?.getAttribute('aria-hidden')).toBe('true');
	});

	it('shows Spanish copy', async () => {
		preferLanguages(['es-ES']);
		render(CupHeader, { props: props() });
		expect(screen.getByRole('heading', { level: 1, name: 'Copa NBA' })).toBeTruthy();
		await fireEvent.click(screen.getByRole('button', { name: 'Torneos' }));
		expect(screen.getByRole('link', { name: 'Copa' }).getAttribute('aria-current')).toBe('page');
	});
});

describe('CupHeader season selector and tag', () => {
	const seasonSelect = (onChange = vi.fn()) => ({
		seasons: [
			{ season: 2027, seasonLabel: '2026-27' },
			{ season: 2025, seasonLabel: '2024-25' }
		],
		value: 2027,
		onChange
	});

	it('draws the season tag only when the header has one', () => {
		const tagged = { ...view().header, tag: 'Season 2024-25' };
		const { unmount } = render(CupHeader, { props: props({ header: tagged }) });
		expect(screen.getByText('Season 2024-25')).toBeTruthy();
		unmount();
		render(CupHeader, { props: props() });
		expect(screen.queryByText('Season 2024-25')).toBeNull();
	});

	it('draws the select on desktop and calls onChange with the end year', () => {
		const onChange = vi.fn();
		render(CupHeader, { props: props({ seasonSelect: seasonSelect(onChange) }) });
		const select = screen.getByRole('combobox', { name: 'Season' }) as HTMLSelectElement;
		expect([...select.options].map((option) => option.textContent)).toEqual(['2026-27', '2024-25']);
		expect(select.classList.contains('full')).toBe(false);
		select.value = '2025';
		select.dispatchEvent(new Event('change', { bubbles: true }));
		expect(onChange).toHaveBeenCalledWith(2025);
	});

	it('draws the select full width on mobile', () => {
		render(CupHeader, { props: props({ layout: 'mobile', seasonSelect: seasonSelect() }) });
		expect(screen.getByRole('combobox', { name: 'Season' }).classList.contains('full')).toBe(true);
	});

	it('draws no select without the prop', () => {
		render(CupHeader, { props: props() });
		expect(screen.queryByRole('combobox')).toBeNull();
	});
});

describe('CupHeader champion logo', () => {
	const champion = {
		code: 'QXA',
		name: 'Herons',
		city: 'Alderton',
		guest: false,
		seasonCode: null,
		historical: false,
		logo: null,
		colors: null
	};

	it('draws the champion logo in the cup-champion box, and the code for a null logo', () => {
		const withLogo = complete({
			...champion,
			logo: { light: 'https://example.com/x-light.svg', dark: 'https://example.com/x-dark.svg' }
		});
		const first = render(CupHeader, { props: props({ header: withLogo }) });
		const box = first.container.querySelector('.champion .team-monogram');
		expect(box?.classList.contains('cup-champion')).toBe(true);
		expect(box?.querySelector('img')?.getAttribute('src')).toBe('https://example.com/x-dark.svg');
		first.unmount();
		const second = render(CupHeader, { props: props({ header: complete(champion) }) });
		const plain = second.container.querySelector('.champion .team-monogram');
		expect(plain?.querySelector('img')).toBeNull();
		expect(plain?.textContent).toBe('QXA');
	});
});
