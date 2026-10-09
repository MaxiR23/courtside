// DOM helpers for the search dialog: the scroll lock and the focus trap.

/** Locks the page's scroll. Returns the function that restores the previous inline value. */
export function lockBodyScroll(body: HTMLElement): () => void {
	const previous = body.style.overflow;
	body.style.overflow = 'hidden';
	return () => {
		body.style.overflow = previous;
	};
}

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled])';

/** Keeps Tab and Shift+Tab inside the container: they wrap from the last to the first. */
export function keepFocusInside(event: KeyboardEvent, container: HTMLElement): void {
	if (event.key !== 'Tab') return;
	const focusable = [...container.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
		(el) => el.getAttribute('tabindex') !== '-1'
	);
	const first = focusable[0];
	const last = focusable[focusable.length - 1];
	if (!first || !last) return;
	const active = document.activeElement;
	if (event.shiftKey && active === first) {
		event.preventDefault();
		last.focus();
	} else if (!event.shiftKey && active === last) {
		event.preventDefault();
		first.focus();
	}
}
