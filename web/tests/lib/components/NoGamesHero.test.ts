// web/tests/lib/components/NoGamesHero.test.ts
//
// Tests for the NoGamesHero component.
//
// Tested:
// - Each of the four scenarios, with and without Coming up, on desktop and mobile, in English and Spanish:
//   the title as the h1, the scenario chip, the paragraph and the date; the Coming up card is inside
//   only on desktop with Coming up, and the with-card class is present only then
// - The next tip-off is absent when null; the network shows only when set
// - A view without the home feed shows the date and the title only
// - The mobile class on a mobile layout
//
// What is covered:
// - Every state the component shows; jsdom does not lay out, so the full width is asserted by class
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/NoGamesHero.test.ts
//
// SEE: web/src/lib/components/NoGamesHero.svelte
import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import NoGamesHero from '../../../src/lib/components/NoGamesHero.svelte';
import type { NoGamesView } from '../../../src/lib/home/types';
import { preferLanguages } from '../../prefer-languages';

const copy = {
	en: {
		title: 'No games today',
		scenarios: [
			['Off day', 'A rest day across the league. The schedule below shows the next games.'],
			['All-Star break', 'The regular season pauses for the All-Star break.'],
			['Finals preview', 'The conference finals are over. The Finals are next.'],
			['Offseason', 'The season is over. The next one starts with the preseason and Opening Night.']
		]
	},
	es: {
		title: 'Hoy no hay partidos',
		scenarios: [
			['Día sin partidos', 'Jornada de descanso en toda la liga.'],
			['Pausa del All-Star', 'La temporada regular se detiene por la pausa del All-Star.'],
			['Previa de las Finales', 'Las finales de conferencia terminaron.'],
			['Fuera de temporada', 'La temporada terminó.']
		]
	}
} as const;

const comingUp = [
	{
		key: 'allStar',
		date: 'Feb 14',
		title: 'All-Star',
		sub: 'The midseason showcase',
		status: 'upcoming' as const,
		statusLabel: 'Upcoming',
		target: 'allStar' as const
	}
];

const cases = (['en', 'es'] as const).flatMap((lang) =>
	[0, 1, 2, 3].flatMap((scenario) =>
		[true, false].flatMap((withComingUp) =>
			(['desktop', 'mobile'] as const).map(
				(layout) => [lang, scenario, withComingUp, layout] as const
			)
		)
	)
);

afterEach(() => {
	vi.restoreAllMocks();
});

describe('NoGamesHero', () => {
	it.each(cases)('in %s, scenario %i, Coming up %s, %s', (lang, scenario, withComingUp, layout) => {
		if (lang === 'es') preferLanguages(['es']);
		const [tag, paragraph] = copy[lang].scenarios[scenario];
		const view: NoGamesView = {
			date: 'Sunday, October 4',
			tag,
			paragraph,
			nextTipOff: null,
			broadcast: null,
			comingUp: withComingUp ? comingUp : null
		};
		const { container } = render(NoGamesHero, { props: { view, layout } });
		expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(copy[lang].title);
		expect(screen.getByText(tag)).toBeTruthy();
		expect(screen.getByText(paragraph)).toBeTruthy();
		expect(screen.getByText('Sunday, October 4')).toBeTruthy();
		const card = withComingUp && layout === 'desktop';
		expect(container.querySelector('.coming-up') !== null).toBe(card);
		expect(container.querySelector('.columns')?.classList.contains('with-card')).toBe(card);
		expect(container.querySelector('.columns')?.classList.contains('mobile')).toBe(
			layout === 'mobile'
		);
	});

	it('shows the next tip-off and the network only when it has one', () => {
		const base: NoGamesView = {
			date: 'Sunday, October 4',
			tag: 'Off day',
			paragraph: 'p',
			nextTipOff: 'Next tip-off: Tue, Oct 6 · 7:00 PM ET',
			broadcast: 'Courtside TV',
			comingUp: null
		};
		const first = render(NoGamesHero, { props: { view: base, layout: 'desktop' } });
		expect(first.container.querySelector('.next')?.textContent?.replace(/\s+/g, ' ').trim()).toBe(
			'Next tip-off: Tue, Oct 6 · 7:00 PM ET · Courtside TV'
		);
		first.unmount();
		const second = render(NoGamesHero, {
			props: { view: { ...base, broadcast: null }, layout: 'desktop' }
		});
		expect(second.container.querySelector('.next')?.textContent?.trim()).toBe(
			'Next tip-off: Tue, Oct 6 · 7:00 PM ET'
		);
		second.unmount();
		const third = render(NoGamesHero, {
			props: { view: { ...base, nextTipOff: null }, layout: 'desktop' }
		});
		expect(third.container.querySelector('.next')).toBeNull();
	});

	it('shows the date and the title only without the home feed', () => {
		const view: NoGamesView = {
			date: 'Sunday, October 4',
			tag: null,
			paragraph: null,
			nextTipOff: null,
			broadcast: null,
			comingUp: null
		};
		const { container } = render(NoGamesHero, { props: { view, layout: 'desktop' } });
		expect(screen.getByText('Sunday, October 4')).toBeTruthy();
		expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('No games today');
		expect(container.querySelector('.status-tag')).toBeNull();
		expect(container.querySelector('.paragraph')).toBeNull();
		expect(container.querySelector('.next')).toBeNull();
		expect(container.querySelector('.coming-up')).toBeNull();
		expect(container.querySelector('.with-card')).toBeNull();
	});
});
