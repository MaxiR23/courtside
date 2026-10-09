// web/tests/lib/components/StandingsHeader.test.ts
//
// Tests for the StandingsHeader component.
//
// Tested:
// - The season tag, the state line, the h1, the note and the toggle with Conference pressed
// - Division click calls onGroupingChange with division
// - Only the nav and the h1 without a header
// - Bones and aria-busy while loading; the shimmer, and not with reduced motion
// - Spanish copy
//
// What is covered:
// - Each state the header shows, drawn from props with no fetch
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/StandingsHeader.test.ts
//
// SEE: web/src/lib/components/StandingsHeader.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import StandingsHeader from '../../../src/lib/components/StandingsHeader.svelte';
import { preferLanguages } from '../../prefer-languages';

const HOME = '/' as ResolvedPathname;
const STANDINGS = '/standings' as ResolvedPathname;
const header = { season: '2025-26', stateLine: 'Regular season · 1180 games played' };

const props = (extra: Record<string, unknown> = {}) => ({
	header,
	allGamesHref: HOME,
	standingsHref: STANDINGS,
	layout: 'desktop' as const,
	grouping: 'conference' as const,
	onGroupingChange: () => {},
	...extra
});

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	Reflect.deleteProperty(HTMLElement.prototype, 'animate');
});

describe('StandingsHeader', () => {
	it('renders the season tag, the state line, the h1, the note and the toggle with Conference pressed', () => {
		render(StandingsHeader, { props: props() });
		expect(screen.getByText('2025-26')).toBeTruthy();
		expect(screen.getByText('Regular season · 1180 games played')).toBeTruthy();
		expect(screen.getByRole('heading', { level: 1, name: 'Standings' })).toBeTruthy();
		expect(screen.getByText('Seeds follow the official seeding.')).toBeTruthy();
		const group = screen.getByRole('group', { name: 'Standings view' });
		expect(group).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Conference' }).getAttribute('aria-pressed')).toBe(
			'true'
		);
		expect(screen.getByRole('button', { name: 'Division' }).getAttribute('aria-pressed')).toBe(
			'false'
		);
	});

	it('calls onGroupingChange with division when Division is clicked', async () => {
		const onGroupingChange = vi.fn();
		render(StandingsHeader, { props: props({ onGroupingChange }) });
		await fireEvent.click(screen.getByRole('button', { name: 'Division' }));
		expect(onGroupingChange).toHaveBeenCalledWith('division');
	});

	it('renders only the nav and the h1 without a header', () => {
		const { container } = render(StandingsHeader, { props: props({ header: null }) });
		expect(screen.getByRole('heading', { level: 1, name: 'Standings' })).toBeTruthy();
		expect(screen.getByRole('link', { name: 'All games' })).toBeTruthy();
		expect(screen.queryByRole('group')).toBeNull();
		expect(container.querySelector('.bones')).toBeNull();
	});

	it('shows bones and aria-busy while loading', () => {
		const { container } = render(StandingsHeader, {
			props: props({ header: null, loading: true })
		});
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('.bones')?.getAttribute('aria-hidden')).toBe('true');
		expect(screen.queryByRole('group')).toBeNull();
	});

	it('shimmers, and not with reduced motion', () => {
		const animate = vi.fn<(keyframes: unknown, options: unknown) => { cancel: () => void }>(() => ({
			cancel: vi.fn()
		}));
		Object.assign(HTMLElement.prototype, { animate });
		const looped = () =>
			animate.mock.calls.some(
				(call) => (call[1] as { iterations?: number } | undefined)?.iterations === Infinity
			);
		vi.stubGlobal('matchMedia', () => ({ matches: false }));
		const first = render(StandingsHeader, { props: props({ header: null, loading: true }) });
		expect(looped()).toBe(true);
		first.unmount();
		animate.mockClear();
		vi.stubGlobal('matchMedia', (query: string) => ({
			matches: query === '(prefers-reduced-motion: reduce)'
		}));
		render(StandingsHeader, { props: props({ header: null, loading: true }) });
		expect(animate).not.toHaveBeenCalled();
	});

	it('renders in Spanish', () => {
		preferLanguages(['es-ES']);
		render(StandingsHeader, { props: props() });
		expect(screen.getByRole('heading', { level: 1, name: 'Clasificación' })).toBeTruthy();
		expect(screen.getByText('Los puestos siguen la clasificación oficial.')).toBeTruthy();
		expect(screen.getByRole('group', { name: 'Vista de la clasificación' })).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Conferencia' })).toBeTruthy();
		expect(screen.getByRole('button', { name: 'División' })).toBeTruthy();
	});
});
