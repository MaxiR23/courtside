// web/tests/lib/components/AllStarMvp.test.ts
//
// Tests for the AllStarMvp component.
//
// Tested:
// - The MVP card: kicker, name, league team link with its bar, one line per game with the Championship in accent,
//   the day total and the player profile link
// - The scoreline card: the winner first with its score in accent, the loser muted
// - Without an MVP only the scoreline card shows; without a scoreline only the MVP card
// - The box link calls onChampionship (a button on desktop, the whole card on mobile)
// - The jersey watermark and the initials without a photo
//
// What is covered:
// - Each state the section shows, drawn from the recorded feeds
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/AllStarMvp.test.ts
//
// SEE: web/src/lib/components/AllStarMvp.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

import AllStarMvp from '../../../src/lib/components/AllStarMvp.svelte';
import { playerHref, teamHref, viewOf } from '../all-star/views';

const view = viewOf('after');
const show = (
	props: Partial<{
		mvp: typeof view.mvp;
		scoreline: typeof view.scoreline;
		layout: 'desktop' | 'mobile';
	}> = {},
	onChampionship = () => {}
) =>
	render(AllStarMvp, {
		props: {
			mvp: view.mvp,
			scoreline: view.scoreline,
			layout: 'desktop',
			teamHref,
			playerHref,
			onChampionship,
			...props
		}
	});

describe('AllStarMvp', () => {
	it('draws every frame with the All-Star corner marks', () => {
		const { container } = show();
		const frames = container.querySelectorAll('.blueprint-frame');
		expect(frames.length).toBeGreaterThan(0);
		for (const frame of frames) expect(frame.classList.contains('marks-allstar')).toBe(true);
	});

	it('shows the MVP name, the league team link and one line per game', () => {
		const { container } = show();
		expect(screen.getByText('All-Star MVP')).toBeTruthy();
		expect(screen.getByRole('heading', { name: 'Ada Example' })).toBeTruthy();
		expect(screen.getByRole('link', { name: /HBR/ }).getAttribute('href')).toBe('/team/hbr');
		expect(container.querySelector('.league .league-bar')).not.toBeNull();
		const lines = [...container.querySelectorAll('.line')];
		expect(lines.map((l) => l.querySelector('.result')?.textContent)).toEqual([
			'W 21–18 vs Team Waves',
			'W 20–17 vs Team Peaks',
			'W 25–23 vs Team Waves'
		]);
		expect(lines.map((l) => l.querySelector('.round')?.classList.contains('championship'))).toEqual(
			[false, false, true]
		);
	});

	it('shows the day total and the player profile link', () => {
		show();
		expect(screen.getByText('41 PTS · across 3 games')).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Player profile →' }).getAttribute('href')).toBe(
			'/player/1001'
		);
	});

	it('draws the jersey watermark and a photo, or initials without one', () => {
		const { container } = show();
		expect(container.querySelector('.watermark')?.textContent).toBe('7');
		expect(container.querySelector('img')).not.toBeNull();
		const bare = show({ mvp: { ...view.mvp!, photo: null, jersey: null } });
		expect(bare.container.querySelectorAll('.watermark')).toHaveLength(0);
		expect(
			screen.getAllByRole('img', { name: 'Ada Example' }).some((n) => n.textContent === 'AE')
		).toBe(true);
	});

	it('shows the winner first with the score in accent and the loser muted', () => {
		const { container } = show();
		const rows = [...container.querySelectorAll('.score-row')];
		expect(rows.map((r) => r.querySelector('.score-name')?.textContent?.trim())).toEqual([
			'Team Stripes',
			'Team Waves'
		]);
		expect(rows.map((r) => r.querySelector('.score-value')?.classList.contains('winner'))).toEqual([
			true,
			false
		]);
		expect(rows.map((r) => r.classList.contains('loser'))).toEqual([false, true]);
	});

	it('shows only the scoreline card without an MVP', () => {
		const { container } = show({ mvp: null });
		expect(container.querySelector('.mvp-card')).toBeNull();
		expect(container.querySelector('.scoreline')).not.toBeNull();
	});

	it('shows only the MVP card without a scoreline', () => {
		const { container } = show({ scoreline: null });
		expect(container.querySelector('.mvp-card')).not.toBeNull();
		expect(container.querySelector('.scoreline')).toBeNull();
	});

	it('calls onChampionship from the box link', async () => {
		const onChampionship = vi.fn();
		show({}, onChampionship);
		await fireEvent.click(screen.getByRole('button', { name: 'Box score and highlights →' }));
		expect(onChampionship).toHaveBeenCalledTimes(1);
	});

	it('makes the whole scoreline one tappable block on mobile', async () => {
		const onChampionship = vi.fn();
		const { container } = show({ layout: 'mobile' }, onChampionship);
		const block = container.querySelector('button.scoreline')!;
		expect(block.textContent).toContain('Team Stripes');
		expect(block.textContent).toContain('Box score and highlights →');
		await fireEvent.click(block);
		expect(onChampionship).toHaveBeenCalledTimes(1);
		expect(container.querySelector('.all-star-mvp')?.classList.contains('mobile')).toBe(true);
	});
});
