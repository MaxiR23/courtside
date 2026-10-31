import { untrack } from 'svelte';
import { SvelteMap } from 'svelte/reactivity';

export class ScrolledPastWatch {
	passed = $state(false); // true once the element's bottom edge has left the top of the viewport

	/** Follows `node` against the viewport. Returns the cleanup. */
	observe(node: Element): () => void {
		if (typeof IntersectionObserver !== 'function') return () => {};
		const observer = new IntersectionObserver((entries) => {
			const entry = entries[entries.length - 1];
			if (!entry) return;
			this.passed = !entry.isIntersecting && entry.boundingClientRect.top < 0;
		});
		observer.observe(node);
		return () => observer.disconnect();
	}
}

/** One followed bar: its own stuck state and bottom edge. */
class BarEntry {
	#watch = new ScrolledPastWatch(); // follows the sentinel right above the bar
	#bottom = $state(0);
	#stop: () => void;

	constructor(sentinel: Element, bar: HTMLElement) {
		const unwatch = this.#watch.observe(sentinel);
		const measure = () => {
			this.#bottom =
				(parseFloat(getComputedStyle(bar).top) || 0) + bar.getBoundingClientRect().height;
		};
		measure();
		const resize = typeof ResizeObserver === 'function' ? new ResizeObserver(measure) : null;
		resize?.observe(bar);
		this.#stop = () => {
			unwatch();
			resize?.disconnect();
		};
	}

	get stuck(): boolean {
		return this.#watch.passed;
	}

	get bottom(): number {
		return this.#bottom;
	}

	stop(): void {
		this.#stop();
	}
}

/**
 * The sticky section tab bars, shared by every piece that depends on them. Each bar has its own
 * stuck state (its sentinel has left the top of the viewport) and bottom edge (its sticky top plus
 * its height). `stuck` and `bottom` are the page's bar: the latest registered one still mounted.
 */
export class StickyBarState {
	#bars = new SvelteMap<HTMLElement, BarEntry>();

	#page(): BarEntry | undefined {
		let last: BarEntry | undefined;
		for (const entry of this.#bars.values()) last = entry;
		return last;
	}

	/** True while `bar` is stuck. False for null or a bar that is not registered. */
	stuckOf(bar: HTMLElement | null): boolean {
		return (bar && this.#bars.get(bar)?.stuck) ?? false;
	}

	/** `bar`'s bottom edge while stuck, in px from the top of the viewport. 0 for null or a bar that is not registered. */
	bottomOf(bar: HTMLElement | null): number {
		return (bar && this.#bars.get(bar)?.bottom) ?? 0;
	}

	/** True while the page's bar is stuck. False with no bar. */
	get stuck(): boolean {
		return this.#page()?.stuck ?? false;
	}

	/** The page's bar bottom edge, in px from the top of the viewport: its sticky top plus its height. 0 with no bar. */
	get bottom(): number {
		return this.#page()?.bottom ?? 0;
	}

	/** Follows `bar` through `sentinel`, an empty element right above it in the flow. Returns the cleanup, which removes only this registration. */
	observe(sentinel: Element, bar: HTMLElement): () => void {
		// Untracked: the caller is an effect, which must not depend on the map it writes.
		const entry = untrack(() => {
			this.#bars.get(bar)?.stop();
			this.#bars.delete(bar); // re-registering moves the bar to the end: it is the latest
			const created = new BarEntry(sentinel, bar);
			this.#bars.set(bar, created);
			return created;
		});
		return () => {
			entry.stop();
			untrack(() => {
				if (this.#bars.get(bar) === entry) this.#bars.delete(bar);
			});
		};
	}
}

export const stickyBar = new StickyBarState();
