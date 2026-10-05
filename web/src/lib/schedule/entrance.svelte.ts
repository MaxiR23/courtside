export class ListEntrance {
	run = $state(0); // 0 until the list is first seen or the day changes; rekeys the list
	waiting = $state(false); // true while an observer waits for the first view
	#seen = false;

	/** Bumps `run` the first time `node` scrolls into view. Returns the cleanup. */
	observe(node: Element): () => void {
		if (this.#seen || typeof IntersectionObserver !== 'function') return () => {};
		const observer = new IntersectionObserver((entries) => {
			if (this.#seen || !entries.some((e) => e.isIntersecting)) return;
			this.#seen = true;
			this.waiting = false;
			this.run += 1;
			observer.disconnect();
		});
		observer.observe(node);
		this.waiting = true;
		return () => observer.disconnect();
	}

	replay(): void {
		this.run += 1;
	}
}
