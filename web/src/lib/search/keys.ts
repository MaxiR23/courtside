// Pure helpers for the search overlay's keyboard: the opening shortcuts and the active row.

const NON_TEXT_INPUTS = new Set([
	'checkbox',
	'radio',
	'button',
	'submit',
	'reset',
	'range',
	'color',
	'file',
	'image',
	'hidden'
]);

/** Whether typing goes into the target: a textarea, an editable element or a text-like input. */
export function isTextField(target: EventTarget | null): boolean {
	if (!(target instanceof HTMLElement)) return false;
	if (target instanceof HTMLTextAreaElement) return true;
	if (target.isContentEditable) return true;
	if (target instanceof HTMLInputElement) return !NON_TEXT_INPUTS.has(target.type);
	return false;
}

/** Ctrl or Cmd+K from anywhere; "/" with no modifier outside a text field. */
export function opensSearch(
	event: Pick<
		KeyboardEvent,
		'key' | 'metaKey' | 'ctrlKey' | 'altKey' | 'target' | 'isComposing' | 'defaultPrevented'
	>
): boolean {
	if (event.isComposing || event.defaultPrevented) return false;
	if (event.key.toLowerCase() === 'k' && (event.metaKey || event.ctrlKey) && !event.altKey) {
		return true;
	}
	return (
		event.key === '/' &&
		!event.metaKey &&
		!event.ctrlKey &&
		!event.altKey &&
		!isTextField(event.target)
	);
}

/** The next active row, wrapping at both ends. -1 when there are no rows. */
export function moveActive(current: number, direction: 1 | -1, count: number): number {
	if (count === 0) return -1;
	return (current + direction + count) % count;
}
