// web/tests/lib/components/AllStarTop5.test.ts
//
// Tests for the AllStarTop5 component.
//
// Tested:
// - One linked row per Top 5 entry, in the order the feed sends them, linking to the player
// - Rank #1 in accent, the team line, the points and the line
// - Initials without a photo
// - A league bar only for a player with a league team
// - The mobile avatar size
//
// What is covered:
// - Each state a row shows, drawn from the recorded feeds
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/AllStarTop5.test.ts
//
// SEE: web/src/lib/components/AllStarTop5.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import AllStarTop5 from '../../../src/lib/components/AllStarTop5.svelte';
import { playerHref, viewOf } from '../all-star/views';

const rows = () => viewOf('after').details.g4.top5;
const show = (layout: 'desktop' | 'mobile' = 'desktop', list = rows()) =>
	render(AllStarTop5, { props: { rows: list, layout, playerHref } });

describe('AllStarTop5', () => {
	it('draws one row per entry in feed order, each linking to the player', () => {
		const { container } = show();
		const links = [...container.querySelectorAll('a.row')];
		expect(links.map((a) => a.getAttribute('href'))).toEqual([
			'/player/1001',
			'/player/2001',
			'/player/2002',
			'/player/1002'
		]);
		expect([...container.querySelectorAll('.name')].map((n) => n.textContent)).toEqual([
			'Ada Example',
			'Cy Placeholder',
			'Dee Invented',
			'Ben Sample'
		]);
	});

	it('draws #1 in accent and the other ranks plain', () => {
		const { container } = show();
		const ranks = [...container.querySelectorAll('.rank')];
		expect(ranks.map((r) => r.textContent)).toEqual(['#1', '#2', '#3', '#4']);
		expect(ranks.map((r) => r.classList.contains('top'))).toEqual([true, false, false, false]);
	});

	it('shows the team line, the points and the line', () => {
		const { container } = show();
		expect(container.querySelector('.team-line')?.textContent).toBe('Team Stripes · HBR');
		expect(container.querySelector('.points')?.textContent).toBe('16');
		expect(container.querySelector('.line')?.textContent).toBe('PTS · 4 REB · 3 AST');
	});

	it('shows initials without a photo', () => {
		show();
		expect(screen.getByRole('img', { name: 'Dee Invented' }).textContent).toBe('DI');
	});

	it('draws a league bar only for a player with a league team', () => {
		const { container } = render(AllStarTop5, {
			props: { rows: viewOf('live').details.s2.top5, layout: 'desktop', playerHref }
		});
		const photos = [...container.querySelectorAll('.photo')];
		expect(photos[0].querySelector('.league-bar')).toBeNull(); // no league team
		expect(photos[1].querySelector('.league-bar')).not.toBeNull();
	});

	it('uses the mobile avatar size on mobile', () => {
		const { container } = show('mobile');
		expect(container.querySelector('.avatar')?.classList.contains('allstar-top5-mobile')).toBe(
			true
		);
		const desktop = show('desktop');
		expect(desktop.container.querySelector('.avatar')?.classList.contains('allstar-top5')).toBe(
			true
		);
	});
});
