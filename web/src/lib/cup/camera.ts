// Camera math of the Cup bracket. A view is a translate in px and a scale: a world point (wx, wy)
// shows at (x + wx * k, y + wy * k) inside the viewport. Pure functions only; BracketCamera applies
// them. The constants marked "token" mirror the --bracket-* tokens, pinned by tests/lib/cup/camera.test.ts.

export type View = { x: number; y: number; k: number };
export type Size = { width: number; height: number };
export type Bounds = { min: number; max: number };
export type WheelIntent = 'zoom' | 'pan' | 'page';
export type WheelLike = { deltaX: number; deltaY: number; deltaMode: number; ctrlKey: boolean };

export const LEVEL_THRESHOLD = 0.36; // token --bracket-level-threshold
export const ZOOM_MIN_OF_FIT = 0.75; // token --bracket-zoom-min
export const ZOOM_MAX = 4; // token --bracket-zoom-max
export const DRAG_THRESHOLD_PX = 6; // token --bracket-drag-threshold
export const FLY_MS = 560; // token --bracket-fly-duration

// Plan choices, not in the design.
export const ZOOM_STEP = 1.5;
export const WHEEL_RATE = 0.002; // per pixel of deltaY
export const LINE_HEIGHT_PX = 16; // deltaMode 1
export const PAGE_HEIGHT_PX = 400; // deltaMode 2
export const FLY_STEPS = 24;
export const MOUSE_WHEEL_MIN = 50;

const MIN_SCALE = 1e-6; // the fit of a viewport with no size
const FIT_TOLERANCE = 1e-6;

/** True when the viewport has a size, so a fit can mean something. */
export const isMeasured = (viewport: Size): boolean => viewport.width > 0 && viewport.height > 0;

const clamp = (value: number, min: number, max: number): number =>
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

/** From 0.75 times the fit to 4. */
export function zoomBounds(fitK: number): Bounds {
	return { min: ZOOM_MIN_OF_FIT * fitK, max: Math.max(ZOOM_MAX, fitK) };
}

/** Scales the view by `factor` around a viewport point, which keeps the world point under it. */
export function zoomAt(
	view: View,
	point: { x: number; y: number },
	factor: number,
	bounds: Bounds
): View {
	const k = clamp(view.k * factor, bounds.min, bounds.max);
	const ratio = k / view.k;
	return { x: point.x - (point.x - view.x) * ratio, y: point.y - (point.y - view.y) * ratio, k };
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

/**
 * What a wheel event means. Ctrl (a trackpad pinch) zooms; at fit a mostly vertical scroll belongs
 * to the page; a mouse wheel (line steps, or whole vertical notches) zooms; the rest is a trackpad pan.
 */
export function wheelIntent(event: WheelLike, atFit: boolean): WheelIntent {
	if (event.ctrlKey) return 'zoom';
	if (atFit && Math.abs(event.deltaY) >= Math.abs(event.deltaX)) return 'page';
	if (event.deltaMode !== 0) return 'zoom';
	const notch =
		event.deltaX === 0 &&
		Number.isInteger(Math.abs(event.deltaY)) &&
		Math.abs(event.deltaY) >= MOUSE_WHEEL_MIN;
	return notch ? 'zoom' : 'pan';
}

export function wheelFactor(deltaY: number, deltaMode: number): number {
	const unit = deltaMode === 1 ? LINE_HEIGHT_PX : deltaMode === 2 ? PAGE_HEIGHT_PX : 1;
	return Math.exp(-deltaY * unit * WHEEL_RATE);
}

export const levelOf = (k: number): 1 | 2 => (k < LEVEL_THRESHOLD ? 1 : 2);

/** Level 1 is the fit. Level 2 is the threshold scale (or the fit if larger) around the viewport center. */
export function levelTarget(level: 1 | 2, fit: View, current: View, viewport: Size): View {
	if (level === 1) return fit;
	const k = Math.max(LEVEL_THRESHOLD, fit.k);
	const cx = viewport.width / 2;
	const cy = viewport.height / 2;
	const wx = (cx - current.x) / current.k;
	const wy = (cy - current.y) / current.k;
	return { x: cx - wx * k, y: cy - wy * k, k };
}

export const dragStarted = (dx: number, dy: number): boolean =>
	Math.hypot(dx, dy) > DRAG_THRESHOLD_PX;

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
