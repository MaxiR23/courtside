// web/tests/lib/components/TeamOverview.test.ts
//
// Tests for the TeamOverview component.
//
// Tested:
// - The arena frame with the photo (empty alt, no filter class) and its caption
// - No frame and a stat cell with no photo; the cell replaces the frame after the image fails
// - The head coach cell, present and absent
// - Swatches with the inline colors and the hex text
// - The next game card, or "Season over."
//
// What is covered:
// - Each state the section shows, plus the image error event
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/TeamOverview.test.ts
//
// SEE: web/src/lib/components/TeamOverview.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import TeamOverview from '../../../src/lib/components/TeamOverview.svelte';
import type { OverviewSection } from '../../../src/lib/team/types';

const overview: OverviewSection = {
	arena: { name: 'Paycom Center', city: 'Oklahoma City, OK', photo: 'https://example.com/a.jpg' },
	coach: { label: 'Head coach', value: 'Mark Daigneault', sub: '6 seasons as NBA head coach' },
	colors: [{ hex: '#007AC1' }, { hex: '#EF3B24' }],
	nextGame: {
		gameId: 'g-next',
		linked: false,
		tag: null,
		date: 'Wednesday, October 7',
		opponent: '@ DEN',
		place: 'Ball Arena',
		time: '7:30 PM ET'
	}
};

const gameHref = (id: string) => `/game/${id}` as never;

const show = (value: OverviewSection = overview) =>
	render(TeamOverview, { props: { overview: value, gameHref } });

describe('TeamOverview arena', () => {
	it('shows the photo in a frame with an empty alt, no filter and the caption', () => {
		const { container } = show();
		const img = container.querySelector('img');
		expect(img?.getAttribute('src')).toBe('https://example.com/a.jpg');
		expect(img?.getAttribute('alt')).toBe('');
		expect(img?.classList.contains('filtered')).toBe(false);
		expect(container.querySelector('.blueprint-frame .photo-box')).toBeTruthy();
		expect(container.querySelector('.caption')?.textContent).toContain('Home arena');
		expect(container.querySelector('.caption')?.textContent).toContain('Paycom Center');
		expect(container.querySelector('.caption')?.textContent).toContain('Oklahoma City, OK');
	});

	it('shows a stat cell and no frame without a photo', () => {
		const { container } = show({ ...overview, arena: { ...overview.arena, photo: null } });
		expect(container.querySelector('.photo-box')).toBeNull();
		const cell = container.querySelector('.arena-cell');
		expect(cell?.textContent).toContain('Home arena');
		expect(cell?.textContent).toContain('Paycom Center');
		expect(cell?.textContent).toContain('Oklahoma City, OK');
	});

	it('leaves out the city line when there is no city', () => {
		const { container } = show({
			...overview,
			arena: { name: 'Paycom Center', city: null, photo: null }
		});
		expect(container.querySelector('.arena-cell .cell-sub')).toBeNull();
	});

	it('replaces the frame with the stat cell after the image fails', async () => {
		const { container } = show();
		await fireEvent.error(container.querySelector('img')!);
		expect(container.querySelector('.photo-box')).toBeNull();
		expect(container.querySelector('.arena-cell')).toBeTruthy();
	});
});

describe('TeamOverview cells', () => {
	it('shows the head coach cell, and none without a coach', () => {
		const { unmount } = show();
		expect(screen.getByText('Head coach')).toBeTruthy();
		expect(screen.getByText('Mark Daigneault')).toBeTruthy();
		expect(screen.getByText('6 seasons as NBA head coach')).toBeTruthy();
		unmount();
		const { container } = show({ ...overview, coach: null });
		expect(container.querySelector('.coach-cell')).toBeNull();
	});

	it('shows the team colors as inline swatches with their hex values', () => {
		const { container } = show();
		expect(screen.getByText('Team colors')).toBeTruthy();
		const chips = [...container.querySelectorAll<HTMLElement>('.swatch .chip')];
		expect(chips.map((chip) => chip.style.backgroundColor)).toEqual([
			'rgb(0, 122, 193)',
			'rgb(239, 59, 36)'
		]);
		expect(screen.getByText('#007AC1')).toBeTruthy();
		expect(screen.getByText('#EF3B24')).toBeTruthy();
	});

	it('shows the next game card, or Season over.', () => {
		const { unmount } = show();
		expect(screen.getByText('Next game')).toBeTruthy();
		expect(screen.getByText('@ DEN')).toBeTruthy();
		unmount();
		show({ ...overview, nextGame: null });
		expect(screen.getByText('Season over.')).toBeTruthy();
	});
});
