import { CameraLayer } from '#lib/bracket/layer.ts';
import { FIT_MARGIN } from '#lib/cup/bracket-layout.ts';
import {
	type Bounds,
	dragStarted,
	fitView,
	FLY_MS,
	FLY_STEPS,
	flyFrames,
	isAtFit,
	isMeasured,
	levelOf,
	levelTarget,
	panBy,
	type Size,
	type View,
	wheelFactor,
	wheelIntent,
	ZOOM_STEP,
	zoomAt,
	zoomBounds
} from '#lib/cup/camera.ts';

type PointerLike = {
	button: number;
	clientX: number;
	clientY: number;
	pointerId: number;
	currentTarget: EventTarget | null;
};

type Rect = Pick<DOMRect, 'left' | 'top'>;

const START: View = { x: 0, y: 0, k: 1 };

/**
 * The camera of the Cup bracket. The view is a plain private field and `level` and `atFit` are the
 * only reactive values, so panning and zooming re-render nothing: every input writes one thing,
 * `layer.style.transform`. A fly plays the sampled frames on the Web Animations API (instant under
 * reduced motion).
 */
export class BracketCamera {
	level = $state<1 | 2>(1);
	atFit = $state(true);
	/** True from a drag that started until the next pointer down: the click that ends it is swallowed. */
	suppressClick = false;

	#camera = new CameraLayer();
	#world: Size = { width: 0, height: 0 };
	#viewport: Size = { width: 0, height: 0 };
	#interactive = false;
	#fit: View = START;
	#bounds: Bounds = zoomBounds(START.k);
	#press: { id: number; startX: number; startY: number; lastX: number; lastY: number } | null =
		null;
	#dragging = false;

	attach(layer: HTMLElement, world: Size, viewport: Size, interactive: boolean): void {
		this.#camera.attach(layer);
		this.#world = world;
		this.#interactive = interactive;
		this.resize(viewport);
	}

	/** Back to the fit, at once. A viewport with no size is not measured yet and changes nothing. */
	resize(viewport: Size): void {
		this.#viewport = viewport;
		if (!this.#camera.attached || !isMeasured(viewport)) return;
		this.#camera.cancel();
		this.#fit = fitView(this.#world, viewport, FIT_MARGIN);
		this.#bounds = zoomBounds(this.#fit.k);
		this.#apply(this.#fit);
	}

	wheel(event: WheelEvent, rect: Rect): void {
		if (!this.#ready()) return;
		const intent = wheelIntent(event, isAtFit(this.#camera.view, this.#fit.k));
		if (intent === 'page') return;
		event.preventDefault();
		this.#camera.cancel();
		if (intent === 'zoom') {
			const point = { x: event.clientX - rect.left, y: event.clientY - rect.top };
			const factor = wheelFactor(event.deltaY, event.deltaMode);
			this.#apply(zoomAt(this.#camera.view, point, factor, this.#bounds));
		} else {
			this.#apply(
				panBy(this.#camera.view, -event.deltaX, -event.deltaY, this.#world, this.#viewport)
			);
		}
	}

	pointerDown(event: PointerLike): void {
		if (!this.#ready() || event.button !== 0) return;
		this.suppressClick = false;
		this.#dragging = false;
		this.#press = {
			id: event.pointerId,
			startX: event.clientX,
			startY: event.clientY,
			lastX: event.clientX,
			lastY: event.clientY
		};
	}

	pointerMove(event: PointerLike): void {
		const press = this.#press;
		if (!press || event.pointerId !== press.id) return;
		if (!this.#dragging) {
			if (!dragStarted(event.clientX - press.startX, event.clientY - press.startY)) return;
			this.#dragging = true;
			this.suppressClick = true;
			this.#camera.cancel();
			(event.currentTarget as Element | null)?.setPointerCapture?.(event.pointerId);
		}
		const dx = event.clientX - press.lastX;
		const dy = event.clientY - press.lastY;
		press.lastX = event.clientX;
		press.lastY = event.clientY;
		this.#apply(panBy(this.#camera.view, dx, dy, this.#world, this.#viewport));
	}

	pointerUp(event: PointerLike): void {
		const press = this.#press;
		if (!press || event.pointerId !== press.id) return;
		if (this.#dragging) {
			(event.currentTarget as Element | null)?.releasePointerCapture?.(event.pointerId);
		}
		this.#press = null;
		this.#dragging = false;
	}

	zoomIn(): void {
		this.#zoomBy(ZOOM_STEP);
	}

	zoomOut(): void {
		this.#zoomBy(1 / ZOOM_STEP);
	}

	fit(): void {
		if (this.#ready()) this.#fly(this.#fit);
	}

	goToLevel(level: 1 | 2): void {
		if (!this.#ready()) return;
		this.#fly(levelTarget(level, this.#fit, this.#camera.view, this.#viewport));
	}

	/** The viewport scrolled natively by (dx, dy): the camera follows so the drawing stays where it is. */
	shift(dx: number, dy: number): void {
		if (!this.#ready()) return;
		this.#camera.cancel();
		this.#apply(panBy(this.#camera.view, -dx, -dy, this.#world, this.#viewport));
	}

	destroy(): void {
		this.#camera.detach();
	}

	#ready(): boolean {
		return this.#interactive && this.#camera.attached && isMeasured(this.#viewport);
	}

	#zoomBy(factor: number): void {
		if (!this.#ready()) return;
		const center = { x: this.#viewport.width / 2, y: this.#viewport.height / 2 };
		this.#fly(zoomAt(this.#camera.view, center, factor, this.#bounds));
	}

	#sync(): void {
		this.level = levelOf(this.#camera.view.k);
		this.atFit = isAtFit(this.#camera.view, this.#fit.k);
	}

	#apply(view: View): void {
		this.#camera.apply(view);
		this.#sync();
	}

	#fly(to: View): void {
		this.#camera.fly(
			to,
			(from) => ({
				frames: flyFrames(from, to, this.#viewport, FLY_STEPS),
				duration: FLY_MS,
				easing: 'linear'
			}),
			() => this.#sync()
		);
	}
}
