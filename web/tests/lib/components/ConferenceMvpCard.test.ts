// web/tests/lib/components/ConferenceMvpCard.test.ts
//
// Tests for the ConferenceMvpCard component.
//
// Tested:
// - The name, the label and the team code
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

const mvps = () =>
	toPlayoffsView(
		JSON.parse(
			readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'playoffs-complete.json'), 'utf8')
		) as PlayoffsFeed,
		null
	).conferenceMvps;

afterEach(() => {
	vi.restoreAllMocks();
});

describe('ConferenceMvpCard', () => {
	it('shows the name, the label, the team code and the photo', () => {
		const { container } = render(ConferenceMvpCard, { props: { mvp: mvps()[0]! } });
		expect(screen.getByText('Kai Lowe')).toBeTruthy();
		expect(screen.getByText('East finals MVP')).toBeTruthy();
		expect(screen.getByText('QXA')).toBeTruthy();
		expect(container.querySelector('img')).not.toBeNull();
	});

	it('shows initials without a photo and the West label', () => {
		render(ConferenceMvpCard, { props: { mvp: mvps()[1]! } });
		expect(screen.getByRole('img', { name: 'Moe Nash' }).textContent).toBe('MN');
		expect(screen.getByText('West finals MVP')).toBeTruthy();
	});
});
