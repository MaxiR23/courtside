// web/tests/lib/components/SectionTabs.test.ts
//
// Tests for the SectionTabs component.
//
// Tested:
// - One link per tab in the given order, pointing at its section
// - The mini score when given, none without it
// - A pre-formatted mini text, alone or with tabs
// - Nothing with no tabs and no mini score
// - A click scrolls smoothly to the section, instantly under reduced motion
// - The nav stays above the page content: sticky with z-index from --tabs-z-index
//
// What is covered:
// - Each state the tabs show, plus the click
// - A stub section element and a mocked scrollIntoView; no layout in jsdom
// - The stacking rule is read from the component source and tokens.css, since
//   jsdom does not apply scoped styles
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/SectionTabs.test.ts
//
// SEE: web/src/lib/components/SectionTabs.svelte
// SEE: web/src/lib/styles/tokens.css
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import SectionTabs from '../../../src/lib/components/SectionTabs.svelte';
import type { SectionTab } from '../../../src/lib/game/types';

const tabs: SectionTab[] = [
	{ id: 'score', label: 'Score' },
	{ id: 'box-score', label: 'Box score' },
	{ id: 'injuries', label: 'Injuries' }
];

const miniScore = { awayCode: 'LAL', away: 63, home: 62, homeCode: 'GSW' };

function stubSection(id: string) {
	const section = document.createElement('section');
	section.id = id;
	const scrollIntoView = vi.fn();
	section.scrollIntoView = scrollIntoView;
	document.body.append(section);
	return scrollIntoView;
}

afterEach(() => {
	vi.unstubAllGlobals();
	document.body.innerHTML = '';
});

describe('SectionTabs', () => {
	it('renders one link per tab in the given order, pointing at its section', () => {
		render(SectionTabs, { props: { tabs, miniScore: null } });
		const links = screen.getAllByRole('link');
		expect(links.map((a) => a.textContent)).toEqual(['Score', 'Box score', 'Injuries']);
		expect(links.map((a) => a.getAttribute('href'))).toEqual(['#score', '#box-score', '#injuries']);
		expect(screen.getByRole('navigation', { name: 'Sections' })).toBeTruthy();
	});

	it('shows the mini score when given', () => {
		const { container } = render(SectionTabs, { props: { tabs, miniScore } });
		expect(container.querySelector('.mini-score')?.textContent?.replace(/\s+/g, ' ').trim()).toBe(
			'LAL 63 – 62 GSW'
		);
	});

	it('shows no mini score without it', () => {
		const { container } = render(SectionTabs, { props: { tabs, miniScore: null } });
		expect(container.querySelector('.mini-score')).toBeNull();
	});

	it('shows a mini text, and renders with only a mini text', () => {
		const { container, unmount } = render(SectionTabs, { props: { tabs, mini: 'OKC 57–25' } });
		expect(container.querySelector('.mini-score')?.textContent).toBe('OKC 57–25');
		unmount();
		const only = render(SectionTabs, { props: { tabs: [], mini: 'OKC 57–25' } });
		expect(only.container.querySelector('nav')).toBeTruthy();
		expect(only.container.querySelector('.mini-score')?.textContent).toBe('OKC 57–25');
	});

	it('renders nothing with no tabs and no mini score', () => {
		const { container } = render(SectionTabs, { props: { tabs: [], miniScore: null } });
		expect(container.querySelector('nav')).toBeNull();
	});

	it('scrolls smoothly to the section on click', async () => {
		vi.stubGlobal('matchMedia', () => ({ matches: false }));
		const scrollIntoView = stubSection('box-score');
		render(SectionTabs, { props: { tabs, miniScore: null } });
		const notPrevented = await fireEvent.click(screen.getByRole('link', { name: 'Box score' }));
		expect(notPrevented).toBe(false);
		expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' });
	});

	it('scrolls instantly under reduced motion', async () => {
		vi.stubGlobal('matchMedia', (query: string) => ({
			matches: query === '(prefers-reduced-motion: reduce)'
		}));
		const scrollIntoView = stubSection('injuries');
		render(SectionTabs, { props: { tabs, miniScore: null } });
		await fireEvent.click(screen.getByRole('link', { name: 'Injuries' }));
		expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'auto', block: 'start' });
	});

	it('does nothing when the section is not on the page yet', async () => {
		render(SectionTabs, { props: { tabs, miniScore: null } });
		await expect(fireEvent.click(screen.getByRole('link', { name: 'Score' }))).resolves.toBe(false);
	});

	it('stacks the nav above the page content through the tabs layer token', () => {
		const source = readFileSync(
			join(import.meta.dirname, '../../../src/lib/components/SectionTabs.svelte'),
			'utf8'
		);
		const block = /\.section-tabs\s*\{([^}]*)\}/.exec(source)?.[1] ?? '';
		expect(block).toMatch(/position:\s*sticky;/);
		expect(block).toMatch(/z-index:\s*var\(--tabs-z-index\);/);

		const tokens = readFileSync(
			join(import.meta.dirname, '../../../src/lib/styles/tokens.css'),
			'utf8'
		);
		const level = Number(/--tabs-z-index:\s*(-?\d+);/.exec(tokens)?.[1]);
		expect(level).toBeGreaterThanOrEqual(1);
	});
});
