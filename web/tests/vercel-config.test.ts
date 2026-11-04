// web/tests/vercel-config.test.ts
//
// Cross-cutting test: deploy/vercel.json forwards /api/* to the backend with the origin secret,
// serves 200.html for the browser-rendered paths of docs/deploy.md, and holds no IP, hostname or
// secret.
//
// Tested:
// - The /api/* route and its x-origin-secret transform
// - The rewrites match the "Browser-rendered paths" list of docs/deploy.md
// - The file holds only the allowed references and no address
//
// What is covered:
// - Happy path (the committed file)
// - Edge case (exactly 10 paths and no extra top-level keys)
// - Error case (the guard flags an IP, a URL and a literal secret)
//
// Run with: cd web && pnpm exec vitest run tests/vercel-config.test.ts
//
// SEE: deploy/vercel.json, docs/deploy.md, docs/adr/0079-production-behind-vercel-with-origin-secret.md
// @vitest-environment node
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const root = join(import.meta.dirname, '..', '..');
const rawConfig = readFileSync(join(root, 'deploy', 'vercel.json'), 'utf8');
const config = JSON.parse(rawConfig);
const deployDoc = readFileSync(join(root, 'docs', 'deploy.md'), 'utf8');

const allowedReferences = ['${BACKEND_URL}', '$ORIGIN_SECRET', '$1'];

function hasAddress(text: string): boolean {
	return /\b\d{1,3}(\.\d{1,3}){3}\b/.test(text) || text.includes('://');
}

function references(text: string): string[] {
	return text.match(/\$\{[A-Z_]+\}|\$[A-Za-z_0-9]+/g) ?? [];
}

function stringValues(value: unknown): string[] {
	if (typeof value === 'string') return [value];
	if (Array.isArray(value)) return value.flatMap(stringValues);
	if (value !== null && typeof value === 'object') {
		return Object.values(value).flatMap(stringValues);
	}
	return [];
}

function unexpected(text: string): string[] {
	const found = references(text).filter((ref) => !allowedReferences.includes(ref));
	if (hasAddress(text)) found.push('address');
	return found;
}

describe('deploy/vercel.json', () => {
	it('forwards /api/* to ${BACKEND_URL} and lists BACKEND_URL in its env', () => {
		expect(config.routes).toHaveLength(1);
		const { transforms, ...route } = config.routes[0];
		expect(route).toEqual({
			src: '/api/(.*)',
			dest: '${BACKEND_URL}/$1',
			env: ['BACKEND_URL']
		});
		expect(transforms).toHaveLength(1);
	});

	it('sets x-origin-secret from $ORIGIN_SECRET with a set transform', () => {
		expect(config.routes[0].transforms[0]).toEqual({
			type: 'request.headers',
			op: 'set',
			target: { key: 'x-origin-secret' },
			args: '$ORIGIN_SECRET',
			env: ['ORIGIN_SECRET']
		});
	});

	it('has only routes and rewrites at the top level', () => {
		expect(Object.keys(config).sort()).toEqual(['rewrites', 'routes']);
	});

	it('serves /200.html for exactly the browser-rendered paths of docs/deploy.md', () => {
		const start = deployDoc.indexOf('### Browser-rendered paths');
		expect(start).toBeGreaterThan(-1);
		const rest = deployDoc.slice(deployDoc.indexOf('\n', start) + 1);
		const next = rest.search(/^#{1,3} /m);
		const section = next === -1 ? rest : rest.slice(0, next);
		const documented = [...section.matchAll(/^- `(\/[^`]+)`/gm)].map((m) => m[1]);
		expect(documented).toHaveLength(10);

		const sources = config.rewrites.map((r: { source: string }) =>
			r.source.replace(/\/:path\*$/, '/*')
		);
		expect(sources).toHaveLength(10);
		expect([...sources].sort()).toEqual([...documented].sort());
		for (const rewrite of config.rewrites) {
			expect(rewrite.destination).toBe('/200.html');
		}
	});

	it('holds no IP, no hostname and no secret', () => {
		expect(hasAddress(rawConfig)).toBe(false);
		expect(unexpected(rawConfig)).toEqual([]);
		for (const value of stringValues(config.rewrites).filter((v) => /\w\.\w/.test(v))) {
			expect(value).toBe('/200.html');
		}
	});

	it('flags an IP, a URL and a literal secret in a modified copy', () => {
		const modified = JSON.parse(rawConfig);
		modified.routes[0].dest = 'http://203.0.113.5/$1';
		modified.routes[0].transforms[0].args = 'literal-secret.value';
		const text = JSON.stringify(modified);
		expect(hasAddress(text)).toBe(true);
		expect(text.includes('://')).toBe(true);
		const literal = stringValues(modified.routes).filter(
			(v) => /\w\.\w/.test(v) && v !== '/200.html'
		);
		expect(literal).toContain('literal-secret.value');
		expect(stringValues(modified.routes[0].dest)).toContain('http://203.0.113.5/$1');
		expect(unexpected(text)).toContain('address');
	});
});
