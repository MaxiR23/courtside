// web/tests/lib/components/GameCard.test.ts
//
// Tests for the GameCard component.
//
// Tested:
// - Scheduled, live and final games on the desktop and the mobile row
// - The name and score of the team that is not the winner are dimmed, never its monogram, for home and away winners, following the winner field and not the scores; live games dim no one
// - Monogram sizes per row layout, decorative chevron
// - Spanish live badge with a Spanish browser preference
// - A card without details stays a plain row; with details it toggles an inert panel
// - The panel per state: live, final, overtime and scheduled, its motion and Spanish labels
// - Highlights on final games only: videos, pending, play callback, player removed on close
// - Delayed, postponed and canceled games: status line only, no score, no tip time, no toggle
// - A scheduled game with no known network
// - Spoiler-free mode: final cards that can expand hide the score and the dimming until open
//
// What is covered:
// - Each card state on each row layout
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/GameCard.test.ts
//
// SEE: web/src/lib/components/GameCard.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { GameDetails, ScheduleGame } from '../../../src/lib/schedule/types';
import { preferLanguages } from '../../prefer-languages';

import GameCard from '../../../src/lib/components/GameCard.svelte';

const away = { code: 'GSW', name: 'Warriors', city: 'Golden State' };
const home = { code: 'LAL', name: 'Lakers', city: 'Los Angeles' };
const scheduled: ScheduleGame = {
	id: 's',
	away,
	home,
	status: { state: 'scheduled', tipTime: '9:00', tipSuffix: 'PM ET', network: 'Prime Video' }
};
const live: ScheduleGame = {
	id: 'l',
	away,
	home,
	status: { state: 'live', period: 'Q3', clock: '4:12', awayScore: 78, homeScore: 74 }
};
const final = (awayScore: number, homeScore: number, winner: string): ScheduleGame => ({
	id: 'f',
	away,
	home,
	status: { state: 'final', awayScore, homeScore, winner }
});

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	Reflect.deleteProperty(HTMLElement.prototype, 'animate');
});

const awayPlayer = { firstName: 'Stephen', lastName: 'Curry', teamCode: 'GSW', photo: '/away.svg' };
const homePlayer = { firstName: 'LeBron', lastName: 'James', teamCode: 'LAL', photo: '/home.svg' };
const played = (periodsAway: number[], periodsHome: number[]): GameDetails => ({
	kind: 'played',
	periods: { away: periodsAway, home: periodsHome },
	leaders: {
		away: { ...awayPlayer, points: 34, rebounds: 3, assists: 8 },
		home: { ...homePlayer, points: 29, rebounds: 9, assists: 7 }
	},
	stats: {
		away: { fieldGoalPct: 0.478, threePointPct: 0.391, rebounds: 44, assists: 27, turnovers: 9 },
		home: { fieldGoalPct: 0.452, threePointPct: 0.417, rebounds: 41, assists: 27, turnovers: 14 }
	}
});
const withDetails = (game: ScheduleGame, details: GameDetails): ScheduleGame => ({
	...game,
	details
});
const liveWithDetails = withDetails(live, played([28, 26, 24], [25, 27, 22]));
const finalWithDetails = withDetails(
	final(112, 104, 'GSW'),
	played([30, 28, 26, 28], [24, 27, 25, 28])
);
const overtimeWithDetails = withDetails(
	final(132, 130, 'GSW'),
	played([28, 25, 30, 27, 12, 10], [30, 26, 24, 30, 12, 8])
);
const scheduledWithDetails = withDetails(scheduled, {
	kind: 'scheduled',
	venue: 'Crypto.com Arena',
	playersToWatch: { away: awayPlayer, home: homePlayer }
});
const highlightsData = (videos: { id: string }[]) => ({
	platform: 'Test platform',
	searchUrl: '/search?q=x',
	videos: videos.map(({ id }) => ({
		id,
		title: `Clip ${id}`,
		channel: 'Channel',
		thumbnail: `/thumb-${id}.svg`,
		embedUrl: `/embed/${id}`
	}))
});
const withHighlights = (game: ScheduleGame, videos: { id: string }[]): ScheduleGame =>
	withDetails(game, {
		...played([30, 28, 26, 28], [24, 27, 25, 28]),
		highlights: highlightsData(videos)
	} as GameDetails);
const finalWithHighlights = withHighlights(final(112, 104, 'GSW'), [{ id: 'v1' }, { id: 'v2' }]);
const finalPending = withHighlights(final(112, 104, 'GSW'), []);
const HIGHLIGHTS = 'Highlights will appear here after the final buzzer.';

const dimmedText = (container: HTMLElement) =>
	[...container.querySelectorAll('.dimmed')].map((e) => e.textContent?.replace(/\s+/g, ' ').trim());

describe('GameCard', () => {
	it('shows the network on the status line and the tip time with its suffix on a scheduled game (desktop)', () => {
		const { container } = render(GameCard, { props: { game: scheduled, layout: 'desktop' } });
		expect(container.querySelector('.status-line')?.textContent?.trim()).toBe('Prime Video');
		expect(container.querySelector('.tip-time')?.textContent).toBe('9:00PM ET');
		expect(container.querySelector('.tip-time .suffix')?.textContent).toBe('PM ET');
		expect(container.querySelector('.score')).toBeNull();
	});

	it('shows "9:00 PM ET · Prime Video" on the status line of a scheduled game (mobile)', () => {
		const { container } = render(GameCard, { props: { game: scheduled, layout: 'mobile' } });
		expect(container.querySelector('.status-line')?.textContent?.trim()).toBe(
			'9:00 PM ET · Prime Video'
		);
		expect(container.querySelector('.score')).toBeNull();
	});

	it.each(['desktop', 'mobile'] as const)(
		'shows the live badge with the period and clock on a live game (%s)',
		(layout) => {
			const { container } = render(GameCard, { props: { game: live, layout } });
			expect(screen.getByText('LIVE')).toBeTruthy();
			expect(container.querySelector('.status-line')?.textContent).toContain('Q3 · 4:12');
			expect([...container.querySelectorAll('.score')].map((e) => e.textContent)).toEqual([
				'78',
				'74'
			]);
		}
	);

	it.each(['desktop', 'mobile'] as const)(
		'shows FINAL and both scores on a final game (%s)',
		(layout) => {
			const { container } = render(GameCard, { props: { game: final(112, 104, 'GSW'), layout } });
			expect(container.querySelector('.status-line')?.textContent?.trim()).toBe('Final');
			expect([...container.querySelectorAll('.score')].map((e) => e.textContent)).toEqual([
				'112',
				'104'
			]);
		}
	);

	it('dims the team that is not the winner on a final game, home and away winners', () => {
		const desktop = render(GameCard, { props: { game: final(98, 104, 'LAL'), layout: 'desktop' } });
		const text = dimmedText(desktop.container);
		expect(text.some((t) => t?.includes('Warriors'))).toBe(true);
		expect(text).toContain('98');
		expect(text.some((t) => t?.includes('Lakers'))).toBe(false);
		expect(text).not.toContain('104');
		desktop.unmount();

		const { container } = render(GameCard, {
			props: { game: final(112, 104, 'GSW'), layout: 'mobile' }
		});
		const mobile = dimmedText(container);
		expect(mobile.some((t) => t?.includes('Lakers'))).toBe(true);
		expect(mobile).toContain('104');
		expect(mobile.some((t) => t?.includes('Warriors'))).toBe(false);
		expect(mobile).not.toContain('112');
	});

	it.each([
		['desktop', final(98, 104, 'LAL')],
		['mobile', final(112, 104, 'GSW')]
	] as const)("does not dim the losing team's monogram on the %s row", (layout, game) => {
		const { container } = render(GameCard, { props: { game, layout } });
		expect(container.querySelectorAll('.team-monogram').length).toBeGreaterThan(0);
		expect(container.querySelectorAll('.dimmed .team-monogram')).toHaveLength(0);
		const text = dimmedText(container);
		expect(text.length).toBeGreaterThan(0);
		expect(text.some((t) => t?.includes(layout === 'desktop' ? 'Warriors' : 'Lakers'))).toBe(true);
	});

	it('dims the team that is not the winner even when its score is higher', () => {
		for (const layout of ['desktop', 'mobile'] as const) {
			const { container, unmount } = render(GameCard, {
				props: { game: final(98, 104, 'GSW'), layout }
			});
			const text = dimmedText(container);
			expect(text.some((t) => t?.includes('Lakers'))).toBe(true);
			expect(text).toContain('104');
			expect(text.some((t) => t?.includes('Warriors'))).toBe(false);
			expect(text).not.toContain('98');
			unmount();
		}
	});

	it('does not dim a team on a live game', () => {
		const { container } = render(GameCard, { props: { game: live, layout: 'desktop' } });
		expect(container.querySelectorAll('.dimmed')).toHaveLength(0);
	});

	it('uses the large monograms on the desktop row and the small ones on the mobile row', () => {
		const desktop = render(GameCard, { props: { game: scheduled, layout: 'desktop' } });
		expect(desktop.container.querySelectorAll('.team-monogram.large')).toHaveLength(2);
		expect(desktop.container.querySelectorAll('.team-monogram.small')).toHaveLength(0);
		desktop.unmount();
		const { container } = render(GameCard, { props: { game: scheduled, layout: 'mobile' } });
		expect(container.querySelectorAll('.team-monogram.small')).toHaveLength(2);
		expect(container.querySelectorAll('.team-monogram.large')).toHaveLength(0);
	});

	it('shows a decorative chevron', () => {
		for (const layout of ['desktop', 'mobile'] as const) {
			const { container, unmount } = render(GameCard, { props: { game: scheduled, layout } });
			expect(container.querySelector('svg.chevron')?.getAttribute('aria-hidden')).toBe('true');
			unmount();
		}
	});

	it('shows the live badge in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		render(GameCard, { props: { game: live, layout: 'desktop' } });
		expect(screen.getByText('EN VIVO')).toBeTruthy();
	});

	it('keeps a plain row with no toggle when the game has no details', () => {
		const { container } = render(GameCard, { props: { game: scheduled, layout: 'desktop' } });
		expect(container.querySelector('button')).toBeNull();
		expect(container.querySelector('.panel')).toBeNull();
	});

	it('renders the row as a collapsed toggle with its panel inert when closed', () => {
		const { container } = render(GameCard, {
			props: { game: liveWithDetails, layout: 'desktop' }
		});
		const toggle = container.querySelector('button.toggle');
		const panel = container.querySelector('.panel');
		expect(toggle?.getAttribute('aria-expanded')).toBe('false');
		expect(panel?.id).toBeTruthy();
		expect(toggle?.getAttribute('aria-controls')).toBe(panel?.id);
		expect((panel as HTMLElement).inert).toBe(true);
	});

	it('calls onToggle when the row is clicked', async () => {
		const onToggle = vi.fn();
		const { container } = render(GameCard, {
			props: { game: liveWithDetails, layout: 'desktop', onToggle }
		});
		await fireEvent.click(container.querySelector('button.toggle') as HTMLElement);
		expect(onToggle).toHaveBeenCalledTimes(1);
	});

	it('shows the accent border, the open class and an active panel when open', () => {
		const { container } = render(GameCard, {
			props: { game: liveWithDetails, layout: 'desktop', open: true }
		});
		expect(container.querySelector('.blueprint-frame.active')).not.toBeNull();
		expect(container.querySelector('.card.open')).not.toBeNull();
		expect((container.querySelector('.panel') as HTMLElement).inert).toBe(false);
		expect(container.querySelector('button.toggle')?.getAttribute('aria-expanded')).toBe('true');
	});

	it('shows the line score, leaders and team stats on a live game, plus the highlights notice', () => {
		const { container } = render(GameCard, {
			props: { game: liveWithDetails, layout: 'desktop', open: true }
		});
		expect(container.querySelector('.line-score')).not.toBeNull();
		expect(container.querySelector('.leaders')).not.toBeNull();
		expect(container.querySelector('.team-stats')).not.toBeNull();
		expect(screen.getByText(HIGHLIGHTS)).toBeTruthy();
		const totals = [...container.querySelectorAll('.line-score .total')].map((e) => e.textContent);
		expect(totals).toEqual(['78', '74']);
	});

	it('shows the line score, leaders and team stats on a final game without the highlights notice', () => {
		const { container } = render(GameCard, {
			props: { game: finalWithDetails, layout: 'desktop', open: true }
		});
		expect(container.querySelector('.line-score')).not.toBeNull();
		expect(container.querySelector('.leaders')).not.toBeNull();
		expect(container.querySelector('.team-stats')).not.toBeNull();
		expect(screen.queryByText(HIGHLIGHTS)).toBeNull();
	});

	it('shows the overtime columns on a final game that went to overtime', () => {
		const { container } = render(GameCard, {
			props: { game: overtimeWithDetails, layout: 'desktop', open: true }
		});
		const header = [...container.querySelectorAll('.line-score .head .cell')].map(
			(e) => e.textContent
		);
		expect(header).toEqual(['1', '2', '3', '4', 'OT', '2OT', 'T']);
	});

	it('shows Tip-off, Venue, Broadcast and the players to watch on a scheduled game', () => {
		const { container } = render(GameCard, {
			props: { game: scheduledWithDetails, layout: 'desktop', open: true }
		});
		const facts = [...container.querySelectorAll('.fact')].map((e) =>
			[...e.children].map((c) => c.textContent)
		);
		expect(facts).toEqual([
			['Tip-off', '9:00 PM ET'],
			['Venue', 'Crypto.com Arena'],
			['Broadcast', 'Prime Video']
		]);
		expect(screen.getByText('Players to watch')).toBeTruthy();
		expect(screen.getByText('Stephen Curry')).toBeTruthy();
		expect(screen.getByText('LeBron James')).toBeTruthy();
	});

	it('animates the panel when it opens and not with reduced motion', async () => {
		const animate = vi.fn(() => ({ cancel: vi.fn() }));
		Object.assign(HTMLElement.prototype, { animate });
		vi.stubGlobal('matchMedia', () => ({ matches: false }));
		const props = { game: liveWithDetails, layout: 'desktop' as const };
		const motion = render(GameCard, { props: { ...props, open: false } });
		expect(animate).not.toHaveBeenCalled();
		await motion.rerender({ ...props, open: true });
		expect(animate).toHaveBeenCalled();
		motion.unmount();

		animate.mockClear();
		vi.stubGlobal('matchMedia', () => ({ matches: true }));
		const reduced = render(GameCard, { props: { ...props, open: false } });
		await reduced.rerender({ ...props, open: true });
		expect(animate).not.toHaveBeenCalled();
	});

	it('shows the panel labels in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		const { container } = render(GameCard, {
			props: { game: scheduledWithDetails, layout: 'desktop', open: true }
		});
		expect(screen.getByText('Inicio')).toBeTruthy();
		expect(screen.getByText('Estadio')).toBeTruthy();
		expect(screen.getByText('Transmisión')).toBeTruthy();
		expect(screen.getByText('Jugadores a seguir')).toBeTruthy();
		expect(container.querySelector('.fact dd')?.textContent).toBe('9:00 PM ET');
	});

	it('shows the highlights after the stats on an open final game with highlights', () => {
		const { container } = render(GameCard, {
			props: { game: finalWithHighlights, layout: 'desktop', open: true }
		});
		const section = container.querySelector('.panel-highlights');
		expect(section).not.toBeNull();
		expect(section?.querySelectorAll('li')).toHaveLength(2);
		expect(screen.getByText('Clip v1')).toBeTruthy();
		const grid = container.querySelector('.panel-grid');
		expect(grid?.compareDocumentPosition(section as Node)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
	});

	it('shows the pending highlights state on a final game whose highlights are not in yet', () => {
		const { container } = render(GameCard, {
			props: { game: finalPending, layout: 'desktop', open: true }
		});
		expect(
			screen.getByText("Highlights aren't in yet. They'll appear here automatically.")
		).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Search highlights on Test platform' })).toBeTruthy();
		expect(container.querySelector('.panel-highlights img')).toBeNull();
	});

	it('shows no highlights section on a final game without highlights', () => {
		const { container } = render(GameCard, {
			props: { game: finalWithDetails, layout: 'desktop', open: true }
		});
		expect(container.querySelector('.highlights')).toBeNull();
	});

	it('shows no highlights section on a live game, only the notice', () => {
		const liveWithHighlights = withHighlights(live, [{ id: 'v1' }]);
		const { container } = render(GameCard, {
			props: { game: liveWithHighlights, layout: 'desktop', open: true }
		});
		expect(container.querySelector('.highlights')).toBeNull();
		expect(screen.getByText(HIGHLIGHTS)).toBeTruthy();
	});

	it('calls onPlay with the video id when a highlight thumbnail is clicked', async () => {
		const onPlay = vi.fn();
		render(GameCard, {
			props: { game: finalWithHighlights, layout: 'desktop', open: true, onPlay }
		});
		await fireEvent.click(screen.getByRole('button', { name: 'Play Clip v2' }));
		expect(onPlay).toHaveBeenCalledWith('v2');
	});

	it('shows the player for playingVideoId while open and removes it when the card closes', async () => {
		const props = { game: finalWithHighlights, layout: 'desktop' as const, playingVideoId: 'v1' };
		const { container, rerender } = render(GameCard, { props: { ...props, open: true } });
		expect(container.querySelector('iframe')?.getAttribute('src')).toBe('/embed/v1');
		await rerender({ ...props, open: false });
		expect(container.querySelector('iframe')).toBeNull();
	});

	describe('spoiler-free mode', () => {
		const row = (container: HTMLElement) => container.querySelector('button.toggle') as HTMLElement;

		it.each(['desktop', 'mobile'] as const)(
			'hides final scores until the card is expanded in spoiler-free mode (%s)',
			async (layout) => {
				const props = { game: finalWithDetails, layout, spoilerFree: true };
				const { container, rerender } = render(GameCard, { props });
				expect(row(container).querySelector('.score')).toBeNull();
				expect(row(container).textContent).toContain('Tap to reveal');
				await rerender({ ...props, open: true });
				expect(row(container).textContent).toContain('112');
				expect(row(container).textContent).toContain('104');
				expect(row(container).textContent).not.toContain('Tap to reveal');
			}
		);

		it('does not dim the losing team while the score is hidden', async () => {
			const game = withDetails(final(98, 104, 'LAL'), played([30, 28, 20, 20], [24, 27, 25, 28]));
			const props = { game, layout: 'desktop' as const, spoilerFree: true };
			const { container, rerender } = render(GameCard, { props });
			expect(container.querySelectorAll('.dimmed')).toHaveLength(0);
			await rerender({ ...props, open: true });
			expect(dimmedText(container)).toContain('98');
		});

		it('hides the score again when the expanded card is collapsed', async () => {
			const props = { game: finalWithDetails, layout: 'desktop' as const, spoilerFree: true };
			const { container, rerender } = render(GameCard, { props: { ...props, open: true } });
			expect(row(container).querySelector('.score')).not.toBeNull();
			await rerender({ ...props, open: false });
			expect(row(container).querySelector('.score')).toBeNull();
		});

		it('leaves live and scheduled cards unchanged in spoiler-free mode', () => {
			const liveCard = render(GameCard, {
				props: { game: liveWithDetails, layout: 'desktop', spoilerFree: true }
			});
			expect(row(liveCard.container).textContent).toContain('78');
			expect(row(liveCard.container).textContent).not.toContain('Tap to reveal');
			liveCard.unmount();
			const next = render(GameCard, {
				props: { game: scheduledWithDetails, layout: 'desktop', spoilerFree: true }
			});
			expect(next.container.querySelector('.tip-time')?.textContent).toBe('9:00PM ET');
			expect(next.container.textContent).not.toContain('Tap to reveal');
		});

		it('keeps the score on a final card that cannot expand', () => {
			const { container } = render(GameCard, {
				props: { game: final(112, 104, 'GSW'), layout: 'desktop', spoilerFree: true }
			});
			expect(container.querySelectorAll('.score')).toHaveLength(2);
			expect(container.textContent).not.toContain('Tap to reveal');
		});

		it('shows Toca para ver with a Spanish preference', () => {
			preferLanguages(['es-ES']);
			const { container } = render(GameCard, {
				props: { game: finalWithDetails, layout: 'desktop', spoilerFree: true }
			});
			expect(row(container).textContent).toContain('Toca para ver');
		});
	});
});

describe('GameCard with a delayed, postponed or canceled game', () => {
	const inState = (state: 'delayed' | 'postponed' | 'canceled'): ScheduleGame => ({
		id: state,
		away,
		home,
		status: { state }
	});
	const labels = [
		['delayed', 'Delayed', 'Retrasado'],
		['postponed', 'Postponed', 'Aplazado'],
		['canceled', 'Canceled', 'Cancelado']
	] as const;

	it.each(labels)('shows %s on the status line with no score and no tip time', (state, english) => {
		for (const layout of ['desktop', 'mobile'] as const) {
			const { container, unmount } = render(GameCard, {
				props: { game: inState(state), layout }
			});
			expect(container.querySelector('.status-line')?.textContent?.trim()).toBe(english);
			expect(container.querySelector('.score')).toBeNull();
			expect(container.querySelector('.tip-time')).toBeNull();
			unmount();
		}
	});

	it.each(labels)('shows %s in Spanish', (state, _label, spanish) => {
		preferLanguages(['es-ES']);
		const { container } = render(GameCard, { props: { game: inState(state), layout: 'desktop' } });
		expect(container.querySelector('.status-line')?.textContent?.trim()).toBe(spanish);
	});

	it.each(labels)('keeps %s as a plain row with no toggle', (state) => {
		const { container } = render(GameCard, { props: { game: inState(state), layout: 'desktop' } });
		expect(container.querySelector('button.toggle')).toBeNull();
	});
});

describe('GameCard with an unknown network', () => {
	const noNetwork: ScheduleGame = {
		...scheduled,
		status: { state: 'scheduled', tipTime: '9:00', tipSuffix: 'PM ET', network: null }
	};

	it('shows only the tip time on the mobile status line', () => {
		const { container } = render(GameCard, { props: { game: noNetwork, layout: 'mobile' } });
		expect(container.querySelector('.status-line')?.textContent?.trim()).toBe('9:00 PM ET');
	});

	it('hides the Broadcast fact', () => {
		const { container } = render(GameCard, {
			props: {
				game: withDetails(noNetwork, {
					kind: 'scheduled',
					venue: 'Crypto.com Arena',
					playersToWatch: { away: awayPlayer, home: homePlayer }
				}),
				layout: 'desktop',
				open: true
			}
		});
		expect(screen.queryByText('Broadcast')).toBeNull();
		expect(container.querySelectorAll('.fact').length).toBe(2);
	});
});
