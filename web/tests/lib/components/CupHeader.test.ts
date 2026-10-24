// web/tests/lib/components/CupHeader.test.ts
//
// Tests for the CupHeader component.
//
// Tested:
// - The year tag (or the past season tag in its place), the state line and the h1 with the four-step timeline
// - The decoration and the team row: the champion when complete, the defending champion before; the label, the outline, the logo, the bar and the accent; no links in the decoration
// - No decoration and no team row without a team; the rest of the header stays
// - The timeline: complete and in-progress classes, status texts, dates with their notes
// - The mobile layout class
// - The decoration clipped at the 48px gap above the title block (stylesheet source)
// - The nav with Cup current
// - Only the nav and the h1 without a header; bones and aria-busy while loading
// - The decoration inside the title block's text wrapper (desktop and mobile), before the tag row; the champion's city and name
// - The season tag when the header has one; the select on desktop (after the nav) and mobile (full), its onChange; none without the prop
// - Spanish copy
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

const club = (change: Record<string, unknown> = {}) => ({
	code: 'QXA',
	name: 'Herons',
	city: 'Alderton',
	guest: false,
	seasonCode: null,
	historical: false,
	logo: null,
	colors: null,
	...change
});

const complete = (champion: CupFeed['champion'], accent: string | null = null) => {
	const source = feed();
	source.stage = 'complete';
	source.champion = champion;
	source.championAccent = accent;
	return view(source).header;
};

const defending = (team: CupFeed['defendingChampion'], accent: string | null = null) => {
	const source = feed();
	source.defendingChampion = team;
	source.defendingChampionAccent = accent;
	return view(source).header;
};

const seasonSelectProp = () => ({
	seasons: [{ season: 2027, seasonLabel: '2026-27' }],
	value: 2027,
	onChange: vi.fn()
});

describe('CupHeader', () => {
	it('renders the year tag, the state line, the h1 and the timeline', () => {
		const { container } = render(CupHeader, { props: props() });
		expect(container.querySelector('.year-tag')?.textContent).toBe('2026-27');
		expect(screen.getByText('Group play · 16 of 60 games played')).toBeTruthy();
		expect(screen.getByRole('heading', { level: 1, name: 'NBA Cup' })).toBeTruthy();
		expect(container.querySelectorAll('ol.cup-timeline li')).toHaveLength(4);
	});

	it('marks Cup current in the nav', async () => {
		render(CupHeader, { props: props() });
		await fireEvent.click(screen.getByRole('button', { name: 'Tournaments' }));
		expect(screen.getByRole('link', { name: 'Cup' }).getAttribute('aria-current')).toBe('page');
		expect(screen.getByRole('link', { name: 'All games' }).getAttribute('href')).toBe('/');
		expect(screen.getByRole('link', { name: 'Standings' }).getAttribute('href')).toBe('/standings');
	});

	it('shows the champion decoration and team row when the Cup is complete', () => {
		const colors = { primary: '#111111', secondary: '#222222' };
		const header = complete(club({ colors }), '#abcdef');
		const { container } = render(CupHeader, { props: props({ header }) });
		expect(container.querySelector('.decor')?.getAttribute('aria-hidden')).toBe('true');
		expect(container.querySelector('.outline')?.textContent).toBe('QXA');
		expect(container.querySelector('.team-label')?.textContent).toBe('Champion');
		expect(container.querySelector('.team-name a')?.getAttribute('href')).toBe('/team/qxa');
		const halves = [...container.querySelectorAll<HTMLElement>('.bar .half')];
		expect(halves.map((half) => half.style.backgroundColor)).toEqual([
			'rgb(17, 17, 17)',
			'rgb(34, 34, 34)'
		]);
		expect(container.querySelector('header')?.style.getPropertyValue('--side-accent')).toBe(
			'#abcdef'
		);
		expect(container.querySelectorAll('.decor a')).toHaveLength(0);
	});

	it('uses the neutral accent and no bar when the feed has no color', () => {
		const { container } = render(CupHeader, { props: props({ header: complete(club()) }) });
		expect(container.querySelector('header')?.style.getPropertyValue('--side-accent')).toBe(
			'var(--identity-neutral-accent)'
		);
		expect(container.querySelector('.bar')).toBeNull();
	});

	it('writes the champion city and name, linking the team page', () => {
		const { container } = render(CupHeader, { props: props({ header: complete(club()) }) });
		expect(container.querySelector('.team-name')?.textContent?.trim()).toBe('Alderton Herons');
		expect(container.querySelector('.team-name a')?.getAttribute('href')).toBe('/team/qxa');
	});

	it('writes only the name when the team has no city', () => {
		const header = complete(club({ city: null }));
		const { container } = render(CupHeader, { props: props({ header }) });
		expect(container.querySelector('.team-name')?.textContent?.trim()).toBe('Herons');
	});

	it('places the decoration inside the title block, before the title text', () => {
		const { container } = render(CupHeader, {
			props: props({ header: complete(club()), seasonSelect: seasonSelectProp() })
		});
		const area = container.querySelector('.title-area');
		expect(container.querySelector('.title-block > .title-text > .decor')).not.toBeNull();
		expect(container.querySelector('.title-block > .decor')).toBeNull();
		expect(container.querySelector('.title-block > .title-text > .tag-row')).not.toBeNull();
		expect(container.querySelector('.title-block > .title-text > h1')).not.toBeNull();
		expect(container.querySelector('.title-block > .title-text > .team-row')).not.toBeNull();
		expect(container.querySelector('.title-area > .decor')).toBeNull();
		expect(container.querySelector('header > .decor')).toBeNull();
		expect(container.querySelector('.content > .decor')).toBeNull();
		expect(
			container.querySelector('.title-text')?.firstElementChild?.classList.contains('decor')
		).toBe(true);
		expect(container.querySelector('.decor .glow')).not.toBeNull();
		expect(container.querySelector('.decor .outline')).not.toBeNull();
		expect(container.querySelector('.title-block ol.cup-timeline')).toBeNull();
		expect(container.querySelector('.title-area > ol.cup-timeline')).not.toBeNull();
		expect(area?.querySelector('nav')).toBeNull();
		expect(area?.querySelector('.season-row')).toBeNull();
		expect(container.querySelector('.season-row')).not.toBeNull();
	});

	it('clips the decoration at the gap above the title block', () => {
		const source = readFileSync(
			join(__dirname, '..', '..', '..', 'src', 'lib', 'components', 'CupHeader.svelte'),
			'utf8'
		);
		const rule = /\n\t\.title-block \{([^}]*)\}/.exec(source)?.[1] ?? '';
		expect(rule.replace(/\s+/g, ' ')).toContain(
			'clip-path: inset( calc(-1 * var(--cup-header-gap))'
		);
	});

	it('places the decoration inside the title block on mobile', () => {
		const { container } = render(CupHeader, {
			props: props({ header: complete(club()), layout: 'mobile' })
		});
		expect(container.querySelector('.title-block > .title-text > .decor')).not.toBeNull();
		expect(container.querySelector('.title-area > .decor')).toBeNull();
	});

	it('does not link a guest champion', () => {
		const header = complete(club({ code: null, name: 'Visitors', city: 'Faraway', guest: true }));
		const { container } = render(CupHeader, { props: props({ header }) });
		expect(container.querySelector('.team-name')?.textContent?.trim()).toBe('Faraway Visitors');
		expect(container.querySelectorAll('.team-name a')).toHaveLength(0);
	});

	it('shows the defending champion during group play', () => {
		const header = defending(club(), '#123456');
		const { container } = render(CupHeader, { props: props({ header }) });
		expect(container.querySelector('.team-label')?.textContent).toBe('Defending champion');
		expect(screen.getByText('Group play · 16 of 60 games played')).toBeTruthy();
		expect(container.querySelector('.decor')).not.toBeNull();
		expect(container.querySelector('header')?.style.getPropertyValue('--side-accent')).toBe(
			'#123456'
		);
	});

	it('draws no decoration and no team row without a defending champion', () => {
		const { container } = render(CupHeader, { props: props() });
		expect(container.querySelector('.decor')).toBeNull();
		expect(container.querySelector('.title-area .title-block')).not.toBeNull();
		expect(container.querySelector('.title-area ol.cup-timeline')).not.toBeNull();
		expect(container.querySelector('.team-row')).toBeNull();
		expect(container.querySelector('header')?.style.getPropertyValue('--side-accent')).toBe('');
		expect(container.querySelector('.year-tag')?.textContent).toBe('2026-27');
		expect(screen.getByText('Group play · 16 of 60 games played')).toBeTruthy();
		expect(screen.getByRole('heading', { level: 1, name: 'NBA Cup' })).toBeTruthy();
		expect(container.querySelectorAll('ol.cup-timeline li')).toHaveLength(4);
	});

	it('marks the timeline steps and writes their status and dates', () => {
		const { container } = render(CupHeader, { props: props() });
		const steps = [...container.querySelectorAll('ol.cup-timeline li')];
		expect(steps.map((step) => step.classList.contains('complete'))).toEqual([
			false,
			false,
			false,
			false
		]);
		expect(steps.map((step) => step.classList.contains('in-progress'))).toEqual([
			true,
			false,
			false,
			false
		]);
		expect(steps.map((step) => step.querySelector('.status')?.textContent)).toEqual([
			'In progress',
			'Next',
			'Upcoming',
			'Upcoming'
		]);
		expect(steps.map((step) => step.querySelector('.dates')?.textContent)).toEqual([
			'Nov 4 – Dec 2 · 4 games per team',
			'Dec 8 · Higher seed hosts',
			'TBD',
			'Dec 16'
		]);
	});

	it('marks a complete step', () => {
		const source = feed();
		source.stages[0].status = 'complete';
		const { container } = render(CupHeader, { props: props({ header: view(source).header }) });
		const steps = container.querySelectorAll('ol.cup-timeline li');
		expect(steps[0]?.classList.contains('complete')).toBe(true);
		expect(steps[0]?.classList.contains('in-progress')).toBe(false);
		expect(steps[0]?.querySelector('.status')?.textContent).toBe('Complete');
	});

	it('draws the mobile layout', () => {
		const { container } = render(CupHeader, { props: props({ layout: 'mobile' }) });
		expect(container.querySelector('header')?.classList.contains('mobile')).toBe(true);
		expect(container.querySelector('header')?.classList.contains('desktop')).toBe(false);
	});

	it('marks Cup current in the nav', async () => {
		render(CupHeader, { props: props() });
		await fireEvent.click(screen.getByRole('button', { name: 'Tournaments' }));
		expect(screen.getByRole('link', { name: 'Cup' }).getAttribute('aria-current')).toBe('page');
		expect(screen.getByRole('link', { name: 'All games' }).getAttribute('href')).toBe('/');
		expect(screen.getByRole('link', { name: 'Standings' }).getAttribute('href')).toBe('/standings');
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

	it('shows the Spanish defending champion label and note', () => {
		preferLanguages(['es-ES']);
		const source = feed();
		source.defendingChampion = club() as CupFeed['defendingChampion'];
		const { container } = render(CupHeader, { props: props({ header: view(source).header }) });
		expect(container.querySelector('.team-label')?.textContent).toBe('Campeón vigente');
		expect(container.querySelector('.dates')?.textContent).toContain('4 partidos por equipo');
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

	it('draws only the past season tag on a past season', () => {
		const tagged = { ...view().header, tag: 'Season 2024-25' };
		const { container, unmount } = render(CupHeader, { props: props({ header: tagged }) });
		expect(screen.getByText('Season 2024-25')).toBeTruthy();
		expect(container.querySelector('.year-tag')).toBeNull();
		expect(screen.getByText('Group play · 16 of 60 games played')).toBeTruthy();
		unmount();
		const plain = render(CupHeader, { props: props() });
		expect(screen.queryByText('Season 2024-25')).toBeNull();
		expect(plain.container.querySelector('.year-tag')?.textContent).toBe('2026-27');
	});

	it('draws only the past season tag from a past feed', () => {
		const header = toCupView(feed(), { past: true }).header;
		const { container } = render(CupHeader, { props: props({ header }) });
		expect(screen.getAllByText('Season 2026-27')).toHaveLength(1);
		expect(container.querySelector('.year-tag')).toBeNull();
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

describe('CupHeader decoration logo', () => {
	it('draws the logo as a decoration, and none for a null logo', () => {
		const withLogo = complete(
			club({
				logo: { light: 'https://example.com/x-light.svg', dark: 'https://example.com/x-dark.svg' }
			})
		);
		const first = render(CupHeader, { props: props({ header: withLogo }) });
		expect(
			first.container.querySelector('.title-text > .decor .logo img')?.getAttribute('src')
		).toBe('https://example.com/x-dark.svg');
		expect(first.container.querySelectorAll('.decor a')).toHaveLength(0);
		first.unmount();
		const second = render(CupHeader, { props: props({ header: complete(club()) }) });
		expect(second.container.querySelector('.title-text > .decor .logo')).toBeNull();
		expect(second.container.querySelector('.outline')?.textContent).toBe('QXA');
	});
});
