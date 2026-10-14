// The text of a count-up: every run of digits counts from 0 to its value, every other
// character stays ("16-6", "+142", "−37"). Pure, so the hero's tween is the only reactive part.

/** The text with each run of digits scaled by the progress, 0 to 1; at 1 and beyond the text as it is. */
export function countText(text: string, progress: number): string {
	if (progress >= 1) return text;
	const p = Math.max(0, progress);
	return text.replace(/\d+/g, (digits) => String(Math.round(Number(digits) * p)));
}
