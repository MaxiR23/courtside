// The camera layer shared by the brackets: the only writer of `layer.style.transform`, with the fly
// on the Web Animations API (instant under reduced motion).
import { transformOf, type View } from '#lib/bracket/camera.ts';
import { canAnimate } from '#lib/hero/motion.ts';

export type Flight = { frames: View[]; duration: number; easing: string };

const START: View = { x: 0, y: 0, k: 1 };

export class CameraLayer {
	#layer: HTMLElement | undefined;
	#view: View = START;
	#animation: Animation | undefined;

	get view(): View {
		return this.#view;
	}

	get attached(): boolean {
		return this.#layer !== undefined;
	}

	attach(layer: HTMLElement): void {
		this.#layer = layer;
	}

	detach(): void {
		this.cancel();
		this.#layer = undefined;
	}

	/** The one write to the DOM. */
	apply(view: View): void {
		this.#view = view;
		if (this.#layer) this.#layer.style.transform = transformOf(view);
	}

	cancel(): void {
		const running = this.#animation;
		this.#animation = undefined;
		running?.cancel();
	}

	/** Lands on `to` at once and plays the flight on top. `done` runs when it ends or is cancelled. */
	fly(to: View, flight: (from: View) => Flight, done: () => void): void {
		const layer = this.#layer;
		if (!layer) return;
		const from = this.#view;
		this.cancel();
		this.#view = to;
		layer.style.transform = transformOf(to);
		if (!canAnimate(layer)) {
			done();
			return;
		}
		const { frames, duration, easing } = flight(from);
		const animation = layer.animate(
			frames.map((view) => ({ transform: transformOf(view) })),
			{ duration, easing }
		);
		this.#animation = animation;
		const finish = () => {
			if (this.#animation === animation) this.#animation = undefined;
			done();
		};
		animation.onfinish = finish;
		animation.oncancel = finish;
	}
}
