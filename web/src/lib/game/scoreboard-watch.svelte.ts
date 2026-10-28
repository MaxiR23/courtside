export class ScoreboardWatch {
	passed = $state(false); // true once the scoreboard is fully above the bottom of the tab bar

	/** Follows `node` against the viewport minus the top `offset` px (the tab bar). Returns the cleanup. */
	observe(node: Element, offset: number): () => void {
		if (typeof IntersectionObserver !== 'function') return () => {};
		const observer = new IntersectionObserver(
			(entries) => {
				const entry = entries[entries.length - 1];
				if (!entry) return;
				this.passed = !entry.isIntersecting && entry.boundingClientRect.top < offset;
			},
			{ rootMargin: `-${offset}px 0px 0px 0px` }
		);
		observer.observe(node);
		return () => observer.disconnect();
	}
}
