// web/tests/lib/cup/seasons.test.ts
//
// Tests for the Cup season range.
//
// Tested:
// - cupSeasons lists the calendar seasons from 2023-24, newest first, with the calendar's labels
//
// What is covered:
// - Happy path
//
// Run with: cd web && pnpm exec vitest run tests/lib/cup/seasons.test.ts
//
// SEE: web/src/lib/cup/seasons.ts
import { describe, expect, it } from 'vitest';

import type { CalendarFeed } from '../../../src/lib/contract/calendar';
import { cupSeasons } from '../../../src/lib/cup/seasons';
import calendarJson from '../feed/fixtures/calendar.json';

const calendar = calendarJson as unknown as CalendarFeed;

describe('cupSeasons', () => {
	it('lists the calendar seasons from 2023-24, newest first', () => {
		const seasons = cupSeasons(calendar);
		expect(seasons.map((entry) => entry.season)).toEqual([2027, 2026, 2025, 2024]);
		expect(seasons[3]?.seasonLabel).toBe(
			calendar.seasons.find((entry) => entry.season === 2024)?.seasonLabel
		);
	});
});
