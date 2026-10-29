// web/tests/lib/components/SectionHead.test.ts
//
// Tests for the SectionHead component.
//
// Tested:
// - Shows the title as an h2
// - Shows the meta only when given
// - Adds the emphasis class to the meta on request
// - Draws the detail size by default and the home size on request
// - Puts the id on the h2
// - Draws a kicker through Kicker above the title, and no wrapper without one
// - Passes the title size, kicker size and kicker gap as custom properties
// - Reads the size tokens in its styles
//
// What is covered:
// - The header shared by the sections of the game and team pages, the home
//   sections, the Cup tree, the playoffs bracket, All-Star games and the
//   power ranking
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/SectionHead.test.ts
//
// SEE: web/src/lib/components/SectionHead.svelte
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import SectionHead from '../../../src/lib/components/SectionHead.svelte';

describe('SectionHead', () => {
	it('shows the title as an h2 and no meta without one', () => {
		const { container } = render(SectionHead, { props: { title: 'Roster' } });
		expect(screen.getByRole('heading', { level: 2, name: 'Roster' })).toBeTruthy();
		expect(container.querySelector('.meta')).toBeNull();
	});

	it('shows the meta when given', () => {
		const { container } = render(SectionHead, { props: { title: 'Injuries', meta: 'Report' } });
		const meta = container.querySelector('.meta');
		expect(meta?.textContent).toBe('Report');
		expect(meta?.classList.contains('emphasis')).toBe(false);
	});

	it('adds the emphasis class on request', () => {
		const { container } = render(SectionHead, {
			props: { title: 'Win probability', meta: 'GSW 68%', emphasis: true }
		});
		expect(container.querySelector('.meta')?.classList.contains('emphasis')).toBe(true);
	});

	it('draws the detail size by default and the home size on request', () => {
		const detail = render(SectionHead, { props: { title: 'Roster' } });
		const h2 = detail.container.querySelector('h2');
		expect(h2?.classList.contains('home')).toBe(false);
		expect(h2?.classList.contains('mvp')).toBe(false);
		detail.unmount();
		const home = render(SectionHead, { props: { title: 'Roster', size: 'home' } });
		expect(home.container.querySelector('h2')?.classList.contains('home')).toBe(true);
	});

	it('puts the id on the h2', () => {
		render(SectionHead, { props: { title: 'Roster', id: 'roster-title' } });
		expect(screen.getByRole('heading', { level: 2 }).id).toBe('roster-title');
	});

	it('draws a kicker through Kicker above the title', () => {
		const { container } = render(SectionHead, {
			props: { title: 'Schedule', kicker: 'Today', meta: 'Note' }
		});
		const titled = container.querySelector('.titled');
		expect(titled?.children[0]?.classList.contains('kicker')).toBe(true);
		expect(titled?.children[0]?.textContent).toBe('Today');
		expect(titled?.children[1]?.classList.contains('section-head')).toBe(true);
		expect(titled?.querySelector('.section-head .meta')?.textContent).toBe('Note');
	});

	it('draws no kicker wrapper without a kicker', () => {
		const { container } = render(SectionHead, { props: { title: 'Roster' } });
		expect(container.querySelector('.titled')).toBeNull();
		expect(container.querySelector('.kicker')).toBeNull();
		expect(container.firstElementChild?.classList.contains('section-head')).toBe(true);
	});

	it('passes the title size, kicker size and kicker gap as custom properties', () => {
		const { container } = render(SectionHead, {
			props: {
				title: 'Tree',
				kicker: 'Cup',
				titleSize: 'var(--cup-tree-title-size)',
				kickerSize: 'var(--cup-tree-kicker-size)',
				kickerGap: 'var(--cup-tree-gap)'
			}
		});
		const h2 = container.querySelector('h2') as HTMLElement;
		expect(h2.style.getPropertyValue('--section-head-size')).toBe('var(--cup-tree-title-size)');
		const text = container.querySelector('.kicker-text') as HTMLElement;
		expect(text.style.getPropertyValue('--section-head-kicker-size')).toBe(
			'var(--cup-tree-kicker-size)'
		);
		const titled = container.querySelector('.titled') as HTMLElement;
		expect(titled.style.getPropertyValue('--section-head-kicker-gap')).toBe('var(--cup-tree-gap)');
	});

	it('sets no style attribute without those props', () => {
		const { container } = render(SectionHead, { props: { title: 'Roster', kicker: 'Cup' } });
		expect(container.querySelector('h2')?.hasAttribute('style')).toBe(false);
		expect(container.querySelector('.kicker-text')?.hasAttribute('style')).toBe(false);
		expect(container.querySelector('.titled')?.hasAttribute('style')).toBe(false);
	});

	it('reads the size tokens in its styles', () => {
		const source = readFileSync(
			join(import.meta.dirname, '../../../src/lib/components/SectionHead.svelte'),
			'utf8'
		);
		const style = (source.match(/<style[^>]*>([\s\S]*?)<\/style>/)?.[1] ?? '').replace(/\s+/g, ' ');
		expect(style).toContain(
			'.section-head h2.home { font-size: var(--section-head-size, var(--section-h2-size)); line-height: var(--section-h2-line-height);'
		);
		expect(style).toContain('font-size: var(--section-head-size, var(--detail-section-h2-size));');
	});
});
