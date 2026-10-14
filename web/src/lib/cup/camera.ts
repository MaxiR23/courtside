// Camera math of the Cup bracket. The view math shared with the playoffs bracket lives in
// #lib/bracket/camera.ts and is re-exported here. Pure functions only; BracketCamera applies them.
// The constants marked "token" mirror the --bracket-* tokens, pinned by tests/lib/cup/camera.test.ts.
import { type Bounds, clamp, type Size, type View } from '#lib/bracket/camera.ts';

export {
	cubicInOut,
	fitView,
	flyFrames,
	isAtFit,
	isMeasured,
	panBy,
	transformOf
} from '#lib/bracket/camera.ts';
export type { Bounds, Size, View } from '#lib/bracket/camera.ts';

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
