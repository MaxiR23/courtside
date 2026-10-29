// web/tests/lib/components/PowerRanking.test.ts
//
// Tests for the PowerRanking component.
//
// Tested:
// - Desktop: the header (kicker, title, note) and the column headers
// - Desktop: 10 rows by default; the toggle shows all 30 and back, and the 11th team leaves the DOM
// - Desktop: a tied rank reads T3; muted cells follow the feed's flags; the bar width input is titleShare
// - Desktop: a null name shows the code and no city; a logo reaches the tile
// - Mobile: a row shows rank, name, record and title; it opens to the details and closes again
// - Mobile: one open row at a time; the top 10 and the toggle; collapsing closes an open row
// - Spanish copy
// - The kicker is drawn inside SectionHead, before the title and the note
//
// What is covered:
// - Drawn from props with no fetch; the view comes from the recorded feed. jsdom does not lay
//   out, so the checks are on DOM, attributes, classes and the inline custom property.
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PowerRanking.test.ts
//
// SEE: web/src/lib/components/PowerRanking.svelte
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import PowerRanking from '../../../src/lib/components/PowerRanking.svelte';
import type { PowerRankingFeed } from '../../../src/lib/contract/power-ranking';
import { toPowerRankingView } from '../../../src/lib/feed/power-ranking-props';
import type { PowerRankingView } from '../../../src/lib/standings/types';
import { preferLanguages } from '../../prefer-languages';

const feed = (): PowerRankingFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'power-ranking.json'), 'utf8')
	) as PowerRankingFeed;

const view = (): PowerRankingView => toPowerRankingView(feed()) as PowerRankingView;

const show = (layout: 'desktop' | 'mobile') =>
	render(PowerRanking, { props: { view: view(), layout } });

const bodyRows = (container: HTMLElement) => container.querySelectorAll('.body');
const summaries = (container: HTMLElement) => container.querySelectorAll('button.summary');
const expandedSummaries = (container: HTMLElement) =>
	container.querySelectorAll('button.summary[aria-expanded="true"]');

// The 11th team: its name appears only once the list is expanded.
const ELEVENTH = 'Suns';

afterEach(() => {
	vi.restoreAllMocks();
});

describe('PowerRanking desktop', () => {
	it('draws the kicker inside SectionHead, before the title and the note', () => {
		const { container } = show('desktop');
		const titled = container.querySelector('.titled');
		expect(titled?.children[0]?.textContent).toBe('Team ratings');
		expect(titled?.querySelector('.section-head h2')?.textContent?.trim()).toBe('Power ranking');
		expect(titled?.querySelector('.section-head .meta')?.textContent).toBe(
			'Regular season · Updated daily'
		);
	});

	it('shows the kicker, the title, the note and the column headers', () => {
		show('desktop');
		expect(screen.getByText('Team ratings')).toBeTruthy();
		expect(screen.getByRole('heading', { level: 2, name: 'Power ranking' })).toBeTruthy();
		expect(screen.getByText('Regular season · Updated daily')).toBeTruthy();
		expect(screen.getAllByRole('columnheader').map((h) => h.textContent)).toEqual([
			'#',
			'Team',
			'Record',
			'Rating',
			'Off',
			'Def',
			'Proj.',
			'Playoffs',
			'Title'
		]);
	});

	it('renders 10 rows by default and the 11th team is not in the document', () => {
		const { container } = show('desktop');
		expect(bodyRows(container)).toHaveLength(10);
		expect(screen.queryByText(ELEVENTH)).toBeNull();
	});

	it('shows all 30 teams from the toggle and goes back to 10', async () => {
		const { container } = show('desktop');
		const toggle = screen.getByRole('button', { name: 'Show all 30 teams' });
		expect(toggle.getAttribute('aria-expanded')).toBe('false');
		await fireEvent.click(toggle);
		expect(bodyRows(container)).toHaveLength(30);
		expect(screen.getByText(ELEVENTH)).toBeTruthy();
		const back = screen.getByRole('button', { name: 'Show top 10' });
		expect(back.getAttribute('aria-expanded')).toBe('true');
		await fireEvent.click(back);
		expect(bodyRows(container)).toHaveLength(10);
		expect(screen.queryByText(ELEVENTH)).toBeNull();
	});

	it('reads a tied rank as T3 on both tied rows', () => {
		const { container } = show('desktop');
		const ranks = [...container.querySelectorAll('.body .rank')].map((c) => c.textContent);
		expect(ranks.slice(0, 5)).toEqual(['1', '2', 'T3', 'T3', '5']);
	});

	it('mutes the negative rating and the low playoffs cell, and only those', async () => {
		const { container } = show('desktop');
		await fireEvent.click(screen.getByRole('button', { name: 'Show all 30 teams' }));
		const rows = [...bodyRows(container)];
		expect(rows[0].querySelector('.rating')?.classList.contains('muted')).toBe(false);
		expect(rows[0].querySelector('.playoffs')?.classList.contains('muted')).toBe(false);
		expect(rows[27].querySelector('.rating')?.classList.contains('muted')).toBe(true);
		expect(rows[27].querySelector('.playoffs')?.classList.contains('muted')).toBe(false);
		expect(rows[28].querySelector('.playoffs')?.classList.contains('muted')).toBe(true);
	});

	it('sets each bar from the feed titleShare', async () => {
		const { container } = show('desktop');
		await fireEvent.click(screen.getByRole('button', { name: 'Show all 30 teams' }));
		const shares = [...container.querySelectorAll('.bar')].map((b) =>
			(b as HTMLElement).style.getPropertyValue('--share')
		);
		expect(shares[0]).toBe('1');
		expect(shares[3]).toBe('0.42');
		expect(shares[28]).toBe('0');
	});

	it('shows the code and no city for a team with a null name, and the logo for one that has it', async () => {
		const { container } = show('desktop');
		await fireEvent.click(screen.getByRole('button', { name: 'Show all 30 teams' }));
		const last = bodyRows(container)[29];
		expect(last.textContent).toContain('WAS');
		expect(last.querySelector('.city')).toBeNull();
		expect(last.querySelector('img')).toBeNull();
		const first = bodyRows(container)[0];
		expect(first.querySelector('img')?.getAttribute('src')).toBe(
			'https://example.com/logos/okc.png'
		);
		expect(first.querySelector('.city')?.textContent).toBe('Oklahoma City');
		const cells = [...first.querySelectorAll('.cell')].map((c) => c.textContent?.trim());
		expect(cells.slice(4, 6)).toEqual(['+8.0', '−7.0']);
	});
});

describe('PowerRanking mobile', () => {
	it('shows rank, name, record and title with no details, and opens a row on click', async () => {
		const { container } = show('mobile');
		const first = summaries(container)[0] as HTMLElement;
		expect(first.textContent).toContain('1');
		expect(first.textContent).toContain('Thunder');
		expect(first.textContent).toContain('4-0');
		expect(first.textContent).toContain('31.0%');
		expect(container.querySelector('.details')).toBeNull();
		await fireEvent.click(first);
		expect(first.getAttribute('aria-expanded')).toBe('true');
		expect(first.closest('li')?.classList.contains('open')).toBe(true);
		const details = screen.getByLabelText('Details of Thunder');
		expect(details.textContent).toContain('Rating');
		expect(details.textContent).toContain('+11.2');
		expect(details.textContent).toContain('Proj.');
		expect(details.textContent).toContain('Playoffs');
		expect(details.textContent).toContain('>99.9%');
		expect(details.textContent).toContain('Off / Def');
		expect(details.textContent).toContain('+8.0 / −7.0');
		expect(first.getAttribute('aria-controls')).toBe(details.id);
	});

	it('closes the first row when a second opens, and closes a row on a second click', async () => {
		const { container } = show('mobile');
		const [one, two] = [summaries(container)[0], summaries(container)[1]];
		await fireEvent.click(one);
		await fireEvent.click(two);
		expect(expandedSummaries(container)).toHaveLength(1);
		expect(two.getAttribute('aria-expanded')).toBe('true');
		expect(container.querySelectorAll('.details')).toHaveLength(1);
		await fireEvent.click(two);
		expect(expandedSummaries(container)).toHaveLength(0);
		expect(container.querySelector('.details')).toBeNull();
	});

	it('shows the top 10 and the toggle, and collapsing closes an open row from 11 to 30', async () => {
		const { container } = show('mobile');
		expect(summaries(container)).toHaveLength(10);
		expect(screen.queryByText(ELEVENTH)).toBeNull();
		await fireEvent.click(screen.getByRole('button', { name: 'Show all 30 teams' }));
		expect(summaries(container)).toHaveLength(30);
		await fireEvent.click(summaries(container)[10]);
		expect(container.querySelectorAll('.details')).toHaveLength(1);
		await fireEvent.click(screen.getByRole('button', { name: 'Show top 10' }));
		expect(summaries(container)).toHaveLength(10);
		expect(container.querySelector('.details')).toBeNull();
		await fireEvent.click(screen.getByRole('button', { name: 'Show all 30 teams' }));
		expect(expandedSummaries(container)).toHaveLength(0);
	});
});

describe('PowerRanking Spanish', () => {
	it('shows the kicker, the title, the note and the toggle in Spanish', () => {
		preferLanguages(['es']);
		show('desktop');
		expect(screen.getByText('Valoración de equipos')).toBeTruthy();
		expect(screen.getByRole('heading', { level: 2, name: 'Ranking de poder' })).toBeTruthy();
		expect(screen.getByText('Temporada regular · Actualizado a diario')).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Ver los 30 equipos' })).toBeTruthy();
	});
});
