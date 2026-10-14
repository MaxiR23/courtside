import { fitRect, fitView, isMeasured, panBy, type Size, type View } from '#lib/bracket/camera.ts';
import { CameraLayer } from '#lib/bracket/layer.ts';
import type { SeriesId } from '#lib/contract/playoffs.ts';
import {
	FIT_MARGIN,
	SERIES_IDS,
	SERIES_MARGIN,
	SERIES_ZOOM_MAX,
	seriesRect,
	step,
	WORLD
} from '#lib/playoffs/bracket-layout.ts';

export const CAMERA_MS = 800; // token --playoffs-camera-duration
export const CAMERA_EASING = 'cubic-bezier(0.2, 0.7, 0.1, 1)'; // token --playoffs-camera-easing, which is --ease

/**
 * The camera of the playoffs bracket. Level 1 fits the whole bracket and level 2 fits the selected
 * series with its games list. `level` and `selected` are the only reactive values, so a move
 * re-renders nothing but the controls: every move writes one thing, `layer.style.transform`. A fly
 * plays two keyframes on the Web Animations API (instant under reduced motion).
 */
export class SeriesCamera {
	level = $state<1 | 2>(1);
	selected = $state<SeriesId | null>(null);

	#camera = new CameraLayer();
	#viewport: Size = { width: 0, height: 0 };
	#games: Partial<Record<SeriesId, number>> = {};

	attach(layer: HTMLElement, viewport: Size, games: Partial<Record<SeriesId, number>>): void {
		this.#camera.attach(layer);
		this.#games = games;
		this.resize(viewport);
	}

	/** Back to the target of the current level, at once. A viewport with no size changes nothing. */
	resize(viewport: Size): void {
		this.#viewport = viewport;
		if (!this.#camera.attached || !isMeasured(viewport)) return;
		this.#camera.cancel();
		this.#camera.apply(this.#target());
	}

	/** The number of listed games of each series, which sizes the level 2 view. Does not move the camera. */
	setGames(games: Partial<Record<SeriesId, number>>): void {
		this.#games = games;
	}

	select(id: SeriesId): void {
		this.selected = id;
		this.level = 2;
		this.#fly();
	}

	overview(): void {
		this.level = 1;
		this.#fly();
	}

	seriesLevel(): void {
		this.select(this.selected ?? SERIES_IDS[0]);
	}

	next(): void {
		this.select(step(this.selected, 1));
	}

	prev(): void {
		this.select(step(this.selected, -1));
	}

	/** A native scroll of the clipped viewport, taken as a pan: the camera keeps the focused card in view. */
	shift(dx: number, dy: number): void {
		if (!this.#camera.attached || !isMeasured(this.#viewport)) return;
		this.#camera.cancel();
		this.#camera.apply(panBy(this.#camera.view, -dx, -dy, WORLD, this.#viewport));
	}

	destroy(): void {
		this.#camera.detach();
	}

	#target(): View {
		if (this.level === 2 && this.selected !== null) {
			const rect = seriesRect(this.selected, this.#games[this.selected] ?? 0);
			return fitRect(rect, this.#viewport, SERIES_MARGIN, SERIES_ZOOM_MAX);
		}
		return fitView(WORLD, this.#viewport, FIT_MARGIN);
	}

	#fly(): void {
		if (!this.#camera.attached || !isMeasured(this.#viewport)) return;
		const to = this.#target();
		this.#camera.fly(
			to,
			(from) => ({ frames: [from, to], duration: CAMERA_MS, easing: CAMERA_EASING }),
			() => {}
		);
	}
}
