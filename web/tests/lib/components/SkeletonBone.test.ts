// web/tests/lib/components/SkeletonBone.test.ts
//
// Tests for the SkeletonBone component.
//
// Tested:
// - Renders one empty bone block
// - Sets no shape of its own unless given one
// - Carries the width, height and aspect ratio it is given
// - Fills with surface, has square corners and reads its shape from the custom properties
//
// What is covered:
// - Its only state, plus each option set and unset
// - Pixels are not measured: jsdom has no layout, so the rules are read from the source
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/SkeletonBone.test.ts
//
// SEE: web/src/lib/components/SkeletonBone.svelte
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import SkeletonBone from '../../../src/lib/components/SkeletonBone.svelte';

function ruleOf(selector: string): Map<string, string> {
	const source = readFileSync(
		join(import.meta.dirname, '../../../src/lib/components/SkeletonBone.svelte'),
		'utf8'
	);
	const style = (source.match(/<style[^>]*>([\s\S]*?)<\/style>/)?.[1] ?? '').replace(
		/\/\*[\s\S]*?\*\//g,
		''
	);
	const declarations = new Map<string, string>();
	for (const match of style.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
		if ((match[1] ?? '').trim() !== selector) continue;
		for (const part of (match[2] ?? '').split(';')) {
			const index = part.indexOf(':');
			if (index > 0) declarations.set(part.slice(0, index).trim(), part.slice(index + 1).trim());
		}
	}
	return declarations;
}

describe('SkeletonBone', () => {
	it('renders one empty bone block', () => {
		const { container } = render(SkeletonBone);
		const bones = container.querySelectorAll('span.bone');
		expect(bones).toHaveLength(1);
		expect(bones[0]?.textContent).toBe('');
	});

	it('sets no shape of its own unless given one', () => {
		const { container } = render(SkeletonBone);
		const style = (container.querySelector('.bone') as HTMLElement).style;
		expect(style.getPropertyValue('--bone-width')).toBe('');
		expect(style.getPropertyValue('--bone-height')).toBe('');
		expect(style.getPropertyValue('--bone-aspect')).toBe('');
	});

	it('carries the width, height and aspect it is given', () => {
		const { container } = render(SkeletonBone, {
			props: {
				width: 'var(--skeleton-short-width)',
				height: 'var(--body-size)',
				aspect: 'var(--video-aspect)'
			}
		});
		const style = (container.querySelector('.bone') as HTMLElement).style;
		expect(style.getPropertyValue('--bone-width')).toBe('var(--skeleton-short-width)');
		expect(style.getPropertyValue('--bone-height')).toBe('var(--body-size)');
		expect(style.getPropertyValue('--bone-aspect')).toBe('var(--video-aspect)');
	});

	it('fills with surface, square corners and reads its shape from the custom properties', () => {
		const rule = ruleOf('.bone');
		expect(rule.get('display')).toBe('block');
		expect(rule.get('background')).toBe('var(--color-surface)');
		expect(rule.get('border-radius')).toBe('var(--radius)');
		expect(rule.get('width')).toBe('var(--bone-width, auto)');
		expect(rule.get('height')).toBe('var(--bone-height, auto)');
		expect(rule.get('aspect-ratio')).toBe('var(--bone-aspect, auto)');
	});
});
