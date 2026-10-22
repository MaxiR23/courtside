// web/tests/lib/components/SearchResultRow.test.ts
//
// Tests for the SearchResultRow component, one team or player row of the search overlay.
//
// Tested:
// - Team row: a tile with a strip in both colors, a plain tile without colors, city, name, meta, record, link
// - Player row: the photo, initials with a null photo, the long line on desktop, the short name and line on mobile
// - No line when it is empty
// - The injury tag follows the status (out, questionable, doubtful, day-to-day) and is absent without an injury
// - The team bar is in the primary color, plain when null
// - The team row draws the logo in the search box and the player row an inline logo before the code, on both layouts; a null logo draws the monogram
// - The active class follows the prop; mouseenter calls onHover; click calls onOpen
//
// What is covered:
// - Every state of both row kinds; jsdom does not lay out, so looks are asserted through classes and styles
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/SearchResultRow.test.ts
//
// SEE: web/src/lib/components/SearchResultRow.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

import type { SearchPlayerRow, SearchTeamRow } from '../../../src/lib/search/types';

import SearchResultRow from '../../../src/lib/components/SearchResultRow.svelte';

const team: SearchTeamRow = {
	code: 'OKC',
	team: { code: 'OKC', name: 'Thunder', city: 'Oklahoma City', guest: false },
	city: 'Oklahoma City',
	name: 'Thunder',
	meta: 'OKC · 1st in Northwest',
	record: '64-18',
	strip: { primary: '#007ac1', secondary: '#ef3b24' }
};
const player: SearchPlayerRow = {
	id: '1628983',
	name: 'Shai Gilgeous-Alexander',
	shortName: 'S. Gilgeous-Alexander',
	line: '#2 · Guard (G)',
	lineShort: '#2 · G',
	photo: 'https://cdn.example.com/players/1628983.png',
	injury: null,
	teamCode: 'OKC',
	team: { code: 'OKC', name: null, city: null, guest: false },
	teamColor: '#007ac1'
};

const base = {
	href: '/team/okc' as ResolvedPathname,
	layout: 'desktop' as const,
	active: false,
	id: 'search-row-0',
	onHover: () => {},
	onOpen: () => {}
};
const teamRow = (over: Partial<SearchTeamRow> = {}) => ({
	kind: 'team' as const,
	team: { ...team, ...over }
});
const playerRow = (over: Partial<SearchPlayerRow> = {}) => ({
	kind: 'player' as const,
	player: { ...player, ...over }
});

describe('SearchResultRow, team', () => {
	it('shows city, name, meta and record in a link to the href', () => {
		render(SearchResultRow, { props: { ...base, row: teamRow() } });
		const link = screen.getByRole('link');
		expect(link.getAttribute('href')).toBe('/team/okc');
		expect(link.id).toBe('search-row-0');
		for (const text of ['Oklahoma City', 'Thunder', 'OKC · 1st in Northwest', '64-18']) {
			expect(screen.getByText(text)).toBeTruthy();
		}
	});

	it('draws a strip in both colors', () => {
		const { container } = render(SearchResultRow, { props: { ...base, row: teamRow() } });
		const halves = container.querySelectorAll<HTMLElement>('.strip .half');
		expect([...halves].map((h) => h.style.backgroundColor)).toEqual([
			'rgb(0, 122, 193)',
			'rgb(239, 59, 36)'
		]);
		expect(container.querySelector('.tile')?.classList.contains('plain')).toBe(false);
	});

	it('draws a plain tile without colors', () => {
		const { container } = render(SearchResultRow, {
			props: { ...base, row: teamRow({ strip: null }) }
		});
		expect(container.querySelector('.strip')).toBeNull();
		expect(container.querySelector('.tile')?.classList.contains('plain')).toBe(true);
	});
});

describe('SearchResultRow, player', () => {
	const playerBase = { ...base, href: '/player/1628983' as ResolvedPathname };

	it('shows the photo, the name and the long line on desktop', () => {
		render(SearchResultRow, { props: { ...playerBase, row: playerRow() } });
		expect(screen.getByRole('img', { name: 'Shai Gilgeous-Alexander' }).getAttribute('src')).toBe(
			player.photo
		);
		expect(screen.getByText('Shai Gilgeous-Alexander')).toBeTruthy();
		expect(screen.getByText('#2 · Guard (G)')).toBeTruthy();
	});

	it('shows the initials with a null photo', () => {
		render(SearchResultRow, { props: { ...playerBase, row: playerRow({ photo: null }) } });
		expect(screen.getByRole('img', { name: 'Shai Gilgeous-Alexander' }).textContent).toBe('SG');
	});

	it('shows the short name and short line on mobile', () => {
		render(SearchResultRow, { props: { ...playerBase, layout: 'mobile', row: playerRow() } });
		expect(screen.getByText('S. Gilgeous-Alexander')).toBeTruthy();
		expect(screen.getByText('#2 · G')).toBeTruthy();
		expect(screen.queryByText('#2 · Guard (G)')).toBeNull();
	});

	it('shows no line when it is empty', () => {
		const { container } = render(SearchResultRow, {
			props: { ...playerBase, row: playerRow({ line: '', lineShort: '' }) }
		});
		expect(container.querySelector('.meta')).toBeNull();
	});

	it('shows the injury tag with the class of its status', () => {
		for (const [injury, label] of [
			['out', 'Out'],
			['questionable', 'Questionable'],
			['doubtful', 'Doubtful'],
			['day-to-day', 'Day-to-day']
		] as const) {
			const { unmount } = render(SearchResultRow, {
				props: { ...playerBase, row: playerRow({ injury }) }
			});
			const tag = screen.getByText(label);
			expect(tag.classList.contains(injury)).toBe(true);
			unmount();
		}
	});

	it('shows no tag without an injury', () => {
		const { container } = render(SearchResultRow, {
			props: { ...playerBase, row: playerRow() }
		});
		expect(container.querySelector('.status-tag')).toBeNull();
	});

	it('draws the team bar in the primary color, plain when null', () => {
		const { container, unmount } = render(SearchResultRow, {
			props: { ...playerBase, row: playerRow() }
		});
		const bar = container.querySelector<HTMLElement>('.bar');
		expect(bar?.style.backgroundColor).toBe('rgb(0, 122, 193)');
		expect(bar?.classList.contains('plain')).toBe(false);
		expect(container.querySelector('.team .code')?.textContent).toBe('OKC');
		unmount();
		const plain = render(SearchResultRow, {
			props: { ...playerBase, row: playerRow({ teamColor: null }) }
		});
		expect(plain.container.querySelector('.bar')?.classList.contains('plain')).toBe(true);
	});
});

describe('SearchResultRow, interaction', () => {
	it('follows the active prop', () => {
		const { rerender } = render(SearchResultRow, { props: { ...base, row: teamRow() } });
		expect(screen.getByRole('link').classList.contains('active')).toBe(false);
		rerender({ ...base, row: teamRow(), active: true });
		expect(screen.getByRole('link').classList.contains('active')).toBe(true);
	});

	it('calls onHover on mouseenter and onOpen on click', async () => {
		const onHover = vi.fn();
		const onOpen = vi.fn();
		render(SearchResultRow, { props: { ...base, row: teamRow(), onHover, onOpen } });
		await fireEvent.mouseEnter(screen.getByRole('link'));
		expect(onHover).toHaveBeenCalledTimes(1);
		await fireEvent.click(screen.getByRole('link'));
		expect(onOpen).toHaveBeenCalledTimes(1);
	});
});

describe('SearchResultRow, logos', () => {
	const logo = {
		light: 'https://example.com/okc-light.svg',
		dark: 'https://example.com/okc-dark.svg'
	};

	it('draws the team logo in the search box, and the code with a null logo', () => {
		const withLogo = render(SearchResultRow, {
			props: { ...base, row: teamRow({ team: { ...team.team, logo } }) }
		});
		const box = withLogo.container.querySelector('.team-monogram.search');
		expect(box?.querySelector('img')?.getAttribute('src')).toBe('https://example.com/okc-dark.svg');
		expect(box?.querySelector('img')?.getAttribute('aria-hidden')).toBe('true');
		withLogo.unmount();
		const plain = render(SearchResultRow, { props: { ...base, row: teamRow() } });
		const code = plain.container.querySelector('.team-monogram.search');
		expect(code?.querySelector('img')).toBeNull();
		expect(code?.textContent).toBe('OKC');
	});

	it('draws the inline logo before the team code of a player, on both layouts', () => {
		for (const layout of ['desktop', 'mobile'] as const) {
			const { container, unmount } = render(SearchResultRow, {
				props: { ...base, layout, row: playerRow({ team: { ...player.team, logo } }) }
			});
			const mark = container.querySelector('.team .team-monogram.inline');
			expect(mark?.querySelector('img')?.getAttribute('src')).toBe(
				'https://example.com/okc-dark.svg'
			);
			expect(mark?.nextElementSibling?.classList.contains('code')).toBe(true);
			unmount();
		}
	});

	it('draws the monogram of a player team with a null logo', () => {
		const { container } = render(SearchResultRow, { props: { ...base, row: playerRow() } });
		const mark = container.querySelector('.team .team-monogram.inline');
		expect(mark?.querySelector('img')).toBeNull();
		expect(mark?.textContent).toBe('OKC');
	});
});
