// web/tests/lib/components/SiteFooter.test.ts
//
// Tests for the SiteFooter component.
//
// Tested:
// - Shows the brand name and the not-affiliated line
// - Shows the not-affiliated line in Spanish with a Spanish browser preference
// - Keeps the brand name on the footer's own size token
//
// What is covered:
// - Its only state, in English and in Spanish
// - The brand name's size token, read from the component source (jsdom does not lay out)
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/SiteFooter.test.ts
//
// SEE: web/src/lib/components/SiteFooter.svelte
import { render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { preferLanguages } from '../../prefer-languages';

import SiteFooter from '../../../src/lib/components/SiteFooter.svelte';

type Declaration = { property: string; value: string };
type Rule = { selectors: string[]; declarations: Declaration[] };

function styleOf(source: string): string {
	const match = source.match(/<style[^>]*>([\s\S]*?)<\/style>/);
	return (match?.[1] ?? '').replace(/\/\*[\s\S]*?\*\//g, '');
}

function rulesOf(style: string): Rule[] {
	const rules: Rule[] = [];
	for (const match of style.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
		const declarations = (match[2] ?? '')
			.split(';')
			.map((part) => part.trim())
			.filter((part) => part.includes(':'))
			.map((part) => {
				const index = part.indexOf(':');
				return {
					property: part.slice(0, index).trim().toLowerCase(),
					value: part.slice(index + 1).trim()
				};
			});
		const selectors = (match[1] ?? '').split(',').map((selector) => selector.trim());
		rules.push({ selectors, declarations });
	}
	return rules;
}

/** Whether a rule for the selector sets the property to the value. */
function sets(css: string, selector: string, property: string, value: string): boolean {
	return rulesOf(css).some(
		(rule) =>
			rule.selectors.includes(selector) &&
			rule.declarations.some((d) => d.property === property && d.value === value)
	);
}

afterEach(() => {
	vi.restoreAllMocks();
});

describe('SiteFooter', () => {
	it('shows the brand name and the not-affiliated line', () => {
		render(SiteFooter);
		expect(screen.getByText('Courtside')).toBeTruthy();
		expect(
			screen.getByText(
				'Unofficial site, not affiliated with the NBA or its teams. Names and logos belong to their owners.'
			)
		).toBeTruthy();
	});

	it('shows the not-affiliated line in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		render(SiteFooter);
		expect(
			screen.getByText(
				'Sitio no oficial. Sin afiliación con la NBA ni sus equipos. Nombres y logos son propiedad de sus dueños.'
			)
		).toBeTruthy();
	});

	it("keeps the brand name on the footer's own size token", () => {
		const source = readFileSync(
			join(import.meta.dirname, '../../../src/lib/components/SiteFooter.svelte'),
			'utf8'
		);
		expect(sets(styleOf(source), '.name', 'font-size', 'var(--footer-brand-size)')).toBe(true);
		expect(source).not.toContain('var(--brand-size)');
	});
});
