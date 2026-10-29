// web/tests/lib/components/PageContainer.test.ts
//
// Tests for the PageContainer component.
//
// Tested:
// - Renders its content inside the page container
// - Sets the content width, the centering and the side padding
// - Keeps the side padding token unless given another
// - Drops the bottom padding only when flush at the bottom
// - Draws the top hairline only with a divider
//
// What is covered:
// - Its only state and its three options
// - Pixels are not measured: jsdom has no layout, so the rules are read from the source
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PageContainer.test.ts
//
// SEE: web/src/lib/components/PageContainer.svelte
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { render, screen } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { describe, expect, it } from 'vitest';

import PageContainer from '../../../src/lib/components/PageContainer.svelte';

type Options = { sidePadding?: string; flushBottom?: boolean; divider?: boolean };

function renderContainer(options: Options = {}) {
	return render(PageContainer, {
		props: {
			...options,
			children: createRawSnippet(() => ({ render: () => '<p>Inside</p>' }))
		}
	});
}

function ruleOf(selector: string): Map<string, string> {
	const source = readFileSync(
		join(import.meta.dirname, '../../../src/lib/components/PageContainer.svelte'),
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

describe('PageContainer', () => {
	it('renders its content inside the page container', () => {
		const { container } = renderContainer();
		const box = container.querySelector('.page-container');
		expect(box?.contains(screen.getByText('Inside'))).toBe(true);
	});

	it('sets the content width, the centering and the side padding', () => {
		const rule = ruleOf('.page-container');
		expect(rule.get('max-width')).toBe('var(--content-max-width)');
		expect(rule.get('margin')).toBe('0 auto');
		expect(rule.get('padding')).toBe('var(--side-padding)');
		expect(rule.get('padding-inline')).toBe('var(--page-side-padding, var(--side-padding))');
	});

	it('keeps the side padding token unless given another', () => {
		const plain = renderContainer().container.querySelector<HTMLElement>('.page-container');
		expect(plain?.style.getPropertyValue('--page-side-padding')).toBe('');
		const other = renderContainer({
			sidePadding: 'var(--allstar-side-padding-mobile)'
		}).container.querySelector<HTMLElement>('.page-container');
		expect(other?.style.getPropertyValue('--page-side-padding')).toBe(
			'var(--allstar-side-padding-mobile)'
		);
	});

	it('drops the bottom padding only when flush at the bottom', () => {
		const plain = renderContainer().container.querySelector('.page-container');
		expect(plain?.classList.contains('flush-bottom')).toBe(false);
		const flush = renderContainer({ flushBottom: true }).container.querySelector('.page-container');
		expect(flush?.classList.contains('flush-bottom')).toBe(true);
		expect(ruleOf('.flush-bottom').get('padding-bottom')).toBe('0');
	});

	it('draws the top hairline only with a divider', () => {
		const plain = renderContainer().container.querySelector('.page-container');
		expect(plain?.classList.contains('divider')).toBe(false);
		const divided = renderContainer({ divider: true }).container.querySelector('.page-container');
		expect(divided?.classList.contains('divider')).toBe(true);
		expect(ruleOf('.divider').get('border-top')).toBe('var(--hairline) solid var(--color-divider)');
	});
});
