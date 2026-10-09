/**
 * Whether the search overlay is open, shared by the nav triggers and the root layout, which
 * renders the overlay once for the whole visit. It also holds the trigger that gets the focus
 * back on close.
 */
export class SearchOverlayState {
	open = $state(false);

	#trigger: HTMLElement | null = null;

	/** Keeps the latest trigger. The cleanup clears it only if it is still the same element. */
	register(trigger: HTMLElement): () => void {
		this.#trigger = trigger;
		return () => {
			if (this.#trigger === trigger) this.#trigger = null;
		};
	}

	show(): void {
		this.open = true;
	}

	close(): void {
		this.open = false;
		this.#trigger?.focus();
	}
}

export const searchOverlay = new SearchOverlayState();
