// web/tests/lib/components/AllStarSigla.test.ts
//
// Tests for the AllStarSigla component.
//
// Tested:
// - The team code in an outlined box, in both sizes
// - No link for a guest team
// - The name of a guest team that has no code
// - "—" for a slot still to be determined
// - The winner flag adds the accent border class
//
// What is covered:
// - Each state the box shows, drawn from props
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/AllStarSigla.test.ts
//
// SEE: web/src/lib/components/AllStarSigla.svelte
import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import AllStarSigla from '../../../src/lib/components/AllStarSigla.svelte';

const team = { code: 'STR', name: 'Team Stripes', city: null, guest: true };

describe('AllStarSigla', () => {
	it('shows the code in a box of the given size', () => {
		const { container } = render(AllStarSigla, { props: { team, size: 'large' } });
		const box = container.querySelector('.sigla');
		expect(box?.textContent?.trim()).toBe('STR');
		expect(box?.classList.contains('large')).toBe(true);
		const small = render(AllStarSigla, { props: { team, size: 'small' } });
		expect(small.container.querySelector('.sigla')?.classList.contains('small')).toBe(true);
	});

	it('never links a guest team', () => {
		const { container } = render(AllStarSigla, { props: { team, size: 'large' } });
		expect(container.querySelector('a')).toBeNull();
	});

	it('shows the name of a guest team with no code', () => {
		const { container } = render(AllStarSigla, {
			props: { team: { ...team, code: null }, size: 'small' }
		});
		expect(container.querySelector('.sigla')?.textContent?.trim()).toBe('Team Stripes');
	});

	it('shows a dash for a slot to be determined', () => {
		const { container } = render(AllStarSigla, { props: { team: null, size: 'large' } });
		expect(container.querySelector('.sigla')?.textContent?.trim()).toBe('—');
	});

	it('adds the winner class only when asked', () => {
		const plain = render(AllStarSigla, { props: { team, size: 'large' } });
		expect(plain.container.querySelector('.sigla')?.classList.contains('winner')).toBe(false);
		const won = render(AllStarSigla, { props: { team, size: 'large', winner: true } });
		expect(won.container.querySelector('.sigla')?.classList.contains('winner')).toBe(true);
	});
});
