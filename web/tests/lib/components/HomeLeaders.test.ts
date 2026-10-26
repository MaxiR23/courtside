// web/tests/lib/components/HomeLeaders.test.ts
//
// Tests for the Leaders section of the home with no games.
//
// Tested:
// - The kicker and the title as the h2
// - Four rows in order with category, team code, name and value
// - One row per leader sent, for one to four leaders
// - A photo draws an img with the name as alt; a null photo draws the placeholder and no img
// - A leader with no team shows the category and no separator
// - Each title key in English and Spanish
// - The mobile class
//
// What is covered:
// - Each state of the rows; jsdom does not lay out, so classes are asserted
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/HomeLeaders.test.ts
//
// SEE: web/src/lib/components/HomeLeaders.svelte
import { render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import HomeLeaders from '../../../src/lib/components/HomeLeaders.svelte';
import type { HomeFeed } from '../../../src/lib/contract/home';
import { toHomeLeadersView } from '../../../src/lib/feed/home-props';
import { preferLanguages } from '../../prefer-languages';

const feed = (): HomeFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'home.json'), 'utf8')
	) as HomeFeed;
const view = (count = 4, edit: (home: HomeFeed) => void = () => {}) => {
	const home = feed();
	edit(home);
	home.leaders!.categories = home.leaders!.categories.slice(0, count) as never;
	return toHomeLeadersView(home)!;
};
const rows = (container: HTMLElement) => [...container.querySelectorAll('li.leader')];

afterEach(() => {
	vi.restoreAllMocks();
});

describe('HomeLeaders', () => {
	it('shows the kicker and the title as the h2', () => {
		const { container } = render(HomeLeaders, { props: { view: view(), layout: 'desktop' } });
		expect(screen.getByRole('heading', { level: 2 }).textContent).toBe('This season');
		expect(container.querySelector('.kicker')?.textContent).toBe('Leaders');
	});

	it('shows four rows in order with category, team, name and value', () => {
		const { container } = render(HomeLeaders, { props: { view: view(), layout: 'desktop' } });
		const list = rows(container);
		expect(list).toHaveLength(4);
		expect(list[0].textContent).toContain('Points per game');
		expect(list[0].textContent).toContain('NRT');
		expect(list[0].textContent).toContain('Aron Vale');
		expect(list[0].textContent).toContain('31.4');
		expect(list.map((l) => l.querySelector('.meta')?.textContent?.split('·')[0].trim())).toEqual([
			'Points per game',
			'Rebounds per game',
			'Assists per game',
			'Blocks per game'
		]);
	});

	it.each([1, 2, 3, 4])('renders exactly %i rows for that many leaders', (count) => {
		const { container } = render(HomeLeaders, { props: { view: view(count), layout: 'desktop' } });
		const order = ['Points', 'Rebounds', 'Assists', 'Blocks'].slice(0, count);
		const list = rows(container);
		expect(list).toHaveLength(count);
		expect(list.map((l) => l.querySelector('.meta')?.textContent?.trim().split(' ')[0])).toEqual(
			order
		);
	});

	it('draws a photo as an img and a null photo as the placeholder', () => {
		const { container } = render(HomeLeaders, { props: { view: view(), layout: 'desktop' } });
		const list = rows(container);
		expect(list[0].querySelector('img')?.getAttribute('alt')).toBe('Aron Vale');
		expect(list[1].querySelector('img')).toBeNull();
		const placeholder = list[1].querySelector('[role="img"]') as HTMLElement;
		expect(placeholder.textContent?.trim()).toBe('BO');
	});

	it('shows no separator for a leader with no team', () => {
		const { container } = render(HomeLeaders, { props: { view: view(), layout: 'desktop' } });
		const meta = rows(container)[2].querySelector('.meta') as HTMLElement;
		expect(meta.textContent?.trim()).toBe('Assists per game');
	});

	it.each([
		['season', null, 'This season', 'Esta temporada'],
		['playoffs', null, 'Playoffs', 'Playoffs'],
		['previousSeason', '2025-26', '2025-26 season', 'Temporada 2025-26'],
		['previousSeason', null, 'Last season', 'Temporada pasada']
	] as const)('shows the %s title (%s) in both languages', (title, label, en, es) => {
		const edit = (home: HomeFeed) => {
			home.leaders!.title = title;
			home.leaders!.seasonLabel = label;
		};
		const first = render(HomeLeaders, { props: { view: view(4, edit), layout: 'desktop' } });
		expect(screen.getByRole('heading', { level: 2 }).textContent).toBe(en);
		first.unmount();
		preferLanguages(['es']);
		render(HomeLeaders, { props: { view: view(4, edit), layout: 'desktop' } });
		expect(screen.getByRole('heading', { level: 2 }).textContent).toBe(es);
	});

	it('takes the mobile class', () => {
		const { container } = render(HomeLeaders, { props: { view: view(), layout: 'mobile' } });
		expect(container.querySelector('section.home-leaders.mobile')).not.toBeNull();
	});
});
