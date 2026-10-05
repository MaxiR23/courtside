// web/tests/components-use-tokens.test.ts
//
// Cross-cutting test: base components style themselves with design tokens only.
//
// Tested:
// - The base components under web/src/lib/components are found
// - No component style holds a raw color, length, duration, easing, font family or font weight
//
// What is covered:
// - Happy path (every style block is token-only)
// - Edge cases (the scan cannot pass by finding no component)
//
// Run with: cd web && pnpm exec vitest run tests/components-use-tokens.test.ts
//
// SEE: web/src/lib/components
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const componentsDir = join(import.meta.dirname, '../src/lib/components');
const files = readdirSync(componentsDir).filter((f) => f.endsWith('.svelte'));

const forbidden: Record<string, RegExp> = {
	'hex color': /#[0-9a-fA-F]{3,8}\b/,
	'color function': /\b(rgba?|hsla?|color-mix)\(/,
	'length with a unit': /\d*\.?\d+(px|em|rem|vw|vh)\b/,
	duration: /\b\d*\.?\d+m?s\b/,
	easing: /cubic-bezier\(/,
	'font name': /Barlow/,
	'numeric font weight': /font-weight\s*:\s*\d/
};

function styleOf(source: string): string {
	const match = source.match(/<style[^>]*>([\s\S]*?)<\/style>/);
	return (match?.[1] ?? '').replace(/\/\*[\s\S]*?\*\//g, '').replace(/var\(--[\w-]+\)/g, '');
}

describe('base components use tokens only', () => {
	it('finds the base components to check', () => {
		expect(files.length).toBeGreaterThanOrEqual(6);
	});

	it('holds no raw color, length, duration, easing, font family or font weight', () => {
		for (const file of files) {
			const style = styleOf(readFileSync(join(componentsDir, file), 'utf8'));
			for (const [kind, pattern] of Object.entries(forbidden)) {
				const found = style.match(pattern);
				expect(found, `${file} has a raw ${kind}: ${found?.[0]}`).toBeNull();
			}
		}
	});
});
