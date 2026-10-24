// web/tests/lib/components/ConferenceMvpCard.test.ts
//
// Tests for the ConferenceMvpCard component.
//
// Tested:
// - The label, the name, the team name and the logo in place of the code; the monogram with no logo
// - The team accent on the photo cell
// - Initials without a photo
// - The photo cell keeps a min-height floor from a token, and the overflow clip; the floor equals the two-column cell height and never grows the two-column layout
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

const tokenPx = (name: string): number => {
	const css = readFileSync(join(srcDir, 'styles/tokens.css'), 'utf8');
	const match = css.match(new RegExp(`${name}:\\s*([0-9.]+)px;`));
	expect(match, name).not.toBeNull();
	return Number(match![1]);
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

describe('ConferenceMvpCard photo cell', () => {
	const rules = rulesOf(
		styleOf(readFileSync(join(srcDir, 'components/ConferenceMvpCard.svelte'), 'utf8'))
	);
	const photo = rules
		.filter((rule) => rule.selectors.includes('.photo'))
		.flatMap((rule) => rule.declarations);

	it('floors the cell height with a token and keeps the overflow clip', () => {
		expect(rules.length).toBeGreaterThan(0);
		expect(photo.length).toBeGreaterThan(0);
		expect(photo).toContainEqual({
			property: 'min-height',
			value: 'var(--playoffs-conf-photo-min-height)'
		});
		expect(photo).toContainEqual({ property: 'overflow', value: 'hidden' });
	});

	it('never makes the two-column layout taller than the Finals MVP card', () => {
		const hairline = tokenPx('--hairline');
		const floor = tokenPx('--playoffs-conf-photo-min-height');
		expect(2 * (floor + 2 * hairline) + tokenPx('--playoffs-conf-gap')).toBeLessThanOrEqual(
			tokenPx('--playoffs-mvp-photo-min-height') + 2 * hairline
		);
	});

	it('equals the two-column cell height, so one column matches two columns', () => {
		const hairline = tokenPx('--hairline');
		expect(tokenPx('--playoffs-conf-photo-min-height')).toBe(
			(tokenPx('--playoffs-mvp-photo-min-height') + 2 * hairline - tokenPx('--playoffs-conf-gap')) /
				2 -
				2 * hairline
		);
	});
});
