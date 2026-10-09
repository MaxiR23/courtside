// web/tests/lib/components/Leaders.test.ts
//
// Tests for the Leaders component.
//
// Tested:
// - Each team's top performer with team code, name and stat line
// - Each team code links to the team page
// - A placeholder in place of a photo that fails to load, keeping the other photo
// - The stat line in Spanish with a Spanish browser preference
// - A guest leader: the team code is plain text and a missing photo shows the initials
//
// What is covered:
// - Happy path, the photo error interaction and Spanish
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/Leaders.test.ts
//
// SEE: web/src/lib/components/Leaders.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { Leader } from '../../../src/lib/schedule/types';
import { preferLanguages } from '../../prefer-languages';

import Leaders from '../../../src/lib/components/Leaders.svelte';

const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;

afterEach(() => {
	vi.restoreAllMocks();
});

const away: Leader = {
	firstName: 'Stephen',
	lastName: 'Curry',
	teamCode: 'GSW',
	photo: '/away.svg',
	points: 34,
	rebounds: 3,
	assists: 8
};
const home: Leader = {
	firstName: 'LeBron',
	lastName: 'James',
	teamCode: 'LAL',
	photo: '/home.svg',
	points: 29,
	rebounds: 9,
	assists: 7
};

describe('Leaders', () => {
	it("shows each team's top performer with team code, name and stat line", () => {
		const { container } = render(Leaders, { props: { away, home, teamHref } });
		const leaders = [...container.querySelectorAll('.leader')];
		expect(leaders).toHaveLength(2);
		expect(leaders[0].querySelector('.leader-code')?.textContent).toBe('GSW');
		expect(leaders[0].querySelector('.leader-name')?.textContent).toBe('Stephen Curry');
		expect(leaders[0].querySelector('.leader-line')?.textContent?.trim()).toBe(
			'34 PTS · 3 REB · 8 AST'
		);
		expect(leaders[1].querySelector('.leader-line')?.textContent?.trim()).toBe(
			'29 PTS · 9 REB · 7 AST'
		);
	});

	it('shows a placeholder in place of a photo that fails to load and keeps the other photo', async () => {
		render(Leaders, { props: { away, home, teamHref } });
		await fireEvent.error(screen.getByAltText('Stephen Curry'));
		expect(screen.getByRole('img', { name: 'Stephen Curry' }).textContent).toBe('SC');
		expect(screen.getByAltText('LeBron James').tagName).toBe('IMG');
	});

	it('shows the stat line in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		const { container } = render(Leaders, { props: { away, home, teamHref } });
		expect(container.querySelector('.leader-line')?.textContent?.trim()).toBe(
			'34 PTS · 3 REB · 8 AST'
		);
	});

	it('links each team code to the team page and keeps the names plain', () => {
		const { container } = render(Leaders, { props: { away, home, teamHref } });
		const links = [...container.querySelectorAll('a')];
		expect(links.map((a) => [a.textContent, a.getAttribute('href')])).toEqual([
			['GSW', '/team/gsw'],
			['LAL', '/team/lal']
		]);
	});
});

describe('Leaders of a guest team', () => {
	const guest: Leader = {
		...away,
		firstName: 'Casey',
		lastName: 'Marin',
		teamCode: 'HCM',
		photo: null,
		guest: true
	};

	it('shows the guest code as plain text and the league code as a link', () => {
		const { container } = render(Leaders, { props: { away: guest, home, teamHref } });
		const codes = [...container.querySelectorAll('.leader-code')];
		expect(codes[0].textContent).toBe('HCM');
		expect(codes[0].querySelector('a')).toBeNull();
		expect(codes[1].querySelector('a')?.getAttribute('href')).toBe('/team/lal');
	});

	it('shows initials in place of a missing photo', () => {
		render(Leaders, { props: { away: guest, home, teamHref } });
		expect(screen.getByRole('img', { name: 'Casey Marin' }).textContent).toBe('CM');
		expect(screen.getByAltText('LeBron James')).toBeTruthy();
	});
});
