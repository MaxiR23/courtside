// The photo of the player header fades out and drifts down as it scrolls under the top of the
// viewport. The drift comes from the design tokens; the 90 and the 1.1 are the spec's formula.

// docs/design-profiles.md, Player page, Scroll behavior:
// p = clamp((90 − photoTop) / (photoHeight × 1.1), 0, 1)
export const FADE_START_PX = 90;
export const FADE_SPAN = 1.1;

const DRIFT_TOKEN = '--player-photo-drift';

/** How far the photo has faded, from 0 (in place) to 1 (gone). */
export function fadeProgress(top: number, height: number): number {
	if (height <= 0) return 0;
	return Math.min(1, Math.max(0, (FADE_START_PX - top) / (height * FADE_SPAN)));
}

/**
 * Writes opacity and transform on the node on each scroll, one frame at a time. Does nothing
 * under reduced motion or without requestAnimationFrame.
 */
export function scrollFade(node: HTMLElement): { destroy(): void } | undefined {
	if (typeof requestAnimationFrame !== 'function') return undefined;
	if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return undefined;
	const drift = parseFloat(getComputedStyle(node).getPropertyValue(DRIFT_TOKEN)) || 0;
	let pending: number | null = null;
	// The drift last written: the rect includes it, so it is taken out to get the layout top.
	let written = 0;

	const apply = () => {
		pending = null;
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
		destroy() {
			window.removeEventListener('scroll', onScroll);
			if (pending !== null) cancelAnimationFrame(pending);
			pending = null;
		}
	};
}
