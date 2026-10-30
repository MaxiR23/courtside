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
