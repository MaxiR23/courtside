export type Rect = { left: number; top: number; width: number; height: number };

type MatchMedia = (query: string) => { matches: boolean };

function clamp(value: number): number {
	return Math.max(-1, Math.min(1, value));
}

/** Maps a pointer inside the rect to [-1, 1] on each axis; the center is 0. */
export function pointerPosition(
	rect: Rect,
	clientX: number,
	clientY: number
): { x: number; y: number } {
	if (rect.width <= 0 || rect.height <= 0) return { x: 0, y: 0 };
	return {
		x: clamp(((clientX - rect.left) / rect.width) * 2 - 1),
		y: clamp(((clientY - rect.top) / rect.height) * 2 - 1)
	};
}

/** Parallax needs a fine hovering pointer and no reduced-motion request. */
export function parallaxAllowed(matchMedia: MatchMedia | undefined): boolean {
	if (!matchMedia) return false;
	return (
		matchMedia('(hover: hover) and (pointer: fine)').matches &&
		!matchMedia('(prefers-reduced-motion: reduce)').matches
	);
}
