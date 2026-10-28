// web/tests/time-zone-is-pinned.test.ts
//
// Cross-cutting test: the suite pins the viewer's time zone, so times do not depend on the machine.
//
// Tested:
// - The suite runs in America/New_York
// - vi.stubEnv('TZ', ...) switches the zone for one test
//
// What is covered:
// - Happy path and the switch the time tests rely on
//
// Run with: cd web && pnpm exec vitest run tests/time-zone-is-pinned.test.ts
//
// SEE: web/vite.config.ts (test.env), docs/adr/0082-tip-times-in-the-viewers-time-zone.md
import { afterEach, describe, expect, it, vi } from 'vitest';

const zone = (): string => new Intl.DateTimeFormat().resolvedOptions().timeZone;

afterEach(() => {
	vi.unstubAllEnvs();
});

describe('the test time zone', () => {
	it('is America/New_York', () => {
		expect(zone()).toBe('America/New_York');
	});

	it('can be switched for one test', () => {
		vi.stubEnv('TZ', 'Europe/Madrid');
		expect(zone()).toBe('Europe/Madrid');
	});
});
