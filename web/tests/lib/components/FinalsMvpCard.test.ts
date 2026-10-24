// web/tests/lib/components/FinalsMvpCard.test.ts
//
// Tests for the FinalsMvpCard component.
//
// Tested:
// - The label, the name, the team row and the four stats with the best game in accent
// - The team logo in the team row, the monogram with no logo; no logo behind the player
// - The team accent on the photo panel, the neutral accent with none
// - Initials without a photo; — for a missing value
// - The mobile layout class, absent on desktop
// - The cutout clips only at the bottom (clip-bottom on the avatar)
//
// What is covered:
// - Each state the card shows, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/FinalsMvpCard.test.ts
//
// SEE: web/src/lib/components/FinalsMvpCard.svelte
import { render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { PlayoffsFeed } from '../../../src/lib/contract/playoffs';
import type { PlayoffsFinalsFeed } from '../../../src/lib/contract/playoffs-finals';
import { toPlayoffsView } from '../../../src/lib/feed/playoffs-props';
import FinalsMvpCard from '../../../src/lib/components/FinalsMvpCard.svelte';

const read = <T>(file: string): T =>
	JSON.parse(readFileSync(join(__dirname, '..', 'feed', 'fixtures', file), 'utf8')) as T;
const mvp = (
	change: (f: PlayoffsFinalsFeed) => void = () => {},
	changeFeed: (f: PlayoffsFeed) => void = () => {}
) => {
	const finals = read<PlayoffsFinalsFeed>('playoffs-finals.json');
	const feed = read<PlayoffsFeed>('playoffs-complete.json');
	change(finals);
	changeFeed(feed);
	return toPlayoffsView(feed, finals).finalsMvp!;
};
const withLogo = (f: PlayoffsFeed) => {
	f.bracket.find((s) => s.conference === null)!.top.team!.logo = {
		light: 'https://cdn.example.com/qxa.svg',
		dark: null
	};
};

afterEach(() => {
	vi.restoreAllMocks();
});

describe('FinalsMvpCard', () => {
	it('shows the name, the label, the photo and the four stats', () => {
		const { container } = render(FinalsMvpCard, { props: { mvp: mvp() } });
		expect(screen.getByText('Kai Lowe', { selector: '.name' })).toBeTruthy();
		expect(screen.getByText('Finals MVP')).toBeTruthy();
		expect(container.querySelector('.team')?.textContent).toContain('Harbor Owls');
		expect(container.querySelector('img')?.getAttribute('src')).toBe(
			'https://cdn.example.com/p/a6.png'
		);
		const stats = [...container.querySelectorAll('.stat')].map((s) => [
			s.querySelector('dt')?.textContent,
			s.querySelector('dd')?.textContent,
			s.classList.contains('accent')
		]);
		expect(stats).toEqual([
			['Points per game', '27.5', false],
			['Best game', '41', true],
			['REB · AST', '8.2 · 6.8', false],
			['Games', '5', false]
		]);
	});

	it('draws the team logo in the team row, and the monogram with no logo', () => {
		const first = render(FinalsMvpCard, { props: { mvp: mvp(undefined, withLogo) } });
		expect(first.container.querySelector('.team img')?.getAttribute('src')).toBe(
			'https://cdn.example.com/qxa.svg'
		);
		first.unmount();
		const { container } = render(FinalsMvpCard, { props: { mvp: mvp() } });
		expect(container.querySelector('.team img')).toBeNull();
		expect(container.querySelector('.team')?.textContent).toContain('QXA');
	});

	it('puts the team color on the photo panel, the neutral accent with none', () => {
		const first = render(FinalsMvpCard, {
			props: { mvp: mvp((f) => (f.finalsMvp!.accent = '#1d4e89')) }
		});
		expect(
			first.container.querySelector<HTMLElement>('.photo')?.style.getPropertyValue('--side-accent')
		).toBe('#1d4e89');
		first.unmount();
		const { container } = render(FinalsMvpCard, { props: { mvp: mvp() } });
		expect(
			container.querySelector<HTMLElement>('.photo')?.style.getPropertyValue('--side-accent')
		).toBe('var(--identity-neutral-accent)');
	});

	it('draws no logo behind the player', () => {
		const { container } = render(FinalsMvpCard, { props: { mvp: mvp(undefined, withLogo) } });
		expect(container.querySelector('.photo .team-monogram')).toBeNull();
		expect(container.querySelector('.photo img[src*="qxa"]')).toBeNull();
	});

	it('shows initials without a photo and — for a missing value', () => {
		render(FinalsMvpCard, {
			props: {
				mvp: mvp((f) => {
					f.finalsMvp!.photoUrl = null;
					f.finalsMvp!.points = null;
					f.finalsMvp!.bestGame = null;
				})
			}
		});
		expect(screen.getByRole('img', { name: 'Kai Lowe' }).textContent).toBe('KL');
		expect(screen.getAllByText('—')).toHaveLength(2);
	});

	it('clips the cutout only at the bottom', () => {
		const { container } = render(FinalsMvpCard, { props: { mvp: mvp() } });
		expect(container.querySelector('.photo .avatar')?.classList.contains('clip-bottom')).toBe(true);
	});

	it('stacks the photo above the info in the mobile layout only', () => {
		const wide = render(FinalsMvpCard, { props: { mvp: mvp() } });
		expect(wide.container.querySelector('.finals-mvp.mobile')).toBeNull();
		const narrow = render(FinalsMvpCard, { props: { mvp: mvp(), layout: 'mobile' } });
		expect(narrow.container.querySelector('.finals-mvp.mobile')).not.toBeNull();
		expect(narrow.container.querySelectorAll('.stat')).toHaveLength(4);
	});
});
