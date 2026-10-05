// web/tests/inlang-plugins-are-local.test.ts
//
// Cross-cutting test: the inlang plugins load from pinned local packages, never from the network.
//
// Tested:
// - Every plugin module in project.inlang/settings.json is a local path under node_modules
// - Every plugin package is a devDependency pinned to an exact version
// - Every plugin file exists after install
//
// What is covered:
// - Happy path (both plugins are local, pinned and present)
// - Edge cases (the check cannot pass with an empty module list)
// - Error case: a remote URL or a version range fails the test
//
// Run with: cd web && pnpm exec vitest run tests/inlang-plugins-are-local.test.ts
//
// SEE: web/project.inlang/settings.json, web/package.json
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const webDir = join(import.meta.dirname, '..');
const settings = JSON.parse(
	readFileSync(join(webDir, 'project.inlang', 'settings.json'), 'utf8')
) as { modules?: string[] };
const devDependencies = (
	JSON.parse(readFileSync(join(webDir, 'package.json'), 'utf8')) as {
		devDependencies: Record<string, string>;
	}
).devDependencies;
const modules = settings.modules ?? [];
const localModule = /^\.\/node_modules\/(@inlang\/[^/]+)\/dist\/index\.js$/;

describe('inlang plugins', () => {
	it('lists at least one plugin module', () => {
		expect(modules.length).toBeGreaterThan(0);
	});

	it.each(modules)('loads %s from a local package, not a URL', (module) => {
		expect(module).toMatch(localModule);
	});

	it.each(modules)('pins the package of %s to an exact devDependency version', (module) => {
		const name = localModule.exec(module)?.[1] ?? '';
		expect(devDependencies[name]).toMatch(/^\d+\.\d+\.\d+$/);
	});

	it.each(modules)('finds the file of %s installed', (module) => {
		expect(existsSync(join(webDir, module))).toBe(true);
	});
});
