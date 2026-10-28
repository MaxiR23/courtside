// web/tests/lib/components/AllStarPlate.test.ts
//
// Tests for the AllStarPlate component.
//
// Tested:
// - The MVP plate: headshot, watermark, labels, solid MVP tag; initials without a photo
// - The score plate with the winner first
// - The live plate: header, format line, two rows with the leader in ink, clock, status and Next
// - The live clock is re-read from the feed on each tick
// - The tip-off plate and the year plate, with "—" without a year
// - Mobile: the MVP thumb links to #mvp, and the live scoreboard is a button that calls onLive
//
// What is covered:
// - Each plate kind on both layouts, drawn from the recorded feeds
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/AllStarPlate.test.ts
//
// SEE: web/src/lib/components/AllStarPlate.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { tick as flush } from 'svelte';
import { describe, expect, it, vi } from 'vitest';

import { LiveTick } from '../../../src/lib/all-star/live-tick.svelte';
import type { PlateView } from '../../../src/lib/all-star/types';
import AllStarPlate from '../../../src/lib/components/AllStarPlate.svelte';
import { viewOf } from '../all-star/views';

const plateOf = (name: 'before' | 'live' | 'after') => viewOf(name).header.plate;
const show = (
	plate: PlateView,
	layout: 'desktop' | 'mobile' = 'desktop',
	onLive = () => {},
	tick = new LiveTick()
) => render(AllStarPlate, { props: { plate, layout, tick, onLive } });

describe('AllStarPlate, MVP', () => {
	it('draws every frame with the All-Star corner marks', () => {
		const { container } = show(plateOf('after'));
		const frames = container.querySelectorAll('.blueprint-frame');
		expect(frames.length).toBeGreaterThan(0);
		for (const frame of frames) expect(frame.classList.contains('marks-allstar')).toBe(true);
	});

	it('shows the headshot, the watermark, the labels and the solid MVP tag', () => {
		const { container } = show(plateOf('after'));
		expect(screen.getByRole('img', { name: 'Ada Example' }).getAttribute('src')).toBe(
			'https://example.com/photos/1001.png'
		);
		expect(container.querySelector('.watermark')?.textContent).toBe('7');
		expect(screen.getByText('All-Star MVP')).toBeTruthy();
		expect(screen.getByText('41 PTS · 3 games')).toBeTruthy();
		expect(container.querySelector('.solid-tag')?.textContent).toBe('MVP');
		expect(container.querySelector('.plate-name')?.textContent).toBe('Ada Example');
	});

	it('shows initials without a photo and no watermark without a jersey', () => {
		const plate = { ...plateOf('after'), photo: null, jersey: null } as PlateView;
		const { container } = show(plate);
		expect(screen.getByRole('img', { name: 'Ada Example' }).textContent).toBe('AE');
		expect(container.querySelector('.watermark')).toBeNull();
	});

	it('draws a 116 by 156 thumb linking to #mvp on mobile', () => {
		const { container } = show(plateOf('after'), 'mobile');
		const link = container.querySelector('a.mvp-thumb');
		expect(link?.getAttribute('href')).toBe('#mvp');
		expect(link?.querySelector('.solid-tag')?.textContent).toBe('MVP');
		expect(container.querySelector('.plate')).toBeNull();
	});
});

describe('AllStarPlate, score', () => {
	it('shows the Championship score with the winner first', () => {
		const view = viewOf('after');
		const feed = { ...view.header.plate, kind: 'score', rows: view.scoreline!.rows } as PlateView;
		const { container } = show(feed);
		const rows = [...container.querySelectorAll('.score-row')];
		expect(rows.map((r) => r.querySelector('.score-name')?.textContent?.trim())).toEqual([
			'Team Stripes',
			'Team Waves'
		]);
		expect(rows.map((r) => r.querySelector('.score-value')?.textContent)).toEqual(['25', '23']);
	});
});

describe('AllStarPlate, live', () => {
	it('shows the header, the format line, both rows with the leader in ink, the clock and Next', () => {
		const { container } = show(plateOf('live'));
		expect(screen.getByText('Live · Semifinals')).toBeTruthy();
		expect(screen.getByText('1 period · 12 min')).toBeTruthy();
		const rows = [...container.querySelectorAll('.live-row')];
		expect(rows.map((r) => r.classList.contains('loser'))).toEqual([false, true]);
		expect(rows.map((r) => r.querySelector('.live-score')?.textContent)).toEqual(['30', '12']);
		expect(container.querySelector('.clock')?.textContent).toBe('5:12');
		expect(screen.getByText('Q1')).toBeTruthy();
		expect(screen.getByText('Next: Championship')).toBeTruthy();
		expect(container.querySelector('.live-dot')).not.toBeNull();
	});

	it('omits the status and Next when the feed has none', () => {
		const plate = { ...plateOf('live'), status: null, next: null } as PlateView;
		const { container } = show(plate);
		expect(container.querySelector('.status')).toBeNull();
		expect(container.querySelector('.next')).toBeNull();
	});

	it('re-reads the clock of the latest feed on each tick', async () => {
		const tick = new LiveTick();
		const { container, rerender } = show(plateOf('live'), 'desktop', () => {}, tick);
		expect(container.querySelector('.clock')?.textContent).toBe('5:12');
		await rerender({
			plate: { ...plateOf('live'), clock: '4:58' } as PlateView,
			layout: 'desktop',
			tick,
			onLive: () => {}
		});
		expect(container.querySelector('.clock')?.textContent).toBe('4:58');
		tick.tick += 1;
		await flush();
		expect(container.querySelector('.clock')?.textContent).toBe('4:58');
	});

	it('is one tappable scoreboard on mobile that calls onLive with the game', async () => {
		const onLive = vi.fn();
		const { container } = show(plateOf('live'), 'mobile', onLive);
		await fireEvent.click(container.querySelector('button.live-block')!);
		expect(onLive).toHaveBeenCalledWith('s2');
	});
});

describe('AllStarPlate, tip-off and year', () => {
	it('shows the tip-off text', () => {
		const plate = { kind: 'tipoff', gameId: 'c1', text: 'Tip-off · 8:20 PM' } as PlateView;
		show(plate);
		expect(screen.getByText('Tip-off · 8:20 PM')).toBeTruthy();
	});

	it('shows the outlined year over the dashed circles', () => {
		const { container } = show(plateOf('before'));
		expect(container.querySelector('.numeral')?.textContent).toBe('2027');
		expect(container.querySelectorAll('.circle')).toHaveLength(2);
	});

	it('shows a dash when the year is unknown', () => {
		const { container } = show({ kind: 'year', year: null });
		expect(container.querySelector('.numeral')?.textContent).toBe('—');
		expect(container.querySelectorAll('.circle')).toHaveLength(2);
	});
});
