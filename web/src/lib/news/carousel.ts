/**
 * The card a carousel shows first: the scroll offset over the step between cards, kept inside the
 * cards. At the end of the track (maxScroll is the most the track can scroll) it is the last card,
 * since a wide screen never scrolls far enough to round to it.
 */
export function carouselIndex(
	scrollLeft: number,
	step: number,
	count: number,
	maxScroll = 0
): number {
	if (step <= 0 || count <= 0) return 0;
	if (maxScroll > 0 && scrollLeft >= maxScroll - 1) return count - 1;
	return Math.min(Math.max(Math.round(scrollLeft / step), 0), count - 1);
}
