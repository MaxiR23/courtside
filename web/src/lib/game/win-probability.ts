// Pure geometry of the win probability chart. The x domain is the feed's own
// points, in seconds: no period length is assumed anywhere.

export const CHART_WIDTH = 1000;
export const CHART_HEIGHT = 200;

export type ChartPoint = { elapsedSeconds: number; homeWinProbability: number };
export type Segment = { x0: number; y0: number; x1: number; y1: number };

function checkSeconds(seconds: number): void {
	if (!Number.isFinite(seconds) || seconds < 0) {
		throw new RangeError(`Invalid elapsed seconds: ${seconds}`);
	}
}

/** The x domain, 0 to the largest elapsed seconds among the points; one second at least. */
export function span(points: readonly ChartPoint[]): number {
	if (points.length === 0) throw new RangeError('A chart needs at least one point');
	for (const point of points) checkSeconds(point.elapsedSeconds);
	return Math.max(1, ...points.map((p) => p.elapsedSeconds));
}

/** The horizontal scale that fits the span in the viewBox width. */
export function xScale(domain: number): number {
	if (!Number.isFinite(domain) || domain <= 0) throw new RangeError(`Invalid span: ${domain}`);
	return CHART_WIDTH / domain;
}

/** x in seconds; y from the top, which is 100% home. */
export function toPoint(point: ChartPoint): { x: number; y: number } {
	checkSeconds(point.elapsedSeconds);
	const p = point.homeWinProbability;
	if (!Number.isFinite(p) || p < 0 || p > 1) throw new RangeError(`Invalid probability: ${p}`);
	return { x: point.elapsedSeconds, y: (1 - p) * CHART_HEIGHT };
}

/** Consecutive pairs of points, in feed order. */
export function segments(points: readonly ChartPoint[]): Segment[] {
	const mapped = points.map(toPoint);
	return mapped.slice(1).map((to, i) => ({ x0: mapped[i].x, y0: mapped[i].y, x1: to.x, y1: to.y }));
}

/** The latest point (last in feed order) as fractions of the chart, 0 to 1. */
export function markerPosition(points: readonly ChartPoint[]): { left: number; top: number } {
	const domain = span(points);
	const { x, y } = toPoint(points[points.length - 1]);
	return { left: x / domain, top: y / CHART_HEIGHT };
}
