// web/tests/lib/components/TeamMonogram.test.ts
//
// Tests for the TeamMonogram component.
//
// Tested:
// - Shows the three-letter code
// - Uses the large or small box by size
// - Uses the header and header-mobile boxes on the game detail page
// - Uses the injury box on the injuries section
// - Uses the team box on the team page
// - Uses the standings box on the standings page
// - Uses the search box in the search overlay
// - Uses the cup-draw box in the Cup draw list and the cup-champion box in the Cup header
// - Uses the cup-node box in a bracket node
// - Uses the playoffs-mvp-team box in the Finals MVP team row and the playoffs-mvp-logo box in a conference MVP card
// - Uses the allstar-league box for a player's league team
// - Uses the names box in the franchise names timeline
// - Uses the fill box of its parent and the inline box before a team's text
// - A logo is hidden from assistive technology without logoAlt and has its alt text with one
// - A linked hidden logo is named by its code through aria-label, a linked logo with logoAlt by that text
// - A monogram has neither aria-label nor aria-hidden, except an inline one, which is hidden
// - Draws a logo image in the box in place of the code, and calls back on its error
// - Links the code to the href when one is given, and renders a span without one
//
// What is covered:
// - Both sizes
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/TeamMonogram.test.ts
//
// SEE: web/src/lib/components/TeamMonogram.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

import TeamMonogram from '../../../src/lib/components/TeamMonogram.svelte';

describe('TeamMonogram', () => {
	it("shows the team's three-letter code", () => {
		render(TeamMonogram, { props: { code: 'GSW', size: 'large' } });
		expect(screen.getByText('GSW')).toBeTruthy();
	});

	it('uses the large box for the desktop row', () => {
		render(TeamMonogram, { props: { code: 'GSW', size: 'large' } });
		const el = screen.getByText('GSW');
		expect(el.classList.contains('large')).toBe(true);
		expect(el.classList.contains('small')).toBe(false);
	});

	it('uses the small box for the mobile row', () => {
		render(TeamMonogram, { props: { code: 'GSW', size: 'small' } });
		const el = screen.getByText('GSW');
		expect(el.classList.contains('small')).toBe(true);
		expect(el.classList.contains('large')).toBe(false);
	});

	it('renders the header and header-mobile sizes', () => {
		const { unmount } = render(TeamMonogram, { props: { code: 'GSW', size: 'header' } });
		expect(screen.getByText('GSW').classList.contains('header')).toBe(true);
		unmount();
		render(TeamMonogram, { props: { code: 'LAL', size: 'header-mobile' } });
		expect(screen.getByText('LAL').classList.contains('header-mobile')).toBe(true);
	});

	it('renders the team size', () => {
		render(TeamMonogram, { props: { code: 'OKC', size: 'team' } });
		expect(screen.getByText('OKC').classList.contains('team')).toBe(true);
	});

	it('renders the injury size', () => {
		render(TeamMonogram, { props: { code: 'GSW', size: 'injury' } });
		expect(screen.getByText('GSW').classList.contains('injury')).toBe(true);
	});

	it('links the code to the href when one is given', () => {
		render(TeamMonogram, {
			props: { code: 'GSW', size: 'large', href: '/team/gsw' as ResolvedPathname }
		});
		const link = screen.getByRole('link', { name: 'GSW' });
		expect(link.getAttribute('href')).toBe('/team/gsw');
		expect(link.classList.contains('large')).toBe(true);
		expect(link.classList.contains('linked')).toBe(true);
	});

	it('renders a span with no link without an href', () => {
		render(TeamMonogram, { props: { code: 'GSW', size: 'large' } });
		expect(screen.queryByRole('link')).toBeNull();
		expect(screen.getByText('GSW').tagName).toBe('SPAN');
	});

	it('renders the standings size', () => {
		render(TeamMonogram, { props: { code: 'OKC', size: 'standings' } });
		expect(screen.getByText('OKC').classList.contains('standings')).toBe(true);
	});

	it('renders the search size', () => {
		render(TeamMonogram, { props: { code: 'OKC', size: 'search' } });
		expect(screen.getByText('OKC').classList.contains('search')).toBe(true);
	});

	it('renders the cup-draw and cup-champion sizes', () => {
		render(TeamMonogram, { props: { code: 'QXA', size: 'cup-draw' } });
		render(TeamMonogram, { props: { code: 'QXB', size: 'cup-champion' } });
		expect(screen.getByText('QXA').classList.contains('cup-draw')).toBe(true);
		expect(screen.getByText('QXB').classList.contains('cup-champion')).toBe(true);
	});

	it('renders the cup-node size', () => {
		render(TeamMonogram, { props: { code: 'QXC', size: 'cup-node' } });
		expect(screen.getByText('QXC').classList.contains('cup-node')).toBe(true);
	});

	it('renders the playoffs-mvp-team and playoffs-mvp-logo sizes', () => {
		render(TeamMonogram, { props: { code: 'QXA', size: 'playoffs-mvp-team' } });
		expect(screen.getByText('QXA').classList.contains('playoffs-mvp-team')).toBe(true);
		render(TeamMonogram, { props: { code: 'QXB', size: 'playoffs-mvp-logo' } });
		expect(screen.getByText('QXB').classList.contains('playoffs-mvp-logo')).toBe(true);
	});

	it('renders the allstar-league size, linked to the team page', () => {
		const { container } = render(TeamMonogram, {
			props: { code: 'HBR', size: 'allstar-league', href: '/team/hbr' as ResolvedPathname }
		});
		const link = container.querySelector('a');
		expect(link?.classList.contains('allstar-league')).toBe(true);
		expect(link?.getAttribute('href')).toBe('/team/hbr');
	});

	it('renders the names size, not linked', () => {
		const { container } = render(TeamMonogram, { props: { code: 'LKV', size: 'names' } });
		expect(screen.getByText('LKV').classList.contains('names')).toBe(true);
		expect(container.querySelector('a')).toBeNull();
	});

	it('uses the fill box of its parent', () => {
		render(TeamMonogram, { props: { code: 'GSW', size: 'fill' } });
		expect(screen.getByText('GSW').classList.contains('fill')).toBe(true);
	});

	it('draws the logo in the box and calls back on the image error', async () => {
		const onlogoerror = vi.fn();
		const { container } = render(TeamMonogram, {
			props: { code: 'GSW', size: 'fill', logo: 'https://example.com/a.svg', onlogoerror }
		});
		const box = container.querySelector('.team-monogram');
		expect(box?.classList.contains('logo')).toBe(true);
		expect(box?.classList.contains('fill')).toBe(true);
		expect(box?.textContent).toBe('');
		await fireEvent.error(container.querySelector('img') as HTMLImageElement);
		expect(onlogoerror).toHaveBeenCalledOnce();
	});

	it('names a linked logo by its code', () => {
		render(TeamMonogram, {
			props: {
				code: 'GSW',
				size: 'large',
				logo: 'https://example.com/a.svg',
				href: '/team/gsw' as ResolvedPathname
			}
		});
		expect(screen.getByRole('link', { name: 'GSW' })).toBeTruthy();
	});

	it('uses the inline box, with the code and with a logo', () => {
		const plain = render(TeamMonogram, { props: { code: 'GSW', size: 'inline' } });
		expect(screen.getByText('GSW').classList.contains('inline')).toBe(true);
		plain.unmount();
		const { container } = render(TeamMonogram, {
			props: { code: 'GSW', size: 'inline', logo: 'https://example.com/a.svg' }
		});
		const box = container.querySelector('.team-monogram');
		expect(box?.classList.contains('inline')).toBe(true);
		expect(box?.querySelector('img')).not.toBeNull();
	});

	it('loads a logo lazily, linked or not', () => {
		const plain = render(TeamMonogram, {
			props: { code: 'GSW', size: 'large', logo: 'https://example.com/a.svg' }
		});
		expect(plain.container.querySelector('img')?.getAttribute('loading')).toBe('lazy');
		plain.unmount();
		const linked = render(TeamMonogram, {
			props: {
				code: 'GSW',
				size: 'large',
				href: '/team/gsw' as ResolvedPathname,
				logo: 'https://example.com/a.svg'
			}
		});
		expect(linked.container.querySelector('img')?.getAttribute('loading')).toBe('lazy');
	});

	it('hides a logo without logoAlt and names it with logoAlt', () => {
		const hidden = render(TeamMonogram, {
			props: { code: 'GSW', size: 'large', logo: 'https://example.com/a.svg' }
		});
		const img = hidden.container.querySelector('img');
		expect(img?.getAttribute('alt')).toBe('');
		expect(img?.getAttribute('aria-hidden')).toBe('true');
		hidden.unmount();
		const named = render(TeamMonogram, {
			props: {
				code: 'GSW',
				size: 'large',
				logo: 'https://example.com/a.svg',
				logoAlt: 'Warriors logo'
			}
		});
		expect(screen.getByAltText('Warriors logo').getAttribute('aria-hidden')).toBeNull();
		named.unmount();
	});

	it('names a linked logo by logoAlt when there is one', () => {
		const { container } = render(TeamMonogram, {
			props: {
				code: 'GSW',
				size: 'large',
				logo: 'https://example.com/a.svg',
				logoAlt: 'Warriors logo',
				href: '/team/gsw' as ResolvedPathname
			}
		});
		expect(container.querySelector('a')?.getAttribute('aria-label')).toBeNull();
		expect(screen.getByRole('link', { name: 'Warriors logo' })).toBeTruthy();
	});

	it('gives a monogram no aria-label and no aria-hidden, except an inline one', () => {
		const large = render(TeamMonogram, {
			props: { code: 'GSW', size: 'large', href: '/team/gsw' as ResolvedPathname }
		});
		const link = large.container.querySelector('a');
		expect(link?.getAttribute('aria-label')).toBeNull();
		expect(link?.getAttribute('aria-hidden')).toBeNull();
		large.unmount();
		const span = render(TeamMonogram, { props: { code: 'GSW', size: 'large' } });
		expect(span.container.querySelector('span')?.getAttribute('aria-hidden')).toBeNull();
		span.unmount();
		const inline = render(TeamMonogram, { props: { code: 'GSW', size: 'inline' } });
		expect(inline.container.querySelector('span')?.getAttribute('aria-hidden')).toBe('true');
	});
});
