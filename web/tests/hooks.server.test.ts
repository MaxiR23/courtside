// web/tests/hooks.server.test.ts
//
// Tests for the server hook that writes the page language and direction.
//
// Tested:
// - Writes English and left-to-right when the request names no language
// - Writes Spanish when the request prefers Spanish
// - Leaves no paraglide placeholder in the page
//
// What is covered:
// - Happy path and the default case, through the real paraglide middleware
//
// Run with: cd web && pnpm exec vitest run tests/hooks.server.test.ts
//
// SEE: web/src/hooks.server.ts
// @vitest-environment node
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { RequestEvent } from '@sveltejs/kit';
import { describe, expect, it } from 'vitest';
import { handle } from '../src/hooks.server';

const htmlLine = readFileSync(join(import.meta.dirname, '../src/app.html'), 'utf8')
	.split('\n')
	.find((line) => line.startsWith('<html'))!;

async function render(headers: Record<string, string> = {}): Promise<string> {
	const request = new Request('http://localhost/', { headers });
	let html = '';
	await handle({
		event: { request } as RequestEvent,
		resolve: async (_event, options) => {
			html = (await options?.transformPageChunk?.({ html: htmlLine, done: true })) ?? htmlLine;
			return new Response(html);
		}
	});
	return html;
}

describe('the server hook', () => {
	it('writes English and left-to-right when no language is requested', async () => {
		const html = await render();
		expect(html).toContain('lang="en"');
		expect(html).toContain('dir="ltr"');
	});

	it('writes Spanish when the request prefers Spanish', async () => {
		const html = await render({ 'accept-language': 'es' });
		expect(html).toContain('lang="es"');
	});

	it('leaves no paraglide placeholder in the page', async () => {
		expect(await render()).not.toContain('%paraglide.');
	});
});
