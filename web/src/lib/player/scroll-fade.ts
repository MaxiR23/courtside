// The photo of the player header fades out and drifts down as it scrolls under the top of the
// viewport on desktop. The drift comes from the design tokens; the 90 and the 1.1 are the spec's
// formula. On mobile the photo only fades: from when its top leaves the viewport top until its
// bottom reaches the bottom edge of the stuck section tabs, read from the shared sticky bar state,
// with the curve from the design tokens.
import type { RowLayout } from '#lib/schedule/types.ts';
import { stickyBar } from '#lib/scroll/scrolled-past.svelte.ts';

// docs/design-profiles.md, Player page, Scroll behavior:
// p = clamp((90 − photoTop) / (photoHeight × 1.1), 0, 1)
export const FADE_START_PX = 90;
export const FADE_SPAN = 1.1;

const DRIFT_TOKEN = '--player-photo-drift';
const EASE_TOKEN_MOBILE = '--player-photo-fade-ease-mobile';

type Bezier = [number, number, number, number];

/** Parses `cubic-bezier(x1, y1, x2, y2)`; null if it does not parse or x is outside [0, 1]. */
export function parseCubicBezier(value: string): Bezier | null {
	const number = '(-?(?:\\d+\\.?\\d*|\\.\\d+))';
	const match = new RegExp(
		`^\\s*cubic-bezier\\(\\s*${number}\\s*,\\s*${number}\\s*,\\s*${number}\\s*,\\s*${number}\\s*\\)\\s*$`
	).exec(value);
	if (!match) return null;
	const points = match.slice(1, 5).map(Number) as Bezier;
	if (points.some((n) => !Number.isFinite(n))) return null;
	if (points[0] < 0 || points[0] > 1 || points[2] < 0 || points[2] > 1) return null;
	return points;
}

/** The y of a CSS cubic-bezier at x, found by bisecting the curve parameter. */
export function cubicBezierAt(points: Bezier, x: number): number {
	if (x <= 0) return 0;
	if (x >= 1) return 1;
	const [x1, y1, x2, y2] = points;
	const at = (t: number, a: number, b: number) =>
		3 * (1 - t) ** 2 * t * a + 3 * (1 - t) * t ** 2 * b + t ** 3;
	let low = 0;
	let high = 1;
	for (let i = 0; i < 30; i++) {
		const mid = (low + high) / 2;
		if (at(mid, x1, x2) < x) low = mid;
		else high = mid;
	}
	return at((low + high) / 2, y1, y2);
}

/**
 * How far the photo has faded on mobile, from 0 to 1, eased: 0 while its top is at or below the
 * viewport top, 1 once its bottom reaches the bar's bottom edge.
 */
export function mobileFadeProgress(
	top: number,
	height: number,
	barBottom: number,
	ease: Bezier | null
): number {
	if (height <= 0) return 0;
	const distance = height - barBottom;
	// A photo no taller than the bar has its bottom above the bar's bottom as soon as it leaves the top.
	if (distance <= 0) return top < 0 ? 1 : 0;
	const linear = Math.min(1, Math.max(0, -top / distance));
	return ease ? cubicBezierAt(ease, linear) : linear;
}

/** How far the photo has faded, from 0 (in place) to 1 (gone). */
export function fadeProgress(top: number, height: number): number {
	if (height <= 0) return 0;
	return Math.min(1, Math.max(0, (FADE_START_PX - top) / (height * FADE_SPAN)));
}

/**
 * Writes opacity (and, on desktop, transform) on the node on each scroll, one frame at a time.
 * Does nothing under reduced motion or without requestAnimationFrame.
 */
export function scrollFade(
	node: HTMLElement,
	layout: RowLayout = 'desktop'
): { update(next: RowLayout): void; destroy(): void } | undefined {
	if (typeof requestAnimationFrame !== 'function') return undefined;
	if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return undefined;
	const style = getComputedStyle(node);
	const read = (name: string) => style.getPropertyValue(name);
	const drift = parseFloat(read(DRIFT_TOKEN)) || 0;
	const ease = parseCubicBezier(read(EASE_TOKEN_MOBILE));
	let current = layout;
	let pending: number | null = null;
	// The drift last written: the rect includes it, so it is taken out to get the layout top.
	let written = 0;

	const apply = () => {
		pending = null;
		if (current === 'mobile') {
			// The bar's bottom edge comes from the shared sticky bar state, read on every frame.
			const rect = node.getBoundingClientRect();
			node.style.opacity = String(
				1 - mobileFadeProgress(rect.top, rect.height, stickyBar.bottom, ease)
			);
			return;
		}
		const rect = node.getBoundingClientRect();
		const p = fadeProgress(rect.top - written, rect.height);
		written = p * drift;
		node.style.opacity = String(1 - p);
		node.style.transform = `translateY(${written}px)`;
	};
	const onScroll = () => {
		if (pending === null) pending = requestAnimationFrame(apply);
	};

	pending = requestAnimationFrame(apply);
	window.addEventListener('scroll', onScroll, { passive: true });
	return {
		update(next: RowLayout) {
			if (next === current) return;
			current = next;
			written = 0;
			if (next === 'mobile') node.style.transform = '';
			onScroll();
		},
		destroy() {
			window.removeEventListener('scroll', onScroll);
			if (pending !== null) cancelAnimationFrame(pending);
			pending = null;
		}
	};
}
