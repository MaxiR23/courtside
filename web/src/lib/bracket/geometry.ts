// Node and connector geometry shared by the brackets, in world units.
import type { Size } from '#lib/bracket/camera.ts';

export type Point = { x: number; y: number };

/**
 * The orthogonal connector between two nodes of size `node`: from the right edge middle of `from`
 * to the left edge middle of `to`, or the other way round when `mirrored` (the West side).
 */
export function elbowPath(from: Point, to: Point, node: Size, mirrored: boolean): string {
	const y1 = from.y + node.height / 2;
	const y2 = to.y + node.height / 2;
	const x1 = mirrored ? from.x : from.x + node.width;
	const x2 = mirrored ? to.x + node.width : to.x;
	const xm = (x1 + x2) / 2;
	return `M ${x1} ${y1} H ${xm} V ${y2} H ${x2}`;
}
