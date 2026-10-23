// web/tests/lib/components/TeamLeaders.test.ts
//
// Tests for the TeamLeaders component.
//
// Tested:
// - One card per leader with the label, value, name, line and avatar
// - Initials for a leader with no photo
// - The photo is a cutout before the texts, with initials inside it for a leader with no photo
// - The mobile class with the mobile layout, and the sizes taken from tokens (source check)
// - Each card links to its player page, with no nested interactive element
//
// What is covered:
// - A full section and a section with one card, desktop and mobile
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/TeamLeaders.test.ts
//
// SEE: web/src/lib/components/TeamLeaders.svelte
import type { ResolvedPathname } from '$app/types';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import TeamLeaders from '../../../src/lib/components/TeamLeaders.svelte';
import type { LeadersSection } from '../../../src/lib/team/types';

const source = (file: string) =>
	readFileSync(join(__dirname, '..', '..', '..', 'src', 'lib', 'components', file), 'utf8');

const playerHref = (id: string) => `/player/${id}` as ResolvedPathname;

const leaders: LeadersSection = {
	meta: '2025-26 · per game',
	cards: [
		{
			playerId: 'p-sga',
			label: 'Points',
			value: '31.8',
			name: 'Shai Gilgeous-Alexander',
			line: '#2 · Guard',
			photo: 'https://example.com/sga.png'
		},
		{
			playerId: 'p-holmgren',
			label: 'Rebounds',
			value: '8.9',
			name: 'Chet Holmgren',
			line: 'Forward-Center',
			photo: null
		}
	]
};

describe('TeamLeaders', () => {
	it('shows one card per leader with its label, value, name and line', () => {
		render(TeamLeaders, { props: { leaders, layout: 'desktop', playerHref } });
		expect(screen.getAllByRole('listitem')).toHaveLength(2);
		for (const text of [
			'Points',
			'31.8',
			'Shai Gilgeous-Alexander',
			'#2 · Guard',
			'Rebounds',
			'8.9',
			'Chet Holmgren',
			'Forward-Center'
		]) {
			expect(screen.getByText(text)).toBeTruthy();
		}
	});

	it('shows the photo, or initials with none', () => {
		render(TeamLeaders, { props: { leaders, layout: 'desktop', playerHref } });
		expect(screen.getByRole('img', { name: 'Shai Gilgeous-Alexander' }).getAttribute('src')).toBe(
			'https://example.com/sga.png'
		);
		expect(screen.getByRole('img', { name: 'Chet Holmgren' }).textContent).toBe('CH');
	});

	it('links each card to its player page, with nothing interactive inside', () => {
		const { container } = render(TeamLeaders, {
			props: { leaders, layout: 'desktop', playerHref }
		});
		expect(screen.getAllByRole('link').map((a) => a.getAttribute('href'))).toEqual([
			'/player/p-sga',
			'/player/p-holmgren'
		]);
		expect(container.querySelectorAll('a a, button a, a button')).toHaveLength(0);
	});

	it('shows a single card', () => {
		render(TeamLeaders, {
			props: { leaders: { ...leaders, cards: [leaders.cards[0]!] }, layout: 'desktop', playerHref }
		});
		expect(screen.getAllByRole('listitem')).toHaveLength(1);
	});

	it('draws the photo as a cutout before the texts, so it sits behind them', () => {
		const { container } = render(TeamLeaders, {
			props: { leaders, layout: 'desktop', playerHref }
		});
		const cards = container.querySelectorAll('.card');
		expect(cards).toHaveLength(2);
		for (const card of cards) {
			expect(card.firstElementChild?.classList.contains('cutout')).toBe(true);
			expect(card.querySelector('.cutout .avatar.team-leader')).not.toBeNull();
			expect(card.querySelector('.text')).not.toBeNull();
		}
		expect(cards[0]!.querySelector('.cutout img')?.getAttribute('src')).toBe(
			'https://example.com/sga.png'
		);
	});

	it('shows initials in the cutout for a leader with no photo', () => {
		const { container } = render(TeamLeaders, {
			props: { leaders, layout: 'desktop', playerHref }
		});
		const placeholder = container.querySelector('.cutout [role="img"]');
		expect(placeholder?.getAttribute('aria-label')).toBe('Chet Holmgren');
		expect(placeholder?.textContent).toBe('CH');
	});

	it('adds the mobile class with the mobile layout', () => {
		const mobile = render(TeamLeaders, { props: { leaders, layout: 'mobile', playerHref } });
		for (const card of mobile.container.querySelectorAll('.card')) {
			expect(card.classList.contains('mobile')).toBe(true);
		}
		mobile.unmount();
		const desktop = render(TeamLeaders, { props: { leaders, layout: 'desktop', playerHref } });
		expect(desktop.container.querySelectorAll('.card.mobile')).toHaveLength(0);
	});

	it('takes the cutout, its filter, the value and the min-heights from tokens', () => {
		const css = source('TeamLeaders.svelte');
		for (const part of [
			'min-height: var(--team-leader-min-height)',
			'min-height: var(--team-leader-min-height-mobile)',
			'width: var(--team-leader-cutout-width)',
			'right: 0',
			'bottom: 0',
			'font-weight: var(--font-weight-semibold)',
			'font-size: var(--team-leader-value-size)'
		]) {
			expect(css).toContain(part);
		}
		const avatar = source('PlayerAvatar.svelte');
		expect(avatar).toContain('filter: var(--hero-cutout-filter)');
		expect(avatar).toContain('object-position: bottom right');
	});
});
