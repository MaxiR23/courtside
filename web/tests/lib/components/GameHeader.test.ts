// web/tests/lib/components/GameHeader.test.ts
//
// Tests for the GameHeader component.
//
// Tested:
// - The team monogram and name link to the team page, on desktop and mobile
// - The nav row: the brand and an All games link to the home; alone with no header
// - The skeleton under the nav row while loading, busy and hidden from assistive tech
// - The desktop row in every status: scheduled, delayed, postponed, canceled, live and final
// - The loser dimmed on a final game, on the block and on the score
// - The mobile rows: two team rows with "city · record" and the score; the time row before a game
// - The venue strip in three states: the photo with its gradient, no photo, and a photo that fails to load (the grid with
//   the arena name and city); without a city, the arena name alone in the caption and no sub-line under the Venue cell
// - Each team name in full, in its own level 1 heading
// - A guest team: the monogram and name are plain text and no record is shown, on desktop and mobile
// - A guest without a code shows the initials of its name in the monogram and its name as plain text, on desktop and mobile
// - The Cup tag first in the status line, before the live badge, the date and the venue; none for a game without the mark
// - The postseason mark first in the status line, before the live badge and the status text, for a scheduled and a live game; none for a regular game; the Cup tag unchanged
// - The All-Star mark first in the status line of a scheduled game, then the round, the solid tag for the Championship, none without the mark, and no city for a guest side without one
// - The team logos: the feed logo in the header and header-mobile boxes, a guest drawing its monogram
//
// What is covered:
// - Each state the header shows
// - Word breaking is CSS and jsdom does no layout: it is checked with a grep (see the plan)
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/GameHeader.test.ts
//
// SEE: web/src/lib/components/GameHeader.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import GameHeader from '../../../src/lib/components/GameHeader.svelte';
import type { GameHeaderView } from '../../../src/lib/game/types';
import type { RowLayout } from '../../../src/lib/schedule/types';

const HOME = '/' as ResolvedPathname;
const STANDINGS = '/standings' as ResolvedPathname;
const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;

const away = { code: 'LAL', name: 'Lakers', city: 'Los Angeles', record: '12–5', guest: false };
const home = { code: 'GSW', name: 'Warriors', city: 'Golden State', record: '10–7', guest: false };

const venue = {
	arena: 'Chase Center',
	city: 'San Francisco',
	photo: '/highlight-1.svg',
	cells: [
		{ label: 'Tip-off', value: '7:00 PM ET', sub: 'Wednesday, October 7' },
		{ label: 'Venue', value: 'Chase Center', sub: 'San Francisco' },
		{ label: 'Broadcast', value: 'Network One', sub: null }
	]
};

const scheduled: GameHeaderView = {
	layout: 'pre-game',
	status: { state: 'scheduled', text: 'Wednesday, October 7 · Chase Center' },
	cupTag: null,
	postseasonMark: null,
	allStarMark: null,
	away,
	home,
	center: {
		kind: 'tip-off',
		tipTime: '7:00',
		tipSuffix: 'PM ET',
		broadcast: 'Network One',
		delayed: false
	},
	venue
};

const live: GameHeaderView = {
	layout: 'live',
	status: { state: 'live', text: 'Q3 · 4:12 · Chase Center' },
	cupTag: null,
	postseasonMark: null,
	allStarMark: null,
	away,
	home,
	center: { kind: 'score', away: 63, home: 62, loser: null },
	venue: null
};

const final: GameHeaderView = {
	layout: 'final',
	status: { state: 'final', text: 'Final · Wednesday, October 7 · Chase Center' },
	cupTag: null,
	postseasonMark: null,
	allStarMark: null,
	away,
	home,
	center: { kind: 'score', away: 110, home: 98, loser: 'home' },
	venue: null
};

function show(header: GameHeaderView | null, layout: RowLayout = 'desktop', loading = false) {
	return render(GameHeader, {
		props: {
			header,
			allGamesHref: HOME,
			standingsHref: STANDINGS,
			layout,
			loading,
			teamHref
		}
	});
}

describe('GameHeader', () => {
	it('shows the brand and an All games link to the home in the nav row', () => {
		show(null);
		expect(screen.getByText('Courtside')).toBeTruthy();
		expect(screen.getByRole('link', { name: 'All games' }).getAttribute('href')).toBe('/');
		expect(screen.getByRole('link', { name: 'Standings' }).getAttribute('href')).toBe('/standings');
		const cup = screen.getByRole('link', { name: 'Cup' });
		expect(cup.getAttribute('href')).toBe('/cup');
		expect(cup.getAttribute('aria-current')).toBeNull();
		expect(document.querySelector('[aria-current]')).toBeNull();
	});

	it('shows only the nav row with no header', () => {
		const { container } = show(null);
		expect(container.querySelector('.status-line')).toBeNull();
		expect(container.querySelector('.skeleton')).toBeNull();
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBeNull();
		expect(screen.queryAllByRole('heading')).toHaveLength(0);
	});

	it('shows the skeleton with the nav row while loading', () => {
		const { container } = show(null, 'desktop', true);
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('.skeleton')?.getAttribute('aria-hidden')).toBe('true');
		expect(container.querySelectorAll('.skeleton .bone').length).toBeGreaterThan(0);
		expect(screen.getByRole('link', { name: 'All games' })).toBeTruthy();
	});

	it('shows a scheduled game on the desktop row with its tip time, broadcast and venue strip', () => {
		const { container } = show(scheduled);
		expect(screen.getByText('Wednesday, October 7 · Chase Center')).toBeTruthy();
		expect(container.querySelector('.tip-time')?.textContent).toBe('7:00 PM ET');
		expect(container.querySelector('.broadcast')?.textContent).toBe('Network One');
		expect(container.querySelectorAll('.cell')).toHaveLength(3);
		expect(screen.getByText('Tip-off')).toBeTruthy();
		expect(screen.getByText('Los Angeles')).toBeTruthy();
		expect(screen.getByText('12–5')).toBeTruthy();
		expect(container.querySelector('.status-tag')).toBeNull();
		expect(container.querySelector('.live-badge')).toBeNull();
	});

	it('shows the arena name alone in the caption and no sub-line under the Venue cell when the city is null', () => {
		const { container } = show({
			...scheduled,
			venue: {
				...venue,
				city: null,
				cells: venue.cells.map((cell) => (cell.label === 'Venue' ? { ...cell, sub: null } : cell))
			}
		});
		expect(container.querySelector('.caption .arena')?.textContent).toBe('Chase Center');
		expect(container.querySelector('.caption .arena-city')).toBeNull();
		const cell = [...container.querySelectorAll('.cell')].find(
			(c) => c.querySelector('.cell-label')?.textContent === 'Venue'
		);
		expect(cell?.querySelector('.cell-value')?.textContent).toBe('Chase Center');
		expect(cell?.querySelector('.cell-sub')).toBeNull();
		expect(cell?.textContent).not.toContain('·');
	});

	it('shows a delayed game with its tag and "Scheduled" before the time', () => {
		const { container } = show({
			...scheduled,
			status: { state: 'delayed', text: 'Wednesday, October 7 · Chase Center' },
			center: {
				kind: 'tip-off',
				tipTime: '7:00',
				tipSuffix: 'PM ET',
				broadcast: null,
				delayed: true
			}
		});
		expect(container.querySelector('.status-tag')?.textContent).toBe('Delayed');
		expect(screen.getByText('Scheduled')).toBeTruthy();
		expect(container.querySelector('.broadcast')).toBeNull();
	});

	it('shows postponed and canceled games with their tag and no time', () => {
		for (const [state, label] of [
			['postponed', 'Postponed'],
			['canceled', 'Canceled']
		] as const) {
			const { container, unmount } = show({
				...scheduled,
				status: { state, text: 'Wednesday, October 7 · Chase Center' },
				center: { kind: 'none' }
			});
			expect(container.querySelector('.status-tag')?.textContent).toBe(label);
			expect(container.querySelector('.tip-time')).toBeNull();
			expect(container.querySelector('.score')).toBeNull();
			unmount();
		}
	});

	it('shows a live game with the badge, the period text and the score', () => {
		const { container } = show(live);
		expect(container.querySelector('.live-badge')).not.toBeNull();
		expect(screen.getByText('Q3 · 4:12 · Chase Center')).toBeTruthy();
		const points = [...container.querySelectorAll('.points')].map((el) => el.textContent);
		expect(points).toEqual(['63', '62']);
		expect(container.querySelector('.dimmed')).toBeNull();
		expect(container.querySelector('.venue')).toBeNull();
	});

	it('shows a final game with the loser dimmed on its block and its score', () => {
		const { container } = show(final);
		expect(screen.getByText('Final · Wednesday, October 7 · Chase Center')).toBeTruthy();
		expect(container.querySelector('.team.home')?.classList.contains('dimmed')).toBe(true);
		expect(container.querySelector('.team.away')?.classList.contains('dimmed')).toBe(false);
		const [awayPoints, homePoints] = [...container.querySelectorAll('.points')];
		expect(awayPoints.classList.contains('dimmed')).toBe(false);
		expect(homePoints.classList.contains('dimmed')).toBe(true);
	});

	it('shows two team rows with city · record and the score on the mobile row', () => {
		const { container } = show(final, 'mobile');
		expect(container.querySelectorAll('.row')).toHaveLength(2);
		expect(container.querySelector('.scoreboard')).toBeNull();
		expect(screen.getByText('Los Angeles · 12–5')).toBeTruthy();
		expect(screen.getByText('Golden State · 10–7')).toBeTruthy();
		const [awayPoints, homePoints] = [...container.querySelectorAll('.points')];
		expect(awayPoints.textContent).toBe('110');
		expect(homePoints.textContent).toBe('98');
		const rows = container.querySelectorAll('.row');
		expect(rows[0].classList.contains('dimmed')).toBe(false);
		expect(rows[1].classList.contains('dimmed')).toBe(true);
	});

	it('adds the time row on the mobile pre-game row', () => {
		const { container } = show(scheduled, 'mobile');
		expect(container.querySelectorAll('.row')).toHaveLength(2);
		expect(container.querySelector('.tip-off.mobile .tip-time')?.textContent).toBe('7:00 PM ET');
		expect(container.querySelector('.broadcast')?.textContent).toBe('Network One');
		expect(container.querySelector('.points')).toBeNull();
	});

	it('shows the arena photo with the gradient and its name and city over it', () => {
		const { container } = show(scheduled);
		const img = container.querySelector('.photo-box img');
		expect(img?.getAttribute('src')).toBe('/highlight-1.svg');
		expect(img?.getAttribute('alt')).toBe('');
		expect(container.querySelector('.photo-box .fade')).not.toBeNull();
		expect(container.querySelector('.caption .arena')?.textContent).toBe('Chase Center');
		expect(container.querySelector('.caption .arena-city')?.textContent).toBe('San Francisco');
		expect(container.querySelector('.bare-grid')).toBeNull();
	});

	it('shows the grid with the arena name and city and no gradient without a photo', () => {
		const { container } = show({ ...scheduled, venue: { ...venue, photo: null } });
		expect(container.querySelector('.photo-box img')).toBeNull();
		expect(container.querySelector('.photo-box .fade')).toBeNull();
		expect(container.querySelector('.photo-box .bare-grid')).not.toBeNull();
		expect(container.querySelector('.photo-box .caption .arena')?.textContent).toBe('Chase Center');
		expect(container.querySelector('.photo-box .caption .arena-city')?.textContent).toBe(
			'San Francisco'
		);
	});

	it('shows the arena name alone over the grid without a photo or a city', () => {
		const { container } = show({ ...scheduled, venue: { ...venue, photo: null, city: null } });
		expect(container.querySelector('.caption .arena')?.textContent).toBe('Chase Center');
		expect(container.querySelector('.caption .arena-city')).toBeNull();
		expect(container.querySelector('.bare-grid')).not.toBeNull();
	});

	it('falls back to the grid with the arena name and city when the photo fails to load', async () => {
		const { container } = show(scheduled);
		const img = container.querySelector('.photo-box img');
		expect(img).not.toBeNull();
		await fireEvent.error(img as Element);
		expect(container.querySelector('.photo-box img')).toBeNull();
		expect(container.querySelector('.photo-box .fade')).toBeNull();
		expect(container.querySelector('.bare-grid')).not.toBeNull();
		expect(container.querySelector('.caption .arena')?.textContent).toBe('Chase Center');
		expect(container.querySelector('.caption .arena-city')?.textContent).toBe('San Francisco');
	});

	it('tries the photo again when its URL changes after a failure', async () => {
		const { container, rerender } = show(scheduled);
		await fireEvent.error(container.querySelector('.photo-box img') as Element);
		await rerender({
			header: { ...scheduled, venue: { ...venue, photo: '/other.svg' } },
			allGamesHref: HOME,
			standingsHref: STANDINGS,
			layout: 'desktop',
			loading: false
		});
		expect(container.querySelector('.photo-box img')?.getAttribute('src')).toBe('/other.svg');
	});

	it('renders each team name in full in its own heading', () => {
		for (const layout of ['desktop', 'mobile'] as const) {
			const { unmount } = show(
				{
					...live,
					away: { ...away, name: 'Timberwolves' },
					home: { ...home, name: 'Trail Blazers' }
				},
				layout
			);
			const names = screen.getAllByRole('heading', { level: 1 }).map((h) => h.textContent);
			expect(names).toEqual(['Timberwolves', 'Trail Blazers']);
			unmount();
		}
	});

	it.each<RowLayout>(['desktop', 'mobile'])(
		'links the team monogram and name to the team page on %s',
		(layout) => {
			show(scheduled, layout);
			const lal = screen.getAllByRole('link', { name: /^(LAL|Lakers)$/ });
			const gsw = screen.getAllByRole('link', { name: /^(GSW|Warriors)$/ });
			expect(lal).toHaveLength(2);
			expect(gsw).toHaveLength(2);
			for (const link of lal) expect(link.getAttribute('href')).toBe('/team/lal');
			for (const link of gsw) expect(link.getAttribute('href')).toBe('/team/gsw');
		}
	);
});

describe('GameHeader with a guest team', () => {
	const guest = { code: 'HCM', name: 'Mariners', city: 'Harbor City', record: null, guest: true };
	const guestHeader: GameHeaderView = { ...live, away: guest };

	it('shows the guest monogram and name as plain text with no record on desktop', () => {
		const { container } = show(guestHeader, 'desktop');
		expect(screen.queryByRole('link', { name: 'HCM' })).toBeNull();
		expect(screen.queryByRole('link', { name: 'Mariners' })).toBeNull();
		expect(screen.getByText('HCM').tagName).toBe('SPAN');
		expect(screen.getByRole('link', { name: 'GSW' }).getAttribute('href')).toBe('/team/gsw');
		expect(screen.getByRole('link', { name: 'Warriors' }).getAttribute('href')).toBe('/team/gsw');
		expect(container.querySelectorAll('.record')).toHaveLength(1);
		expect(container.querySelector('.record')?.textContent).toBe('10–7');
	});

	it('shows the guest as plain text and its city without a record on mobile', () => {
		const { container } = show(guestHeader, 'mobile');
		expect(screen.queryByRole('link', { name: 'HCM' })).toBeNull();
		expect(screen.queryByRole('link', { name: 'Mariners' })).toBeNull();
		const metas = [...container.querySelectorAll('.meta')].map((m) => m.textContent);
		expect(metas).toEqual(['Harbor City', 'Golden State · 10–7']);
	});
});

describe('GameHeader with a guest team without a code', () => {
	const guest = { code: null, name: 'Mariners', city: 'Harbor City', record: null, guest: true };
	const header: GameHeaderView = { ...scheduled, away: guest };

	it.each(['desktop', 'mobile'] as const)(
		'shows the initials in the monogram and the name as plain text (%s)',
		(layout: RowLayout) => {
			const { container } = render(GameHeader, {
				props: {
					header,
					allGamesHref: HOME,
					standingsHref: STANDINGS,
					layout,
					teamHref
				}
			});
			expect(screen.getByText('HM').classList.contains('team-monogram')).toBe(true);
			expect(screen.getByRole('heading', { name: 'Mariners' })).toBeTruthy();
			expect(screen.queryByRole('link', { name: 'HM' })).toBeNull();
			expect(screen.queryByRole('link', { name: 'Mariners' })).toBeNull();
			expect(container.querySelectorAll('a[href^="/team/"]').length).toBeGreaterThan(0);
		}
	);
});

describe('GameHeader with the Cup mark', () => {
	it('shows the Cup tag first in the status line, before the date and venue', () => {
		const { container } = show({ ...scheduled, cupTag: 'NBA Cup · Group play' });
		const line = container.querySelector('.status-line');
		expect(line?.firstElementChild?.classList.contains('cup-tag')).toBe(true);
		expect(line?.firstElementChild?.textContent).toBe('NBA Cup · Group play');
		expect(line?.lastElementChild?.textContent).toBe('Wednesday, October 7 · Chase Center');
	});

	it('shows the Cup tag before the live badge on a live game', () => {
		const { container } = show({ ...live, cupTag: 'NBA Cup · Championship' });
		const line = container.querySelector('.status-line');
		expect(line?.firstElementChild?.textContent).toBe('NBA Cup · Championship');
		expect(line?.children.length).toBe(3);
	});

	it('shows no Cup tag on a game that is not a Cup game', () => {
		const { container } = show(scheduled);
		expect(container.querySelector('.cup-tag')).toBeNull();
	});
});

describe('GameHeader with the postseason mark', () => {
	const mark = {
		tag: 'NBA Finals',
		finals: true,
		context: 'Game 5 · NYK leads 3-1',
		stakes: 'Can clinch'
	};

	it('shows the mark first in the status line of a scheduled game, before the status text', () => {
		const { container } = show({ ...scheduled, postseasonMark: mark });
		const line = container.querySelector('.status-line');
		expect(line?.firstElementChild?.classList.contains('postseason-mark')).toBe(true);
		expect(line?.querySelector('.tournament-tag')?.textContent).toBe('NBA Finals');
		expect(line?.querySelector('.stakes-flag')?.textContent).toBe('Can clinch');
		expect(line?.lastElementChild?.textContent).toBe('Wednesday, October 7 · Chase Center');
	});

	it('shows the mark before the live badge on a live game', () => {
		const { container } = show({ ...live, postseasonMark: mark });
		const line = container.querySelector('.status-line');
		expect(line?.firstElementChild?.classList.contains('postseason-mark')).toBe(true);
		expect(line?.children.length).toBe(3);
	});

	it('shows no mark on a regular game', () => {
		const { container } = show(scheduled);
		expect(container.querySelector('.postseason-mark')).toBeNull();
	});

	it('keeps the Cup tag unchanged first for a Cup game', () => {
		const { container } = show({ ...scheduled, cupTag: 'NBA Cup · Group play' });
		expect(
			container.querySelector('.status-line')?.firstElementChild?.classList.contains('cup-tag')
		).toBe(true);
	});
});

describe('GameHeader with the All-Star mark', () => {
	const mark = { tag: 'All-Star', context: 'Semifinals', championship: false };
	const stripes = { code: 'STR', name: 'Team Stripes', city: null, record: null, guest: true };
	const waves = { code: 'WAV', name: 'Team Waves', city: null, record: null, guest: true };

	it('shows the tag first in the status line, then the round', () => {
		const { container } = show({ ...scheduled, allStarMark: mark });
		const line = container.querySelector('.status-line');
		expect(line?.firstElementChild?.classList.contains('allstar-mark')).toBe(true);
		expect(line?.querySelector('.allstar-tag')?.textContent).toBe('All-Star');
		expect(line?.querySelector('.context')?.textContent).toBe('Semifinals');
	});

	it('shows the solid tag for the Championship', () => {
		const championship = { tag: 'All-Star', context: 'Championship', championship: true };
		const { container } = show({ ...scheduled, allStarMark: championship });
		expect(container.querySelector('.allstar-tag')?.classList.contains('solid')).toBe(true);
	});

	it('shows nothing without the mark', () => {
		const { container } = show(scheduled);
		expect(container.querySelector('.allstar-mark')).toBeNull();
	});

	it('shows no city for a guest side without one', () => {
		for (const layout of ['desktop', 'mobile'] as const) {
			const { container, unmount } = show(
				{ ...scheduled, away: stripes, home: waves, allStarMark: mark },
				layout
			);
			expect(container.querySelector('.city')).toBeNull();
			expect(container.querySelector('.meta')?.textContent ?? '').toBe('');
			unmount();
		}
	});
});

describe('GameHeader team logos', () => {
	const logo = {
		light: 'https://example.com/lal-light.svg',
		dark: 'https://example.com/lal-dark.svg'
	};
	const harbor = { code: null, name: 'Mariners', city: 'Harbor City', record: null, guest: true };

	it('draws the logo in the header box on desktop and in the header-mobile box on mobile', () => {
		for (const [layout, size] of [
			['desktop', 'header'],
			['mobile', 'header-mobile']
		] as const) {
			const { container, unmount } = show(
				{ ...final, away: { ...away, logo }, home: { ...harbor } },
				layout
			);
			const boxes = [...container.querySelectorAll('.team-monogram')];
			expect(boxes[0]!.classList.contains(size)).toBe(true);
			expect(boxes[0]!.querySelector('img')?.getAttribute('src')).toBe(
				'https://example.com/lal-dark.svg'
			);
			expect(boxes[1]!.querySelector('img')).toBeNull();
			expect(boxes[1]!.textContent).toBe('HM');
			unmount();
		}
	});
});
