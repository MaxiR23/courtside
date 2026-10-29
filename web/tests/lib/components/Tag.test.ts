// web/tests/lib/components/Tag.test.ts
//
// Tests for the Tag component.
//
// Tested:
// - Shows the given text, or its children in place of the text
// - Draws the outline variant by default, and the accent, solid, muted and live variants when asked
// - Wraps its box in an inherit-tone Kicker with no box of its own, or renders the bare box without the label
// - Sets the size, tracking, padding, border color and text color as custom properties, and none when not given
// - Truncates, keeps one line, wraps, takes the heading font and drops the border when asked
// - Holds the box rule, the solid rule and the live rule once, in its own source, and no rule holds the label set
// - Is plain text: no link or button unless a child brings one
//
// What is covered:
// - Every state and option; there is no interaction
// - Pixels are not measured: jsdom has no layout, so the rules are read from the source
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/Tag.test.ts
//
// SEE: web/src/lib/components/Tag.svelte
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { render, screen } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { describe, expect, it } from 'vitest';

import Tag from '../../../src/lib/components/Tag.svelte';

const inside = createRawSnippet(() => ({ render: () => '<a class="inner" href="/x">Inside</a>' }));

function ruleOf(selector: string): Map<string, string> {
	const source = readFileSync(
		join(import.meta.dirname, '../../../src/lib/components/Tag.svelte'),
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

function tagOf(container: HTMLElement): HTMLElement {
	const tag = container.querySelector<HTMLElement>('.tag');
	if (!tag) throw new Error('no .tag rendered');
	return tag;
}

describe('Tag', () => {
	it('shows the given text', () => {
		render(Tag, { props: { text: 'Out' } });
		expect(screen.getByText('Out')).toBeTruthy();
	});

	it('renders its children in place of the text', () => {
		const { container } = render(Tag, { props: { text: 'Ignored', children: inside } });
		expect(container.querySelector('.tag .inner')?.textContent).toBe('Inside');
		expect(screen.queryByText('Ignored')).toBeNull();
	});

	it('draws the outline variant by default', () => {
		const { container } = render(Tag, { props: { text: 'x' } });
		expect(tagOf(container).classList.contains('outline')).toBe(true);
	});

	it.each(['accent', 'solid', 'muted', 'live'] as const)(
		'draws the %s variant when asked',
		(variant) => {
			const { container } = render(Tag, { props: { text: 'x', variant } });
			const tag = tagOf(container);
			expect(tag.classList.contains(variant)).toBe(true);
			expect(tag.classList.contains('outline')).toBe(false);
		}
	);

	it('wraps the box in an inherit-tone Kicker with no box of its own', () => {
		const { container } = render(Tag, { props: { text: 'x', variant: 'accent' } });
		const kicker = tagOf(container).parentElement;
		expect(kicker?.classList.contains('kicker')).toBe(true);
		expect(kicker?.classList.contains('contents')).toBe(true);
		expect(kicker?.classList.contains('inherit')).toBe(true);
		expect(kicker?.classList.contains('accent')).toBe(false);
		expect(kicker?.classList.contains('muted')).toBe(false);
	});

	it('renders the bare box without the label type', () => {
		const { container } = render(Tag, { props: { text: 'x', label: false } });
		expect(container.querySelector('.kicker')).toBeNull();
		expect(tagOf(container).parentElement).toBe(container);
	});

	it('sets the size, tracking, padding, border color and text color on the box', () => {
		const { container } = render(Tag, {
			props: {
				text: 'x',
				size: 'var(--injury-tag-size)',
				tracking: 'var(--label-letter-spacing)',
				padding: 'var(--hairline) var(--bracket-tick-size)',
				borderColor: 'var(--playoffs-tag-border)',
				color: 'var(--color-ink)'
			}
		});
		const style = tagOf(container).style;
		expect(style.getPropertyValue('--tag-size')).toBe('var(--injury-tag-size)');
		expect(style.getPropertyValue('--tag-tracking')).toBe('var(--label-letter-spacing)');
		expect(style.getPropertyValue('--tag-inset')).toBe('var(--hairline) var(--bracket-tick-size)');
		expect(style.getPropertyValue('--tag-border')).toBe('var(--playoffs-tag-border)');
		expect(style.getPropertyValue('--tag-color')).toBe('var(--color-ink)');
	});

	it('sets none of the custom properties when they are not given', () => {
		const { container } = render(Tag, { props: { text: 'x' } });
		expect(tagOf(container).getAttribute('style')).toBeNull();
	});

	it('truncates, keeps one line, wraps, takes the heading font and drops the border when asked', () => {
		const { container } = render(Tag, {
			props: { text: 'x', truncate: true, wrap: 'nowrap', heading: true, borderless: true }
		});
		const tag = tagOf(container);
		for (const name of ['truncate', 'nowrap', 'heading', 'borderless']) {
			expect(tag.classList.contains(name), name).toBe(true);
		}
		expect(tag.classList.contains('normal')).toBe(false);
	});

	it('wraps at spaces when asked', () => {
		const { container } = render(Tag, { props: { text: 'x', wrap: 'normal' } });
		const tag = tagOf(container);
		expect(tag.classList.contains('normal')).toBe(true);
		expect(tag.classList.contains('nowrap')).toBe(false);
		expect(tag.classList.contains('truncate')).toBe(false);
	});

	it('holds the box, solid and live rules in its own source', () => {
		const box = ruleOf('.tag');
		expect(box.get('padding')).toBe('var(--tag-inset, var(--tag-padding))');
		expect(box.get('border')).toBe('var(--hairline) solid var(--tag-border, var(--color-divider))');
		expect(box.get('border-radius')).toBe('var(--radius)');

		const solid = ruleOf('.solid');
		expect(solid.get('background')).toBe('var(--color-accent)');
		expect(solid.get('border-color')).toBe('var(--color-accent)');
		expect(solid.get('color')).toBe('var(--color-bg)');

		const live = ruleOf('.live');
		expect(live.get('font-size')).toBe('var(--live-badge-size)');
		expect(live.get('letter-spacing')).toBe('var(--label-letter-spacing)');
	});

	it('holds no rule with the whole label set: that lives in Kicker', () => {
		for (const selector of ['.tag', '.accent', '.solid', '.muted', '.live']) {
			const rule = ruleOf(selector);
			const whole =
				rule.get('font-size') === 'var(--label-size)' &&
				rule.get('letter-spacing') === 'var(--label-letter-spacing)' &&
				rule.get('text-transform') === 'uppercase';
			expect(whole, selector).toBe(false);
		}
	});

	it('is plain text: no link or button unless a child brings one', () => {
		const { container } = render(Tag, { props: { text: 'x' } });
		expect(container.querySelector('a, button')).toBeNull();
	});
});
