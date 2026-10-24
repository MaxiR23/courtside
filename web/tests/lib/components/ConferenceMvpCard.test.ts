// web/tests/lib/components/ConferenceMvpCard.test.ts
//
// Tests for the ConferenceMvpCard component.
//
// Tested:
// - The label, the name, the team name and the logo in place of the code; the monogram with no logo
// - The team accent on the photo cell
// - Initials without a photo
// - The photo cell keeps the overflow clip, has no height floor, and the cutout takes no height from it
//   (the two-column stack is driven by the Finals card, not by the photo)
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

const srcDir = join(__dirname, '..', '..', '..', 'src/lib');

type Declaration = { property: string; value: string };
type Rule = { selectors: string[]; declarations: Declaration[] };

function styleOf(source: string): string {
	const match = source.match(/<style[^>]*>([\s\S]*?)<\/style>/);
	return (match?.[1] ?? '').replace(/\/\*[\s\S]*?\*\//g, '');
}

function rulesOf(style: string): Rule[] {
	const rules: Rule[] = [];
	for (const match of style.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
		const declarations = (match[2] ?? '')
			.split(';')
			.map((part) => part.trim())
			.filter((part) => part.includes(':'))
			.map((part) => {
				const index = part.indexOf(':');
				return {
					property: part.slice(0, index).trim().toLowerCase(),
					value: part.slice(index + 1).trim()
				};
			});
		const selectors = (match[1] ?? '').split(',').map((selector) => selector.trim());
		rules.push({ selectors, declarations });
	}
	return rules;
}

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

describe('ConferenceMvpCard photo cell', () => {
	const rules = rulesOf(
		styleOf(readFileSync(join(srcDir, 'components/ConferenceMvpCard.svelte'), 'utf8'))
	);
	const photo = rules
		.filter((rule) => rule.selectors.includes('.photo'))
		.flatMap((rule) => rule.declarations);

	it('keeps the overflow clip and has no height floor', () => {
		expect(rules.length).toBeGreaterThan(0);
		expect(photo.length).toBeGreaterThan(0);
		expect(photo).toContainEqual({ property: 'overflow', value: 'hidden' });
		expect(photo.some((d) => d.property === 'min-height')).toBe(false);
	});

	it('passes the bottom-only clip to the avatar', () => {
		const { container } = render(ConferenceMvpCard, { props: { mvp: mvps()[0]! } });
		expect(container.querySelector('.photo .avatar')?.classList.contains('clip-bottom')).toBe(true);
	});

	it('takes no height from the cutout: the avatar is out of flow', () => {
		const { container } = render(ConferenceMvpCard, { props: { mvp: mvps()[0]! } });
		expect(container.querySelector('.photo .avatar')?.classList.contains('clip-bottom')).toBe(true);
		const avatarRules = rulesOf(
			styleOf(readFileSync(join(srcDir, 'components/PlayerAvatar.svelte'), 'utf8'))
		);
		const clip = avatarRules
			.filter((rule) => rule.selectors.includes('.avatar.clip-bottom'))
			.flatMap((rule) => rule.declarations);
		expect(avatarRules.length).toBeGreaterThan(0);
		expect(clip.length).toBeGreaterThan(0);
		expect(clip).toContainEqual({ property: 'position', value: 'absolute' });
		expect(clip).toContainEqual({ property: 'inset', value: '0' });
		expect(photo).toContainEqual({ property: 'position', value: 'relative' });
	});
});
