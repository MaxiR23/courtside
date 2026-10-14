// Camera math shared by the brackets. A view is a translate in px and a scale: a world point (wx, wy)
// shows at (x + wx * k, y + wy * k) inside the viewport. Pure functions only; each bracket's camera
// applies them.

export type View = { x: number; y: number; k: number };
export type Size = { width: number; height: number };
export type Bounds = { min: number; max: number };
export type Rect = { x: number; y: number; width: number; height: number };

export const MIN_SCALE = 1e-6; // the fit of a viewport with no size
export const FIT_TOLERANCE = 1e-6;

/** True when the viewport has a size, so a fit can mean something. */
export const isMeasured = (viewport: Size): boolean => viewport.width > 0 && viewport.height > 0;

export const clamp = (value: number, min: number, max: number): number =>
	Math.min(Math.max(value, min), max);

/** The whole world inside the viewport with `margin` world units around it, centered. */
export function fitView(world: Size, viewport: Size, margin: number): View {
	const k = Math.max(
		Math.min(
			viewport.width / (world.width + 2 * margin),
			viewport.height / (world.height + 2 * margin)
		),
		MIN_SCALE
	);
	return {
		x: (viewport.width - world.width * k) / 2,
		y: (viewport.height - world.height * k) / 2,
		k
	};
}

/** A world rect inside the viewport with `margin` world units around it, centered, at most `maxK`. */
export function fitRect(rect: Rect, viewport: Size, margin: number, maxK: number): View {
	const k = Math.max(
		Math.min(
			viewport.width / (rect.width + 2 * margin),
			viewport.height / (rect.height + 2 * margin),
			maxK
		),
		MIN_SCALE
	);
	return {
		x: viewport.width / 2 - (rect.x + rect.width / 2) * k,
		y: viewport.height / 2 - (rect.y + rect.height / 2) * k,
		k
	};
}

/** Moves the view, keeping the center of the viewport inside the scaled world. */
export function panBy(view: View, dx: number, dy: number, world: Size, viewport: Size): View {
	const cx = viewport.width / 2;
	const cy = viewport.height / 2;
	return {
		x: clamp(view.x + dx, cx - world.width * view.k, cx),
		y: clamp(view.y + dy, cy - world.height * view.k, cy),
		k: view.k
	};
}

export function isAtFit(view: View, fitK: number): boolean {
	return Math.abs(view.k - fitK) <= fitK * FIT_TOLERANCE;
}

export const cubicInOut = (t: number): number =>
	t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

const lerp = (a: number, b: number, t: number): number => a + (b - a) * t;

/**
 * The views of a fly: `steps + 1` of them, the first `from` and the last `to`. With e the eased
 * progress, the world point at the viewport center moves linearly in e and the scale in log space.
 */
export function flyFrames(from: View, to: View, viewport: Size, steps: number): View[] {
	const cx = viewport.width / 2;
	const cy = viewport.height / 2;
	const a = { x: (cx - from.x) / from.k, y: (cy - from.y) / from.k };
	const b = { x: (cx - to.x) / to.k, y: (cy - to.y) / to.k };
	const frames: View[] = [from];
	for (let i = 1; i < steps; i++) {
		const e = cubicInOut(i / steps);
		const k = Math.exp(lerp(Math.log(from.k), Math.log(to.k), e));
		frames.push({ x: cx - lerp(a.x, b.x, e) * k, y: cy - lerp(a.y, b.y, e) * k, k });
	}
	frames.push(to);
	return frames;
}

export const transformOf = (view: View): string =>
	`translate(${view.x}px, ${view.y}px) scale(${view.k})`;
