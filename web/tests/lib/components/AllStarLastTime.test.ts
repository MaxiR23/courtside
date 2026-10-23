// web/tests/lib/components/AllStarLastTime.test.ts
//
// Tests for the AllStarLastTime component.
//
// Tested:
// - The champion card: kicker, name, date and venue, score
// - The MVP card: name, league team and summary, linking to the player
// - The MVP photo column first, with the headshot and the jersey watermark (none without a jersey), initials without a photo
// - The MVP card stacked photo-first on mobile, and its sizes from tokens (source check)
// - No MVP card without an MVP
// - The link text and its href /all-star/previous
// - The champion card links to the edition video in a new tab when there is one, and is not a link otherwise
//
// What is covered:
// - Each state the section shows, drawn from the recorded feeds
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/AllStarLastTime.test.ts
//
// SEE: web/src/lib/components/AllStarLastTime.svelte
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import AllStarLastTime from '../../../src/lib/components/AllStarLastTime.svelte';
import { playerHref, viewOf } from '../all-star/views';

const source = readFileSync(
	join(__dirname, '..', '..', '..', 'src', 'lib', 'components', 'AllStarLastTime.svelte'),
	'utf8'
);
const lastTime = () => viewOf('before').lastTime!;
const show = (view = lastTime(), layout: 'desktop' | 'mobile' = 'desktop') =>
	render(AllStarLastTime, { props: { lastTime: view, layout, playerHref } });

describe('AllStarLastTime', () => {
	it('draws every frame with the All-Star corner marks', () => {
		const { container } = show();
		const frames = container.querySelectorAll('.blueprint-frame');
		expect(frames.length).toBeGreaterThan(0);
		for (const frame of frames) expect(frame.classList.contains('marks-allstar')).toBe(true);
	});

	it('shows the champion card', () => {
		show();
		expect(screen.getByText('Champions of the day')).toBeTruthy();
		expect(screen.getByText('Team Dunes')).toBeTruthy();
		expect(screen.getByText('Feb 15 · Example Arena')).toBeTruthy();
		expect(screen.getByText('22–20')).toBeTruthy();
	});

	it('shows the MVP card linking to the player', () => {
		const { container } = show();
		const card = container.querySelector('a.mvp-card')!;
		expect(card.getAttribute('href')).toBe('/player/4001');
		expect(card.textContent).toContain('Gus Imagined');
		expect(card.textContent).toContain('RDG');
		expect(card.textContent).toContain('24 PTS · across 2 games');
	});

	it('draws no MVP card without an MVP', () => {
		const { container } = show({ ...lastTime(), mvp: null });
		expect(container.querySelector('.mvp-card')).toBeNull();
		expect(screen.getByText('Team Dunes')).toBeTruthy();
	});

	it('links to the previous edition', () => {
		show();
		const link = screen.getByRole('link', {
			name: 'Every game, box score and highlight from 2026 →'
		});
		expect(link.getAttribute('href')).toBe('/all-star/previous');
	});

	it('adds the mobile class with the mobile layout', () => {
		const { container } = show(lastTime(), 'mobile');
		expect(container.querySelector('.last-time')?.classList.contains('mobile')).toBe(true);
	});
});

describe('AllStarLastTime MVP photo column', () => {
	it('draws the photo column first with the headshot and the jersey watermark', () => {
		const { container } = show();
		const card = container.querySelector('a.mvp-card')!;
		expect(card.firstElementChild?.classList.contains('photo')).toBe(true);
		expect(card.querySelector('.photo .avatar.allstar-plate img')?.getAttribute('src')).toBe(
			'https://example.com/photos/4001.png'
		);
		const mark = card.querySelector('.photo .watermark');
		expect(mark?.textContent).toBe('21');
		expect(mark?.getAttribute('aria-hidden')).toBe('true');
	});

	it('draws no watermark without a jersey', () => {
		const { container } = show({ ...lastTime(), mvp: { ...lastTime().mvp!, jersey: null } });
		expect(container.querySelector('.watermark')).toBeNull();
		expect(container.querySelector('.photo img')).not.toBeNull();
	});

	it('keeps the initials without a photo', () => {
		show({ ...lastTime(), mvp: { ...lastTime().mvp!, photo: null } });
		expect(screen.getByRole('img', { name: 'Gus Imagined' }).textContent).toBe('GI');
	});

	it('stacks the photo on top on mobile', () => {
		const { container } = show(lastTime(), 'mobile');
		expect(container.querySelector('.last-time')?.classList.contains('mobile')).toBe(true);
		expect(
			container.querySelector('.mvp-card')?.firstElementChild?.classList.contains('photo')
		).toBe(true);
		expect(source).toContain('grid-template-columns: minmax(0, 1fr)');
		expect(source).toContain('height: var(--allstar-last-mvp-photo-height-mobile)');
	});

	it('takes the photo column, the glow, the name and the league mark from tokens', () => {
		for (const part of [
			'grid-template-columns: var(--allstar-last-mvp-photo-width) 1fr',
			'var(--allstar-plate-glow)',
			'bottom: 0',
			'font-weight: var(--font-weight-semibold)',
			'font-size: var(--allstar-last-mvp-name-size)',
			'font-size: var(--allstar-last-mvp-league-size)'
		]) {
			expect(source).toContain(part);
		}
	});
});

describe('AllStarLastTime edition video', () => {
	const URL_ = 'https://video.example.com/embed/last';

	it('links the champion card to the video in a new tab', () => {
		const { container } = show({ ...lastTime(), video: URL_ });
		const card = container.querySelector('a.champion-card')!;
		expect(card.getAttribute('href')).toBe(URL_);
		expect(card.getAttribute('target')).toBe('_blank');
		expect(card.getAttribute('rel')).toContain('noopener');
		expect(card.textContent).toContain('Team Dunes');
		expect(screen.getByRole('link', { name: /Every game/ }).getAttribute('href')).toBe(
			'/all-star/previous'
		);
	});

	it('draws the champion card as a plain block without a video', () => {
		const { container } = show({ ...lastTime(), video: null });
		expect(container.querySelector('a.champion-card')).toBeNull();
		expect(container.querySelector('div.champion-card')?.textContent).toContain('Team Dunes');
		expect(screen.getByRole('link', { name: /Every game/ }).getAttribute('href')).toBe(
			'/all-star/previous'
		);
	});
});
