// web/tests/lib/components/InfoCell.test.ts
//
// Tests for the InfoCell component.
//
// Tested:
// - The label, the value and the sub line, in order
// - No sub line when sub is null or absent
// - The label goes through Kicker
// - Children take the place of the value
// - The detail size by default, hero and record when asked; strong and numeric only when set
// - A dt and dd pair with term, spans without it
//
// What is covered:
// - Every state and option; there is no interaction
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/InfoCell.test.ts
//
// SEE: web/src/lib/components/InfoCell.svelte
import { render, screen } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { describe, expect, it } from 'vitest';

import InfoCell from '../../../src/lib/components/InfoCell.svelte';

const swatches = createRawSnippet(() => ({
	render: () => '<ul class="swatches"><li>#fff</li></ul>'
}));

describe('InfoCell', () => {
	it('shows the label, the value and the sub line in order', () => {
		const { container } = render(InfoCell, {
			props: { label: 'Height', value: '6\'6"', sub: '198 cm' }
		});
		expect(container.querySelector('.cell')?.textContent?.replace(/\s+/g, ' ').trim()).toBe(
			'Height 6\'6" 198 cm'
		);
	});

	it('draws no sub line when sub is null or absent', () => {
		const withNull = render(InfoCell, { props: { label: 'A', value: '1', sub: null } });
		expect(withNull.container.querySelector('.sub')).toBeNull();
		withNull.unmount();
		const absent = render(InfoCell, { props: { label: 'A', value: '1' } });
		expect(absent.container.querySelector('.sub')).toBeNull();
	});

	it('renders its label through Kicker', () => {
		const { container } = render(InfoCell, { props: { label: 'Height', value: '1' } });
		const kicker = container.querySelector('.kicker');
		expect(kicker?.textContent).toBe('Height');
		expect(kicker?.classList.contains('accent')).toBe(true);
	});

	it('renders the children in place of the value', () => {
		const { container } = render(InfoCell, { props: { label: 'Team colors', children: swatches } });
		expect(container.querySelector('.cell .swatches')).not.toBeNull();
		expect(container.querySelector('.value')).toBeNull();
	});

	it('uses the detail size by default, and hero or record when asked', () => {
		const detail = render(InfoCell, { props: { label: 'A', value: '1' } });
		const value = detail.container.querySelector('.value');
		expect(value?.classList.contains('detail')).toBe(true);
		expect(value?.classList.contains('hero')).toBe(false);
		detail.unmount();
		for (const size of ['hero', 'record'] as const) {
			const { container, unmount } = render(InfoCell, { props: { label: 'A', value: '1', size } });
			expect(container.querySelector('.value')?.classList.contains(size)).toBe(true);
			unmount();
		}
	});

	it('adds strong and numeric only when set', () => {
		const plain = render(InfoCell, { props: { label: 'A', value: '1' } });
		const el = plain.container.querySelector('.value');
		expect(el?.classList.contains('strong')).toBe(false);
		expect(el?.classList.contains('numeric')).toBe(false);
		plain.unmount();
		const set = render(InfoCell, {
			props: { label: 'A', value: '1', strong: true, numeric: true }
		});
		const both = set.container.querySelector('.value');
		expect(both?.classList.contains('strong')).toBe(true);
		expect(both?.classList.contains('numeric')).toBe(true);
	});

	it('renders a dt and dd pair with term, and spans without it', () => {
		const { container } = render(InfoCell, {
			props: { label: 'Height', value: '6\'6"', sub: '198 cm', term: true },
			target: document.body.appendChild(document.createElement('dl'))
		});
		expect(screen.getByRole('term').textContent).toBe('Height');
		expect(screen.getAllByRole('definition').map((d) => d.textContent)).toEqual([
			'6\'6"',
			'198 cm'
		]);
		expect(container).toBeTruthy();
	});

	it('renders spans without term', () => {
		const { container } = render(InfoCell, { props: { label: 'A', value: '1', sub: 's' } });
		expect([...container.querySelectorAll('.cell > *')].map((e) => e.tagName)).toEqual([
			'SPAN',
			'SPAN',
			'SPAN'
		]);
	});
});
