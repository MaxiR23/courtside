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
// - A final game without stats: the line score and highlights stay, one muted line replaces the leaders and team stats, in English and Spanish
// - Highlights on final games only: videos, pending, play callback, player removed on close
// - Delayed, postponed and canceled games: status line only, no score, no tip time, no toggle
// - A scheduled game with no known network
// - Team names and monograms: plain text with no link inside the button of a card that expands; links to the team page on a card that cannot expand; line score and leader codes link in the open panel
// - Spoiler-free mode: final cards that can expand hide the score and the dimming until open
// - The Game center link on open live, final, final without stats and scheduled cards, after the stats, notice or players to watch; none without detailHref or on a card that cannot expand; Spanish copy
// - A guest without a code shows its initials in the tile and its name unlinked, and the loser dims from a side winner
// - A guest team (outside the league): its monogram and name are never links, the league ones link on a card that cannot expand, no color strip is drawn, a scheduled panel shows only the league player to watch, a final panel shows the leaders, line score and team stats of both sides
//
// What is covered:
// - Each card state on each row layout
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/GameCard.test.ts
//
// SEE: web/src/lib/components/GameCard.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { GameDetails, ScheduleGame } from '../../../src/lib/schedule/types';
import { preferLanguages } from '../../prefer-languages';

import GameCard from '../../../src/lib/components/GameCard.svelte';

const away = { code: 'GSW', name: 'Warriors', city: 'Golden State', guest: false };
const home = { code: 'LAL', name: 'Lakers', city: 'Los Angeles', guest: false };
const scheduled: ScheduleGame = {
	id: 's',
	away,
	home,
	status: { state: 'scheduled', tipTime: '9:00', tipSuffix: 'PM ET', network: 'Courtside TV' }
};
const live: ScheduleGame = {
	id: 'l',
	away,
	home,
	status: { state: 'live', period: 'Q3', clock: '4:12', awayScore: 78, homeScore: 74 }
};
const final = (awayScore: number, homeScore: number, winner: 'away' | 'home'): ScheduleGame => ({
	id: 'f',
	away,
	home,
	status: { state: 'final', awayScore, homeScore, winner }
});

const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	Reflect.deleteProperty(HTMLElement.prototype, 'animate');
});

const awayPlayer = { firstName: 'Stephen', lastName: 'Curry', teamCode: 'GSW', photo: '/away.svg' };
const homePlayer = { firstName: 'LeBron', lastName: 'James', teamCode: 'LAL', photo: '/home.svg' };
const leaderOf = (player: typeof awayPlayer, team: typeof away) => ({
	firstName: player.firstName,
	lastName: player.lastName,
	photo: player.photo,
	team
});
const played = (periodsAway: number[], periodsHome: number[]): GameDetails => ({
	kind: 'played',
	periods: { away: periodsAway, home: periodsHome },
	leaders: {
		away: { ...leaderOf(awayPlayer, away), points: 34, rebounds: 3, assists: 8 },
		home: { ...leaderOf(homePlayer, home), points: 29, rebounds: 9, assists: 7 }
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
	final(112, 104, 'away'),
	played([30, 28, 26, 28], [24, 27, 25, 28])
);
const overtimeWithDetails = withDetails(
	final(132, 130, 'away'),
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
const finalWithHighlights = withHighlights(final(112, 104, 'away'), [{ id: 'v1' }, { id: 'v2' }]);
const finalPending = withHighlights(final(112, 104, 'away'), []);
const withoutStats = (availability: 'pending' | 'unavailable'): ScheduleGame =>
	withDetails(final(112, 104, 'away'), {
		kind: 'final-without-stats',
		periods: { away: [30, 28, 26, 28], home: [24, 27, 25, 28] },
		statsAvailability: availability,
		highlights: highlightsData([])
	});
const HIGHLIGHTS = 'Highlights will appear here after the final buzzer.';

const dimmedText = (container: HTMLElement) =>
	[...container.querySelectorAll('.dimmed')].map((e) => e.textContent?.replace(/\s+/g, ' ').trim());

describe('GameCard', () => {
	it('shows the network on the status line and the tip time with its suffix on a scheduled game (desktop)', () => {
		const { container } = render(GameCard, {
			props: { teamHref, game: scheduled, layout: 'desktop' }
		});
		expect(container.querySelector('.status-line')?.textContent?.trim()).toBe('Courtside TV');
		expect(container.querySelector('.tip-time')?.textContent).toBe('9:00PM ET');
		expect(container.querySelector('.tip-time .suffix')?.textContent).toBe('PM ET');
		expect(container.querySelector('.score')).toBeNull();
	});

	it('shows "9:00 PM ET · Courtside TV" on the status line of a scheduled game (mobile)', () => {
		const { container } = render(GameCard, {
			props: { teamHref, game: scheduled, layout: 'mobile' }
		});
		expect(container.querySelector('.status-line')?.textContent?.trim()).toBe(
			'9:00 PM ET · Courtside TV'
		);
		expect(container.querySelector('.score')).toBeNull();
	});

	it.each(['desktop', 'mobile'] as const)(
		'shows the live badge with the period and clock on a live game (%s)',
		(layout) => {
			const { container } = render(GameCard, { props: { teamHref, game: live, layout } });
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
			const { container } = render(GameCard, {
				props: { teamHref, game: final(112, 104, 'away'), layout }
			});
			expect(container.querySelector('.status-line')?.textContent?.trim()).toBe('Final');
			expect([...container.querySelectorAll('.score')].map((e) => e.textContent)).toEqual([
				'112',
				'104'
			]);
		}
	);

	it('dims the team that is not the winner on a final game, home and away winners', () => {
		const desktop = render(GameCard, {
			props: { teamHref, game: final(98, 104, 'home'), layout: 'desktop' }
		});
		const text = dimmedText(desktop.container);
		expect(text.some((t) => t?.includes('Warriors'))).toBe(true);
		expect(text).toContain('98');
		expect(text.some((t) => t?.includes('Lakers'))).toBe(false);
		expect(text).not.toContain('104');
		desktop.unmount();

		const { container } = render(GameCard, {
			props: { teamHref, game: final(112, 104, 'away'), layout: 'mobile' }
		});
		const mobile = dimmedText(container);
		expect(mobile.some((t) => t?.includes('Lakers'))).toBe(true);
		expect(mobile).toContain('104');
		expect(mobile.some((t) => t?.includes('Warriors'))).toBe(false);
		expect(mobile).not.toContain('112');
	});

	it.each([
		['desktop', final(98, 104, 'home')],
		['mobile', final(112, 104, 'away')]
	] as const)("does not dim the losing team's monogram on the %s row", (layout, game) => {
		const { container } = render(GameCard, { props: { teamHref, game, layout } });
		expect(container.querySelectorAll('.team-monogram').length).toBeGreaterThan(0);
		expect(container.querySelectorAll('.dimmed .team-monogram')).toHaveLength(0);
		const text = dimmedText(container);
		expect(text.length).toBeGreaterThan(0);
		expect(text.some((t) => t?.includes(layout === 'desktop' ? 'Warriors' : 'Lakers'))).toBe(true);
	});

	it('dims the team that is not the winner even when its score is higher', () => {
		for (const layout of ['desktop', 'mobile'] as const) {
			const { container, unmount } = render(GameCard, {
				props: { teamHref, game: final(98, 104, 'away'), layout }
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
		const { container } = render(GameCard, { props: { teamHref, game: live, layout: 'desktop' } });
		expect(container.querySelectorAll('.dimmed')).toHaveLength(0);
	});

	it('uses the large monograms on the desktop row and the small ones on the mobile row', () => {
		const desktop = render(GameCard, { props: { teamHref, game: scheduled, layout: 'desktop' } });
		expect(desktop.container.querySelectorAll('.team-monogram.large')).toHaveLength(2);
		expect(desktop.container.querySelectorAll('.team-monogram.small')).toHaveLength(0);
		desktop.unmount();
		const { container } = render(GameCard, {
			props: { teamHref, game: scheduled, layout: 'mobile' }
		});
		expect(container.querySelectorAll('.team-monogram.small')).toHaveLength(2);
		expect(container.querySelectorAll('.team-monogram.large')).toHaveLength(0);
	});

	it('shows a decorative chevron', () => {
		for (const layout of ['desktop', 'mobile'] as const) {
			const { container, unmount } = render(GameCard, {
				props: { teamHref, game: scheduled, layout }
			});
			expect(container.querySelector('svg.chevron')?.getAttribute('aria-hidden')).toBe('true');
			unmount();
		}
	});

	it('shows the live badge in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		render(GameCard, { props: { teamHref, game: live, layout: 'desktop' } });
		expect(screen.getByText('EN VIVO')).toBeTruthy();
	});

	it('keeps a plain row with no toggle when the game has no details', () => {
		const { container } = render(GameCard, {
			props: { teamHref, game: scheduled, layout: 'desktop' }
		});
		expect(container.querySelector('button')).toBeNull();
		expect(container.querySelector('.panel')).toBeNull();
	});

	it('renders the row as a collapsed toggle with its panel inert when closed', () => {
		const { container } = render(GameCard, {
			props: { teamHref, game: liveWithDetails, layout: 'desktop' }
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
			props: { teamHref, game: liveWithDetails, layout: 'desktop', onToggle }
		});
		await fireEvent.click(container.querySelector('button.toggle') as HTMLElement);
		expect(onToggle).toHaveBeenCalledTimes(1);
	});

	it('shows the accent border, the open class and an active panel when open', () => {
		const { container } = render(GameCard, {
			props: { teamHref, game: liveWithDetails, layout: 'desktop', open: true }
		});
		expect(container.querySelector('.blueprint-frame.active')).not.toBeNull();
		expect(container.querySelector('.card.open')).not.toBeNull();
		expect((container.querySelector('.panel') as HTMLElement).inert).toBe(false);
		expect(container.querySelector('button.toggle')?.getAttribute('aria-expanded')).toBe('true');
	});

	it('shows the line score, leaders and team stats on a live game, plus the highlights notice', () => {
		const { container } = render(GameCard, {
			props: { teamHref, game: liveWithDetails, layout: 'desktop', open: true }
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
			props: { teamHref, game: finalWithDetails, layout: 'desktop', open: true }
		});
		expect(container.querySelector('.line-score')).not.toBeNull();
		expect(container.querySelector('.leaders')).not.toBeNull();
		expect(container.querySelector('.team-stats')).not.toBeNull();
		expect(screen.queryByText(HIGHLIGHTS)).toBeNull();
	});

	it('shows the overtime columns on a final game that went to overtime', () => {
		const { container } = render(GameCard, {
			props: { teamHref, game: overtimeWithDetails, layout: 'desktop', open: true }
		});
		const header = [...container.querySelectorAll('.line-score .head .cell')].map(
			(e) => e.textContent
		);
		expect(header).toEqual(['1', '2', '3', '4', 'OT', '2OT', 'T']);
	});

	it('shows Tip-off, Venue, Broadcast and the players to watch on a scheduled game', () => {
		const { container } = render(GameCard, {
			props: { teamHref, game: scheduledWithDetails, layout: 'desktop', open: true }
		});
		const facts = [...container.querySelectorAll('.fact')].map((e) =>
			[...e.children].map((c) => c.textContent)
		);
		expect(facts).toEqual([
			['Tip-off', '9:00 PM ET'],
			['Venue', 'Crypto.com Arena'],
			['Broadcast', 'Courtside TV']
		]);
		expect(screen.getByText('Players to watch')).toBeTruthy();
		expect(screen.getByText('Stephen Curry')).toBeTruthy();
		expect(screen.getByText('LeBron James')).toBeTruthy();
	});

	it('animates the panel when it opens and not with reduced motion', async () => {
		const animate = vi.fn(() => ({ cancel: vi.fn() }));
		Object.assign(HTMLElement.prototype, { animate });
		vi.stubGlobal('matchMedia', () => ({ matches: false }));
		const props = { teamHref, game: liveWithDetails, layout: 'desktop' as const };
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
			props: { teamHref, game: scheduledWithDetails, layout: 'desktop', open: true }
		});
		expect(screen.getByText('Inicio')).toBeTruthy();
		expect(screen.getByText('Estadio')).toBeTruthy();
		expect(screen.getByText('Transmisión')).toBeTruthy();
		expect(screen.getByText('Jugadores a seguir')).toBeTruthy();
		expect(container.querySelector('.fact dd')?.textContent).toBe('9:00 PM ET');
	});

	it('shows the highlights after the stats on an open final game with highlights', () => {
		const { container } = render(GameCard, {
			props: { teamHref, game: finalWithHighlights, layout: 'desktop', open: true }
		});
		const section = container.querySelector('.panel-highlights');
		expect(section).not.toBeNull();
		expect(section?.querySelectorAll('li')).toHaveLength(2);
		expect(screen.getByText('Clip v1')).toBeTruthy();
		const grid = container.querySelector('.panel-grid');
		expect(grid?.compareDocumentPosition(section as Node)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
	});

	it('shows "Stats will be available soon." in place of the leaders and team stats on a final game with pending stats', () => {
		const { container } = render(GameCard, {
			props: { teamHref, game: withoutStats('pending'), layout: 'desktop', open: true }
		});
		expect(screen.getByText('Stats will be available soon.')).toBeTruthy();
		expect(screen.queryByText("Stats aren't available for this game.")).toBeNull();
		expect(container.querySelector('.line-score')).not.toBeNull();
		expect(container.querySelector('.leaders')).toBeNull();
		expect(container.querySelector('.team-stats')).toBeNull();
		expect(container.querySelector('.panel-highlights')).not.toBeNull();
	});

	it('shows "Stats aren\'t available for this game." on a final game with unavailable stats', () => {
		const { container } = render(GameCard, {
			props: { teamHref, game: withoutStats('unavailable'), layout: 'desktop', open: true }
		});
		expect(screen.getByText("Stats aren't available for this game.")).toBeTruthy();
		expect(screen.queryByText('Stats will be available soon.')).toBeNull();
		expect(container.querySelector('.leaders')).toBeNull();
	});

	it('shows both stats messages in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		render(GameCard, {
			props: { teamHref, game: withoutStats('pending'), layout: 'desktop', open: true }
		});
		expect(screen.getByText('Las estadísticas estarán disponibles pronto.')).toBeTruthy();
		render(GameCard, {
			props: { teamHref, game: withoutStats('unavailable'), layout: 'desktop', open: true }
		});
		expect(
			screen.getByText('Las estadísticas no están disponibles para este partido.')
		).toBeTruthy();
	});

	it('keeps the score and the toggle of a final game without stats', async () => {
		const onToggle = vi.fn();
		const { container } = render(GameCard, {
			props: { teamHref, game: withoutStats('pending'), layout: 'desktop', onToggle }
		});
		expect([...container.querySelectorAll('.score')].map((e) => e.textContent)).toEqual([
			'112',
			'104'
		]);
		const toggle = container.querySelector('button.toggle');
		expect(toggle?.getAttribute('aria-expanded')).toBe('false');
		await fireEvent.click(toggle as HTMLButtonElement);
		expect(onToggle).toHaveBeenCalledTimes(1);
	});

	it('shows the pending highlights state on a final game whose highlights are not in yet', () => {
		const { container } = render(GameCard, {
			props: { teamHref, game: finalPending, layout: 'desktop', open: true }
		});
		expect(
			screen.getByText("Highlights aren't in yet. They'll appear here automatically.")
		).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Search highlights on Test platform' })).toBeTruthy();
		expect(container.querySelector('.panel-highlights img')).toBeNull();
	});

	it('shows no highlights section on a final game without highlights', () => {
		const { container } = render(GameCard, {
			props: { teamHref, game: finalWithDetails, layout: 'desktop', open: true }
		});
		expect(container.querySelector('.highlights')).toBeNull();
	});

	it('shows no highlights section on a live game, only the notice', () => {
		const liveWithHighlights = withHighlights(live, [{ id: 'v1' }]);
		const { container } = render(GameCard, {
			props: { teamHref, game: liveWithHighlights, layout: 'desktop', open: true }
		});
		expect(container.querySelector('.highlights')).toBeNull();
		expect(screen.getByText(HIGHLIGHTS)).toBeTruthy();
	});

	it('calls onPlay with the video id when a highlight thumbnail is clicked', async () => {
		const onPlay = vi.fn();
		render(GameCard, {
			props: { teamHref, game: finalWithHighlights, layout: 'desktop', open: true, onPlay }
		});
		await fireEvent.click(screen.getByRole('button', { name: 'Play Clip v2' }));
		expect(onPlay).toHaveBeenCalledWith('v2');
	});

	it('shows the player for playingVideoId while open and removes it when the card closes', async () => {
		const props = {
			teamHref,
			game: finalWithHighlights,
			layout: 'desktop' as const,
			playingVideoId: 'v1'
		};
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
				const props = { teamHref, game: finalWithDetails, layout, spoilerFree: true };
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
			const game = withDetails(final(98, 104, 'home'), played([30, 28, 20, 20], [24, 27, 25, 28]));
			const props = { teamHref, game, layout: 'desktop' as const, spoilerFree: true };
			const { container, rerender } = render(GameCard, { props });
			expect(container.querySelectorAll('.dimmed')).toHaveLength(0);
			await rerender({ ...props, open: true });
			expect(dimmedText(container)).toContain('98');
		});

		it('hides the score again when the expanded card is collapsed', async () => {
			const props = {
				teamHref,
				game: finalWithDetails,
				layout: 'desktop' as const,
				spoilerFree: true
			};
			const { container, rerender } = render(GameCard, {
				props: { ...props, open: true }
			});
			expect(row(container).querySelector('.score')).not.toBeNull();
			await rerender({ ...props, open: false });
			expect(row(container).querySelector('.score')).toBeNull();
		});

		it('leaves live and scheduled cards unchanged in spoiler-free mode', () => {
			const liveCard = render(GameCard, {
				props: { teamHref, game: liveWithDetails, layout: 'desktop', spoilerFree: true }
			});
			expect(row(liveCard.container).textContent).toContain('78');
			expect(row(liveCard.container).textContent).not.toContain('Tap to reveal');
			liveCard.unmount();
			const next = render(GameCard, {
				props: { teamHref, game: scheduledWithDetails, layout: 'desktop', spoilerFree: true }
			});
			expect(next.container.querySelector('.tip-time')?.textContent).toBe('9:00PM ET');
			expect(next.container.textContent).not.toContain('Tap to reveal');
		});

		it('keeps the score on a final card that cannot expand', () => {
			const { container } = render(GameCard, {
				props: { teamHref, game: final(112, 104, 'away'), layout: 'desktop', spoilerFree: true }
			});
			expect(container.querySelectorAll('.score')).toHaveLength(2);
			expect(container.textContent).not.toContain('Tap to reveal');
		});

		it('shows Toca para ver with a Spanish preference', () => {
			preferLanguages(['es-ES']);
			const { container } = render(GameCard, {
				props: { teamHref, game: finalWithDetails, layout: 'desktop', spoilerFree: true }
			});
			expect(row(container).textContent).toContain('Toca para ver');
		});
	});
});

describe('GameCard game center link', () => {
	const href = '/game/abc' as ResolvedPathname;
	const cases = [
		['live', liveWithDetails, '.team-stats'],
		['final', finalWithDetails, '.team-stats'],
		['final without stats', withoutStats('pending'), '.stats-notice'],
		['scheduled', scheduledWithDetails, '.watch']
	] as const;

	it.each(cases)(
		'links an open %s card to its detail page, after its last block',
		(_n, game, before) => {
			const { container } = render(GameCard, {
				props: { teamHref, game, layout: 'desktop', open: true, detailHref: href }
			});
			const link = screen.getByRole('link', { name: 'Game center' });
			expect(link.getAttribute('href')).toBe('/game/abc');
			expect(link.getAttribute('target')).toBeNull();
			const previous = container.querySelector(before) as Element;
			expect(
				previous.compareDocumentPosition(link) & Node.DOCUMENT_POSITION_FOLLOWING
			).toBeTruthy();
			expect(link.querySelector('svg')?.getAttribute('aria-hidden')).toBe('true');
		}
	);

	it('shows no link without a detailHref', () => {
		render(GameCard, {
			props: { teamHref, game: finalWithDetails, layout: 'desktop', open: true }
		});
		expect(screen.queryByRole('link', { name: 'Game center' })).toBeNull();
	});

	it('shows no link on a delayed card, which does not expand', () => {
		render(GameCard, {
			props: {
				teamHref,
				game: { id: 'd', away, home, status: { state: 'delayed' } },
				layout: 'desktop',
				detailHref: href
			}
		});
		expect(screen.queryByRole('link', { name: 'Game center' })).toBeNull();
	});

	it('shows the link in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		render(GameCard, {
			props: { teamHref, game: finalWithDetails, layout: 'desktop', open: true, detailHref: href }
		});
		expect(screen.getByRole('link', { name: 'Centro del partido' })).toBeTruthy();
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
				props: { teamHref, game: inState(state), layout }
			});
			expect(container.querySelector('.status-line')?.textContent?.trim()).toBe(english);
			expect(container.querySelector('.score')).toBeNull();
			expect(container.querySelector('.tip-time')).toBeNull();
			unmount();
		}
	});

	it.each(labels)('shows %s in Spanish', (state, _label, spanish) => {
		preferLanguages(['es-ES']);
		const { container } = render(GameCard, {
			props: { teamHref, game: inState(state), layout: 'desktop' }
		});
		expect(container.querySelector('.status-line')?.textContent?.trim()).toBe(spanish);
	});

	it.each(labels)('keeps %s as a plain row with no toggle', (state) => {
		const { container } = render(GameCard, {
			props: { teamHref, game: inState(state), layout: 'desktop' }
		});
		expect(container.querySelector('button.toggle')).toBeNull();
	});
});

describe('GameCard with an unknown network', () => {
	const noNetwork: ScheduleGame = {
		...scheduled,
		status: { state: 'scheduled', tipTime: '9:00', tipSuffix: 'PM ET', network: null }
	};

	it('shows only the tip time on the mobile status line', () => {
		const { container } = render(GameCard, {
			props: { teamHref, game: noNetwork, layout: 'mobile' }
		});
		expect(container.querySelector('.status-line')?.textContent?.trim()).toBe('9:00 PM ET');
	});

	it('hides the Broadcast fact', () => {
		const { container } = render(GameCard, {
			props: {
				teamHref,
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

	describe('team links', () => {
		it.each(['desktop', 'mobile'] as const)(
			"keeps an expandable row's team names as plain text with no link inside the button (%s)",
			(layout) => {
				for (const game of [scheduledWithDetails, liveWithDetails, finalWithDetails]) {
					const { container, unmount } = render(GameCard, {
						props: { teamHref, game, layout }
					});
					expect(container.querySelectorAll('button a')).toHaveLength(0);
					expect(container.querySelector('button')?.textContent).toContain('Warriors');
					unmount();
				}
			}
		);

		it.each(['desktop', 'mobile'] as const)(
			"links a delayed, postponed or canceled card's team names and codes to the team page (%s)",
			(layout) => {
				for (const state of ['delayed', 'postponed', 'canceled'] as const) {
					const game = { ...scheduled, status: { state } } as ScheduleGame;
					const { unmount } = render(GameCard, { props: { teamHref, game, layout } });
					for (const name of ['GSW', 'Warriors']) {
						expect(screen.getByRole('link', { name }).getAttribute('href')).toBe('/team/gsw');
					}
					for (const name of ['LAL', 'Lakers']) {
						expect(screen.getByRole('link', { name }).getAttribute('href')).toBe('/team/lal');
					}
					unmount();
				}
			}
		);

		it("links the expanded panel's line score and leader codes", () => {
			const { container } = render(GameCard, {
				props: { teamHref, game: finalWithDetails, layout: 'desktop', open: true }
			});
			expect(container.querySelectorAll('button a')).toHaveLength(0);
			const links = [...container.querySelectorAll('.panel a')].map((a) => [
				a.textContent,
				a.getAttribute('href')
			]);
			expect(links).toEqual(
				expect.arrayContaining([
					['GSW', '/team/gsw'],
					['LAL', '/team/lal']
				])
			);
			expect(container.querySelectorAll('.leader-code a')).toHaveLength(2);
			expect(container.querySelectorAll('.line-score a')).toHaveLength(2);
		});
	});
});

describe('GameCard with a guest team', () => {
	const guest = { code: 'HCM', name: 'Mariners', city: 'Harbor City', guest: true };
	const delayed: ScheduleGame = { id: 'd', away: guest, home, status: { state: 'delayed' } };

	it('keeps the guest monogram and name as plain text and links the league ones', () => {
		for (const layout of ['desktop', 'mobile'] as const) {
			const { container, unmount } = render(GameCard, {
				props: { teamHref, game: delayed, layout }
			});
			expect(screen.queryByRole('link', { name: 'HCM' })).toBeNull();
			expect(screen.queryByRole('link', { name: 'Mariners' })).toBeNull();
			expect(screen.getByText('HCM').tagName).toBe('SPAN');
			expect(screen.getByRole('link', { name: 'LAL' }).getAttribute('href')).toBe('/team/lal');
			expect(screen.getByRole('link', { name: 'Lakers' }).getAttribute('href')).toBe('/team/lal');
			expect(container.querySelector('[class*="strip"]')).toBeNull();
			unmount();
		}
	});

	it('shows only the league player to watch of a scheduled guest game', () => {
		const game = withDetails(
			{ ...scheduled, away: guest },
			{
				kind: 'scheduled',
				venue: 'Test Arena',
				playersToWatch: { away: null, home: homePlayer }
			}
		);
		const { container } = render(GameCard, {
			props: { teamHref, game, layout: 'desktop', open: true }
		});
		expect(container.querySelectorAll('.watch-player')).toHaveLength(1);
		expect(screen.getByText('LeBron James')).toBeTruthy();
	});

	it('shows the leaders, line score and team stats of both sides of a final guest game, the guest code unlinked', () => {
		const details = played([28, 26, 24, 34], [25, 27, 22, 30]);
		if (details.kind !== 'played') throw new Error('Expected played details');
		details.leaders.away = {
			...details.leaders.away,
			team: guest,
			photo: null
		};
		const game = withDetails({ ...final(112, 104, 'away'), away: guest }, details);
		const { container } = render(GameCard, {
			props: { teamHref, game, layout: 'desktop', open: true }
		});
		expect(container.querySelectorAll('.leader')).toHaveLength(2);
		expect(container.querySelectorAll('.line-score .line:not(.head)')).toHaveLength(2);
		expect(container.querySelector('.stats-column')).not.toBeNull();
		const links = [...container.querySelectorAll('.panel a')].map((a) => a.textContent);
		expect(links).toContain('LAL');
		expect(links).not.toContain('HCM');
		expect(container.querySelectorAll('.leader')[0].querySelector('img')).toBeNull();
	});
});

describe('GameCard with a guest team without a code', () => {
	const codeless = { code: null, name: 'Mariners', city: 'Harbor City', guest: true };

	it('shows the initials of the guest in its tile and its name as plain text', () => {
		const game: ScheduleGame = { id: 'c', away: codeless, home, status: { state: 'delayed' } };
		for (const layout of ['desktop', 'mobile'] as const) {
			const { unmount } = render(GameCard, { props: { teamHref, game, layout } });
			expect(screen.getByText('HM').classList.contains('team-monogram')).toBe(true);
			expect(screen.queryByRole('link', { name: 'HM' })).toBeNull();
			expect(screen.queryByRole('link', { name: 'Mariners' })).toBeNull();
			expect(screen.getByRole('link', { name: 'Lakers' }).getAttribute('href')).toBe('/team/lal');
			unmount();
		}
	});

	it('dims the guest when the home side wins and the home side when the guest wins', () => {
		const lost = render(GameCard, {
			props: {
				teamHref,
				game: { ...final(98, 104, 'home'), away: codeless },
				layout: 'desktop'
			}
		});
		expect(dimmedText(lost.container).some((t) => t?.includes('Mariners'))).toBe(true);
		expect(dimmedText(lost.container).some((t) => t?.includes('Lakers'))).toBe(false);
		lost.unmount();
		const won = render(GameCard, {
			props: {
				teamHref,
				game: { ...final(112, 104, 'away'), away: codeless },
				layout: 'desktop'
			}
		});
		expect(dimmedText(won.container).some((t) => t?.includes('Lakers'))).toBe(true);
		expect(dimmedText(won.container).some((t) => t?.includes('Mariners'))).toBe(false);
	});
});
