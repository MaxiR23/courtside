// web/tests/lib/components/CupPage.test.ts
//
// Tests for the CupPage component.
//
// Tested:
// - Ready: the sections in group order in group play and the draw, in knockout order after
// - The bracket sits in the Bracket section in both section orders, with no placeholder text; Groups not drawn yet before the draw; the legend
// - One More columns state widens every group card
// - Loading: the header and the table skeleton are aria-busy
// - The unavailable state of a past season keeps the Season tag; the current season's has none (ADR 0054)
// - Unavailable: the unavailable row under the nav; the footer in every state
// - Spanish copy
// - The champion logo in the header decoration, the outlined code for a null logo
//
// What is covered:
// - Each state the page shows, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/CupPage.test.ts
//
// SEE: web/src/lib/components/CupPage.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { CupFeed } from '../../../src/lib/contract/cup';
import { toCupView } from '../../../src/lib/feed/cup-props';
import { preferLanguages } from '../../prefer-languages';
import CupPage from '../../../src/lib/components/CupPage.svelte';
import { CupMatchupStore } from '../../../src/lib/cup/matchup.svelte';
import type { CupPageState } from '../../../src/lib/cup/types';
const HOME = '/' as ResolvedPathname;
const STANDINGS = '/standings' as ResolvedPathname;
const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;
const gameHref = (id: string) => `/game/${id}` as ResolvedPathname;
const playerHref = (id: string) => `/player/${id}` as ResolvedPathname;

const feed = (): CupFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'cup.json'), 'utf8')
	) as CupFeed;

afterEach(() => {
	vi.restoreAllMocks();
});

const UNAVAILABLE = "Data isn't available right now. Check back later.";

const ready = (change: (f: CupFeed) => void = () => {}): CupPageState => {
	const source = feed();
	change(source);
	return { kind: 'ready', view: toCupView(source) };
};

const show = (state: CupPageState) =>
	render(CupPage, {
		props: {
			state,
			allGamesHref: HOME,
			standingsHref: STANDINGS,
			layout: 'desktop' as const,
			teamHref,
			gameHref,
			playerHref,
			matchup: new CupMatchupStore(undefined)
		}
	});

const headings = () => screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent);

describe('CupPage', () => {
	it('ready: draws the sections in group order during group play', () => {
		const { container } = show(ready());
		expect(headings()).toEqual(['Groups', 'Wild card', 'Bracket', 'Cup games']);
		expect([...container.querySelectorAll('.sections > section')].map((s) => s.id)).toEqual([
			'groups',
			'wild-card',
			'bracket',
			'games'
		]);
		expect(container.querySelectorAll('article')).toHaveLength(6);
		expect(screen.getAllByRole('table').length).toBeGreaterThan(0);
	});

	it('ready: draws the bracket first once the knockout rounds start', () => {
		show(ready((f) => (f.stage = 'quarterfinals')));
		expect(headings()).toEqual(['Bracket', 'Groups', 'Wild card', 'Cup games']);
	});

	it('ready: the bracket sits in the Bracket section in both section orders', () => {
		for (const stage of ['group', 'semifinals'] as const) {
			const { container, unmount } = show(ready((f) => (f.stage = stage)));
			const section = container.querySelector('#bracket');
			expect(section?.querySelector('.viewport')).not.toBeNull();
			expect(section?.querySelectorAll('.node')).toHaveLength(7);
			unmount();
		}
	});

	it('ready: says the groups are not drawn yet instead of the groups', () => {
		const { container } = show(
			ready((f) => {
				f.stage = 'draw';
				f.drawn = false;
			})
		);
		expect(screen.getAllByText('Groups not drawn yet').length).toBeGreaterThan(0);
		expect(container.querySelectorAll('article')).toHaveLength(0);
		expect(container.querySelector('.legend')).toBeNull();
		expect(headings()).toEqual(['Groups', 'Wild card', 'Bracket', 'Cup games']);
	});

	it('ready: shows the legend with the three tags', () => {
		const { container } = show(ready());
		const entries = [...container.querySelectorAll('.legend .entry')].map((e) =>
			e.textContent?.replace(/\s+/g, ' ').trim()
		);
		expect(entries).toEqual(['y Won group', 'x Wild card', 'e Eliminated']);
	});

	it('ready: one More columns toggle widens every group card', async () => {
		const { container } = show(ready());
		const before = screen.getAllByRole('columnheader').length;
		expect(container.querySelector('.groups')?.classList.contains('wide')).toBe(false);
		const buttons = screen.getAllByRole('button', { name: 'More columns' });
		expect(buttons).toHaveLength(2);
		await fireEvent.click(buttons[0]!);
		expect(container.querySelector('.groups')?.classList.contains('wide')).toBe(true);
		for (const button of screen.getAllByRole('button', { name: 'More columns' })) {
			expect(button.getAttribute('aria-pressed')).toBe('true');
		}
		expect(screen.getAllByRole('columnheader').length).toBeGreaterThan(before);
	});

	it('ready: lists the Cup games under the chips', () => {
		show(ready());
		expect(screen.getByRole('group', { name: 'Filter Cup games' })).toBeTruthy();
		expect(screen.getAllByRole('heading', { level: 3, name: /^Wednesday/ })).toHaveLength(2);
	});

	it('loading: the header and the table skeleton are aria-busy', () => {
		const { container } = show({ kind: 'loading' });
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('.table-skeleton')?.getAttribute('aria-busy')).toBe('true');
		expect(screen.queryByText(UNAVAILABLE)).toBeNull();
	});

	it('unavailable: the unavailable row under the nav', () => {
		show({ kind: 'unavailable' });
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		expect(screen.getByRole('link', { name: 'All games' })).toBeTruthy();
		expect(screen.getByRole('heading', { level: 1, name: 'NBA Cup' })).toBeTruthy();
	});

	it('keeps the Season tag on the unavailable state of a past season, and has none on the current one', () => {
		const props = {
			state: { kind: 'unavailable' } as CupPageState,
			allGamesHref: HOME,
			standingsHref: STANDINGS,
			layout: 'desktop' as const,
			teamHref,
			gameHref,
			playerHref,
			matchup: new CupMatchupStore(undefined)
		};
		const { unmount } = render(CupPage, { props: { ...props, seasonTag: 'Season 2022-23' } });
		expect(screen.getByText('Season 2022-23')).toBeTruthy();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		unmount();
		render(CupPage, { props });
		expect(screen.queryByText(/^Season /)).toBeNull();
	});

	it('draws the footer in every state', () => {
		for (const state of [ready(), { kind: 'loading' }, { kind: 'unavailable' }] as CupPageState[]) {
			const { container, unmount } = show(state);
			expect(container.ownerDocument.querySelector('footer')).toBeTruthy();
			unmount();
		}
	});

	it('renders in Spanish', () => {
		preferLanguages(['es-ES']);
		show(ready());
		expect(headings()).toEqual(['Grupos', 'Comodín', 'Cuadro', 'Partidos de la Copa']);
		preferLanguages(['es-ES']);
		show({ kind: 'unavailable' });
		expect(
			screen.getByText(
				'Los datos no están disponibles en este momento. Vuelve a consultar más tarde.'
			)
		).toBeTruthy();
	});
});

describe('CupPage champion logo', () => {
	it('draws the champion logo in the header decoration, and the code for a null logo', () => {
		const champion = (logo: CupFeed['champion'] extends infer C ? C : never) => ({
			code: 'QXA',
			name: 'Herons',
			city: 'Alderton',
			guest: false,
			seasonCode: null,
			historical: false,
			logo,
			colors: null
		});
		const withLogo = ready((f) => {
			f.stage = 'complete';
			f.champion = champion({
				light: 'https://example.com/a-light.svg',
				dark: 'https://example.com/a-dark.svg'
			} as never) as CupFeed['champion'];
		});
		const first = show(withLogo);
		expect(first.container.querySelector('.decor .logo img')?.getAttribute('src')).toBe(
			'https://example.com/a-dark.svg'
		);
		first.unmount();
		const second = show(
			ready((f) => {
				f.stage = 'complete';
				f.champion = champion(null as never) as CupFeed['champion'];
			})
		);
		expect(second.container.querySelector('.decor .logo')).toBeNull();
		expect(second.container.querySelector('.decor .outline')?.textContent).toBe('QXA');
	});
});
