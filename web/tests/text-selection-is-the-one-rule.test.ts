// web/tests/text-selection-is-the-one-rule.test.ts
//
// Guard test: text selection is set in one place.
//
// Tested:
// - Only web/src/lib/styles/base.css declares user-select
// - That rule's selectors are exactly button, select and .unselectable
// - The matcher flags every way to set user-select and passes look-alikes
//
// What is covered:
// - Happy path (only base.css declares it)
// - Edge cases (style directive, JS property, prefixed property, look-alikes)
// - Error case (a stray declaration is flagged with its file)
// - The scan cannot pass on an empty file list
//
// Run with: cd web && pnpm exec vitest run tests/text-selection-is-the-one-rule.test.ts
//
// SEE: web/src/lib/styles/base.css
import { readdirSync, readFileSync } from 'node:fs';
import { join, sep } from 'node:path';
import { describe, expect, it } from 'vitest';

const srcDir = join(import.meta.dirname, '../src');
const rulePath = join('lib', 'styles', 'base.css');
const paraglideDir = join('lib', 'paraglide');

const files = readdirSync(srcDir, { recursive: true, encoding: 'utf8' }).filter(
	(path) => /\.(svelte|css|ts|js|html)$/.test(path) && !path.startsWith(paraglideDir + sep)
);

function declaresUserSelect(text: string): boolean {
	return /user-select\s*:|style:user-select|userSelect/.test(text);
}

describe('text selection rule', () => {
	it('finds the files to scan, so the scan cannot pass on an empty list', () => {
		expect(files.length).toBeGreaterThan(100);
		expect(files).toContain(rulePath);
		expect(files).toContain(join('lib', 'components', 'CupBracket.svelte'));
	});

	it('flags every way to set user-select and passes look-alikes', () => {
		expect(declaresUserSelect('user-select: none;')).toBe(true);
		expect(declaresUserSelect('-webkit-user-select:none')).toBe(true);
		expect(declaresUserSelect('style:user-select="none"')).toBe(true);
		expect(declaresUserSelect("el.style.userSelect = 'none'")).toBe(true);
		expect(declaresUserSelect('<select class="select">')).toBe(false);
		expect(declaresUserSelect('.select { height: 0 }')).toBe(false);
		expect(declaresUserSelect('onselect={go}')).toBe(false);
	});

	it('holds the one rule in base.css: button, select and .unselectable are not selectable', () => {
		const css = readFileSync(join(srcDir, rulePath), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
		const blocks = [...css.matchAll(/([^{}]+)\{([^{}]*user-select[^{}]*)\}/g)];
		expect(blocks).toHaveLength(1);
		const [, selectors, body] = blocks[0];
		expect(selectors.split(',').map((s) => s.trim())).toEqual([
			'button',
			'select',
			'.unselectable'
		]);
		const declarations = body
			.split(';')
			.map((d) => d.trim())
			.filter(Boolean);
		expect(declarations).toEqual(['-webkit-user-select: none', 'user-select: none']);
	});

	it('declares user-select nowhere else in web/src', () => {
		for (const file of files.filter((f) => f !== rulePath)) {
			const text = readFileSync(join(srcDir, file), 'utf8');
			expect(declaresUserSelect(text), `${file} declares user-select`).toBe(false);
		}
	});
});
