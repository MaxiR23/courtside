// web/tests/lib/components/AllStarLeagueBar.test.ts
//
// Tests for the AllStarLeagueBar component.
//
// Tested:
// - Two halves colored with the primary and secondary colors of the league team
// - A neutral color for a color the feed does not send
// - The bar is hidden from assistive technology
//
// What is covered:
// - Each state the bar shows, drawn from props
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/AllStarLeagueBar.test.ts
//
// SEE: web/src/lib/components/AllStarLeagueBar.svelte
import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import AllStarLeagueBar from '../../../src/lib/components/AllStarLeagueBar.svelte';

const halves = (container: HTMLElement) =>
	[...container.querySelectorAll('.half')].map((h) => (h as HTMLElement).style.backgroundColor);

describe('AllStarLeagueBar', () => {
	it('colors the two halves with the league colors', () => {
		const { container } = render(AllStarLeagueBar, {
			props: { league: { code: 'HBR', primary: '#1d428a', secondary: '#ffc72c' } }
		});
		expect(halves(container)).toEqual(['rgb(29, 66, 138)', 'rgb(255, 199, 44)']);
		expect(container.querySelector('.league-bar')?.getAttribute('aria-hidden')).toBe('true');
	});

	it('uses a neutral color for a missing color', () => {
		const { container } = render(AllStarLeagueBar, {
			props: { league: { code: 'HBR', primary: null, secondary: '#ffc72c' } }
		});
		expect(halves(container)[0]).toBe('var(--color-bar-neutral)');
	});
});
