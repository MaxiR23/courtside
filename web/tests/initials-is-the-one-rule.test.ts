// web/tests/initials-is-the-one-rule.test.ts
//
// Cross-cutting test: the initials of a player or a guest team come from one helper,
// so no other module or component declares an initials function of its own.
//
// Tested:
// - The files to scan are found, and the scan cannot pass by matching nothing
// - The matcher flags function declarations, arrow functions and methods named initials
//   and passes lookalikes (an aliased import, a derived constant, a call, a short name)
// - Only format/initials.ts declares an initials function
//
// What is covered:
// - Happy path (only the helper declares it), edge cases (lookalikes, an aliased import,
//   a $derived constant) and the error case (each function form is flagged)
//
// Run with: cd web && pnpm exec vitest run tests/initials-is-the-one-rule.test.ts
//
// SEE: web/src/lib/format/initials.ts
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

const srcDir = join(import.meta.dirname, '../src/lib');
const helperFile = join(srcDir, 'format/initials.ts');

const PATTERNS: RegExp[] = [
	/\bfunction\s+initials\w*\s*[<(]/g,
	/\b(?:const|let|var)\s+initials\w*\s*(?::[^=]+)?=\s*(?:async\s+)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*(?::[^=]+)?=>/g,
	/^\s*initials\w*\s*\([^)]*\)\s*(?::[^{]+)?\{/gm
];

function initialsFunctions(source: string): string[] {
	return PATTERNS.flatMap((pattern) => [...source.matchAll(pattern)].map((m) => m[0].trim()));
}

function sourcesUnder(dir: string): string[] {
	return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
		const path = join(dir, entry.name);
		if (entry.isDirectory()) return entry.name === 'paraglide' ? [] : sourcesUnder(path);
		return entry.name.endsWith('.ts') || entry.name.endsWith('.svelte') ? [path] : [];
	});
}

const files = sourcesUnder(srcDir);

describe('the scan', () => {
	it('finds the files to check', () => {
		expect(files.length).toBeGreaterThanOrEqual(150);
	});

	it('finds the one declaration in the helper', () => {
		expect(initialsFunctions(readFileSync(helperFile, 'utf8'))).toHaveLength(1);
	});
});

describe('the matcher', () => {
	it('flags a function, an arrow function and a method', () => {
		expect(initialsFunctions('function initials(p: X): string {')).toHaveLength(1);
		expect(initialsFunctions('const initials = (p: X) => p.a;')).toHaveLength(1);
		expect(initialsFunctions('const initialsOf = name => name;')).toHaveLength(1);
		expect(initialsFunctions('\tinitials(p) {')).toHaveLength(1);
	});

	it('passes lookalikes', () => {
		expect(
			initialsFunctions("import { initials as initialsOf } from '#lib/format/initials.ts';")
		).toEqual([]);
		expect(initialsFunctions('const initials = $derived(initialsOf(name));')).toEqual([]);
		expect(initialsFunctions('function initialAndLast(feed: PlayerFeed) {')).toEqual([]);
		expect(initialsFunctions('{initials(s.star)}')).toEqual([]);
		expect(initialsFunctions('return initials([team.city, team.name].join(" "));')).toEqual([]);
	});
});

describe('the initials rule', () => {
	it('is declared only in format/initials.ts', () => {
		const offenders: string[] = [];
		for (const file of files) {
			if (file === helperFile) continue;
			for (const match of initialsFunctions(readFileSync(file, 'utf8'))) {
				offenders.push(`${relative(srcDir, file)} ${match}`);
			}
		}
		expect(offenders, `declare initials outside the helper:\n${offenders.join('\n')}`).toEqual([]);
	});
});
