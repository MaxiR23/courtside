// web/tests/strings-are-translated.test.ts
//
// Cross-cutting test: shipped components and routes hold no literal text in their markup.
//
// Tested:
// - The shipped .svelte files are found (the dev-only preview route is excluded)
// - No markup holds a letter outside a { } expression
// - No quoted alt, aria-label, title or placeholder value holds a letter outside a { } expression
// - The attribute scan flags a literal value, so it cannot pass vacuously
//
// What is covered:
// - Happy path (every markup is text-free)
// - Edge cases (the scan cannot pass by finding no files)
// - Known limit: string literals inside <script> and attributes other than alt, aria-label, title and
//   placeholder are not scanned; component tests cover those
//
// Run with: cd web && pnpm exec vitest run tests/strings-are-translated.test.ts
//
// SEE: web/src/lib/components, web/src/routes
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { describe, expect, it } from 'vitest';

const srcDir = join(import.meta.dirname, '../src');
const previewDir = join(srcDir, 'routes', 'preview');

function svelteFiles(dir: string): string[] {
	return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
		const path = join(dir, entry.name);
		if (entry.isDirectory()) return path === previewDir ? [] : svelteFiles(path);
		return entry.name.endsWith('.svelte') ? [path] : [];
	});
}

const files = [
	...svelteFiles(join(srcDir, 'lib', 'components')),
	...svelteFiles(join(srcDir, 'routes'))
];

function markupText(source: string): string {
	return source
		.replace(/<script[\s\S]*?<\/script>/g, '')
		.replace(/<style[\s\S]*?<\/style>/g, '')
		.replace(/<!--[\s\S]*?-->/g, '')
		.replace(/\{[^{}]*\}/g, '')
		.replace(/<[^>]*>/g, '');
}

function attributeText(source: string): string {
	const markup = source
		.replace(/<script[\s\S]*?<\/script>/g, '')
		.replace(/<style[\s\S]*?<\/style>/g, '')
		.replace(/<!--[\s\S]*?-->/g, '');
	const values = [
		...markup.matchAll(/\b(?:alt|aria-label|title|placeholder)=(?:"([^"]*)"|'([^']*)')/g)
	];
	return values.map((m) => (m[1] ?? m[2]).replace(/\{[^{}]*\}/g, '')).join(' ');
}

describe('shipped markup holds no literal text', () => {
	it('finds the base components, the page and the layout', () => {
		const names = files.map((f) => relative(srcDir, f).split(sep).join('/'));
		expect(files.length).toBeGreaterThanOrEqual(8);
		expect(names).toContain('routes/+page.svelte');
		expect(names).toContain('routes/+layout.svelte');
	});

	it('has no letter outside a { } expression', () => {
		for (const file of files) {
			const text = markupText(readFileSync(file, 'utf8')).trim();
			expect(
				text.match(/\p{L}+/u),
				`${relative(srcDir, file)} has literal text: ${text}`
			).toBeNull();
		}
	});

	it('has no letter in a quoted alt, aria-label, title or placeholder value', () => {
		for (const file of files) {
			const text = attributeText(readFileSync(file, 'utf8')).trim();
			expect(
				text.match(/\p{L}+/u),
				`${relative(srcDir, file)} has a literal attribute value: ${text}`
			).toBeNull();
		}
	});

	it('flags a literal attribute value', () => {
		expect(attributeText('<button aria-label="Close">')).toMatch(/\p{L}/u);
		expect(attributeText("<img alt='Logo {x}'>")).toMatch(/\p{L}/u);
		expect(attributeText('<img alt="{label}" title={other}>')).not.toMatch(/\p{L}/u);
	});
});
