// web/tests/lib/components/TrophyDrawing.test.ts
//
// Tests for the TrophyDrawing component.
//
// Tested:
// - One svg with role img and the title as its accessible name
// - Lines only: no text element, no fill, no shapes other than lines
// - Every drawn element keeps a constant stroke width
//
// What is covered:
// - The one state the drawing has, drawn from a prop
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/TrophyDrawing.test.ts
//
// SEE: web/src/lib/components/TrophyDrawing.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import TrophyDrawing from '../../../src/lib/components/TrophyDrawing.svelte';

describe('TrophyDrawing', () => {
	it('draws one svg with role img and the title as its accessible name', () => {
		const { container } = render(TrophyDrawing, { props: { title: '2027 champions' } });
		expect(container.querySelectorAll('svg')).toHaveLength(1);
		expect(screen.getByRole('img', { name: '2027 champions' })).toBeTruthy();
		expect(container.querySelector('title')?.textContent).toBe('2027 champions');
	});

	it('holds only lines: no text element and no fill attribute', () => {
		const { container } = render(TrophyDrawing, { props: { title: 'x' } });
		expect(container.querySelector('text')).toBeNull();
		const drawn = [...container.querySelectorAll('path, line, polyline')];
		expect(drawn.length).toBeGreaterThan(5);
		for (const element of drawn) expect(element.hasAttribute('fill')).toBe(false);
		expect(container.querySelector('circle, rect, polygon, ellipse, image')).toBeNull();
	});

	it('gives every drawn element a non-scaling stroke', () => {
		const { container } = render(TrophyDrawing, { props: { title: 'x' } });
		for (const element of container.querySelectorAll('path, line, polyline')) {
			expect(element.getAttribute('vector-effect')).toBe('non-scaling-stroke');
		}
	});
});
