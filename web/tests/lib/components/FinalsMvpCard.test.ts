// web/tests/lib/components/FinalsMvpCard.test.ts
//
// Tests for the FinalsMvpCard component.
//
// Tested:
// - The name, the label and the four stats with the best game in accent
// - Initials without a photo; — for a missing value
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
const mvp = (change: (f: PlayoffsFinalsFeed) => void = () => {}) => {
	const finals = read<PlayoffsFinalsFeed>('playoffs-finals.json');
	change(finals);
	return toPlayoffsView(read<PlayoffsFeed>('playoffs-complete.json'), finals).finalsMvp!;
};

afterEach(() => {
	vi.restoreAllMocks();
});

describe('FinalsMvpCard', () => {
	it('shows the name, the label, the photo and the four stats', () => {
		const { container } = render(FinalsMvpCard, { props: { mvp: mvp() } });
		expect(screen.getByText('Kai Lowe', { selector: '.name' })).toBeTruthy();
		expect(screen.getByText('Finals MVP')).toBeTruthy();
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
});
