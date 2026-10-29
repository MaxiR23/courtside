// web/tests/lib/components/Kicker.test.ts
//
// Tests for the Kicker component.
//
// Tested:
// - Shows the given text, or its children in place of the text
// - Draws the accent tone by default, the muted tone when asked, and no tone with inherit
// - Renders as a span by default, and as a dt, an h3 or a thead when asked
// - Wraps its children with no box of its own when contents is set
// - Holds the label declarations once, in its own rules
//
// What is covered:
// - Every state and option; there is no interaction
// - Pixels are not measured: jsdom has no layout, so the rules are read from the source
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/Kicker.test.ts
//
// SEE: web/src/lib/components/Kicker.svelte
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { render, screen } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { describe, expect, it } from 'vitest';

import Kicker from '../../../src/lib/components/Kicker.svelte';

const inside = createRawSnippet(() => ({ render: () => '<span class="inner">Inside</span>' }));

function ruleOf(selector: string): Map<string, string> {
	const source = readFileSync(
		join(import.meta.dirname, '../../../src/lib/components/Kicker.svelte'),
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

describe('Kicker', () => {
	it('shows the given text', () => {
		render(Kicker, { props: { text: '10:30 PM · Chase Center' } });
		expect(screen.getByText('10:30 PM · Chase Center')).toBeTruthy();
	});

	it('renders its children in place of the text', () => {
		const { container } = render(Kicker, { props: { text: 'Ignored', children: inside } });
		expect(container.querySelector('.kicker .inner')?.textContent).toBe('Inside');
		expect(screen.queryByText('Ignored')).toBeNull();
	});

	it('draws the accent tone by default', () => {
		render(Kicker, { props: { text: 'Label' } });
		expect(screen.getByText('Label').classList.contains('accent')).toBe(true);
	});

	it('draws the muted tone when asked', () => {
		render(Kicker, { props: { text: 'Label', tone: 'muted' } });
		const el = screen.getByText('Label');
		expect(el.classList.contains('muted')).toBe(true);
		expect(el.classList.contains('accent')).toBe(false);
	});

	it('leaves the color to the surrounding text with the inherit tone', () => {
		render(Kicker, { props: { text: 'Label', tone: 'inherit' } });
		const el = screen.getByText('Label');
		expect(el.classList.contains('accent')).toBe(false);
		expect(el.classList.contains('muted')).toBe(false);
	});

	it('renders as a span by default, and as a dt, an h3 or a thead when asked', () => {
		render(Kicker, { props: { text: 'Label' } });
		expect(screen.getByText('Label').tagName).toBe('SPAN');
		for (const as of ['dt', 'h3', 'div'] as const) {
			const { container } = render(Kicker, { props: { text: as, as } });
			expect(container.querySelector(as)?.classList.contains('kicker')).toBe(true);
		}
		const table = document.createElement('table');
		document.body.append(table);
		render(Kicker, { target: table, props: { as: 'thead', children: inside } });
		expect(table.querySelector('thead.kicker')).not.toBeNull();
		table.remove();
	});

	it('wraps its children with no box of its own when contents is set', () => {
		const { container } = render(Kicker, {
			props: { as: 'div', contents: true, children: inside }
		});
		const el = container.querySelector('.kicker');
		expect(el?.classList.contains('contents')).toBe(true);
		expect(el?.querySelector('.inner')).not.toBeNull();
	});

	it('does not set contents by default', () => {
		render(Kicker, { props: { text: 'Label' } });
		expect(screen.getByText('Label').classList.contains('contents')).toBe(false);
	});

	it('holds the label declarations in .kicker and one color per tone', () => {
		const kicker = ruleOf('.kicker');
		expect(kicker.get('font-size')).toBe('var(--label-size)');
		expect(kicker.get('letter-spacing')).toBe('var(--label-letter-spacing)');
		expect(kicker.get('text-transform')).toBe('uppercase');
		expect(kicker.get('margin')).toBe('0');
		expect(ruleOf('.accent').get('color')).toBe('var(--color-accent-light)');
		expect(ruleOf('.muted').get('color')).toBe('var(--color-muted)');
		expect(ruleOf('.contents').get('display')).toBe('contents');
	});
});
