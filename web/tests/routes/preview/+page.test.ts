// web/tests/routes/preview/+page.test.ts
//
// Tests for the development-only preview route.
//
// Tested:
// - Returns the preview component in development
// - Answers 404 outside development
// - Renders the preview content it receives
//
// What is covered:
// - Both environments, and the page render
//
// Run with: cd web && pnpm exec vitest run tests/routes/preview/+page.test.ts
//
// SEE: web/src/routes/preview/+page.ts, web/src/routes/preview/+page.svelte
import { isHttpError } from '@sveltejs/kit';
import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { load } from '../../../src/routes/preview/+page';
import Preview from '../../../src/routes/preview/Preview.svelte';
import Page from '../../../src/routes/preview/+page.svelte';

const event = {} as Parameters<typeof load>[0];

describe('preview route', () => {
	afterEach(() => {
		vi.unstubAllEnvs();
	});

	it('returns the preview component in development', async () => {
		const data = await load(event);
		expect(data).toHaveProperty('Preview');
	});

	it('answers 404 outside development', async () => {
		vi.stubEnv('DEV', false);
		const error = await Promise.resolve(load(event)).catch((e: unknown) => e);
		expect(isHttpError(error) && error.status === 404).toBe(true);
	});

	it('renders the preview content it receives', () => {
		render(Page, { props: { params: {}, data: { Preview } } });
		expect(screen.getByRole('heading', { level: 1, name: 'Component preview' })).toBeTruthy();
	});
});
