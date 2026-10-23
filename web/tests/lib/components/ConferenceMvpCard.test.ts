// web/tests/lib/components/ConferenceMvpCard.test.ts
//
// Tests for the ConferenceMvpCard component.
//
// Tested:
// - The label, the name, the team name and the logo in place of the code; the monogram with no logo
// - The team accent on the photo cell
// - Initials without a photo
//
// What is covered:
// - Each state the card shows, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/ConferenceMvpCard.test.ts
//
// SEE: web/src/lib/components/ConferenceMvpCard.svelte
import { render, screen } from '@testing-library/svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { PlayoffsFeed } from '../../../src/lib/contract/playoffs';
import { toPlayoffsView } from '../../../src/lib/feed/playoffs-props';
import ConferenceMvpCard from '../../../src/lib/components/ConferenceMvpCard.svelte';

const mvps = (change: (f: PlayoffsFeed) => void = () => {}) => {
	const feed = JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'playoffs-complete.json'), 'utf8')
	) as PlayoffsFeed;
	change(feed);
	return toPlayoffsView(feed, null).conferenceMvps;
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

describe('ConferenceMvpCard', () => {
	it('shows the label, the name, the team name and the logo in place of the code', () => {
		const { container } = render(ConferenceMvpCard, { props: { mvp: mvps(withLogo)[0]! } });
		expect(screen.getByText('Kai Lowe')).toBeTruthy();
		expect(screen.getByText('East Finals MVP')).toBeTruthy();
		expect(screen.getByText('Harbor Owls')).toBeTruthy();
		expect(container.querySelector('.logo img')?.getAttribute('src')).toBe(
			'https://cdn.example.com/qxa.svg'
		);
		expect(screen.queryByText('QXA')).toBeNull();
		expect(container.querySelector('.photo img')).not.toBeNull();
	});

	it('shows the monogram code when the team has no logo', () => {
		const { container } = render(ConferenceMvpCard, { props: { mvp: mvps()[0]! } });
		expect(container.querySelector('.logo')?.textContent?.trim()).toBe('QXA');
	});

	it('puts the team color on the photo cell', () => {
		const first = render(ConferenceMvpCard, {
			props: {
				mvp: mvps((f) => {
					f.awards!.find((a) => a.code === 'east_finals_mvp')!.winners[0]!.accent = '#5a2d82';
				})[0]!
			}
		});
		expect(
			first.container.querySelector<HTMLElement>('.photo')?.style.getPropertyValue('--side-accent')
		).toBe('#5a2d82');
		first.unmount();
		const { container } = render(ConferenceMvpCard, { props: { mvp: mvps()[0]! } });
		expect(
			container.querySelector<HTMLElement>('.photo')?.style.getPropertyValue('--side-accent')
		).toBe('var(--identity-neutral-accent)');
	});

	it('shows initials without a photo and the West label', () => {
		render(ConferenceMvpCard, { props: { mvp: mvps()[1]! } });
		expect(screen.getByRole('img', { name: 'Moe Nash' }).textContent).toBe('MN');
		expect(screen.getByText('West Finals MVP')).toBeTruthy();
	});
});
