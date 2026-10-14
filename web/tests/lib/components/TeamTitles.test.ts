// web/tests/lib/components/TeamTitles.test.ts
//
// Tests for the TeamTitles component.
//
// Tested:
// - One badge per title, in the order given
// - A single title draws a single badge
//
// What is covered:
// - The list; the wrapping is CSS and jsdom does no layout
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/TeamTitles.test.ts
//
// SEE: web/src/lib/components/TeamTitles.svelte
import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import TeamTitles from '../../../src/lib/components/TeamTitles.svelte';

describe('TeamTitles', () => {
	it('draws one badge per title in order', () => {
		const { container } = render(TeamTitles, {
			props: {
				titles: [
					{ text: '2027 NBA Champions', solid: true },
					{ text: '2026 NBA Cup Champions', solid: false },
					{ text: 'West Champions', solid: false }
				]
			}
		});
		const badges = [...container.querySelectorAll('ul > li > .title-badge')];
		expect(badges.map((badge) => badge.textContent)).toEqual([
			'2027 NBA Champions',
			'2026 NBA Cup Champions',
			'West Champions'
		]);
	});

	it('draws a single badge for a single title', () => {
		const { container } = render(TeamTitles, {
			props: { titles: [{ text: 'East Champions', solid: false }] }
		});
		expect(container.querySelectorAll('li').length).toBe(1);
	});
});
