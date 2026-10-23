// The series selected in the playoffs bracket, and what a tap on a card does.
// SEE: docs/design-playoffs.md, Bracket, Interaction
import type { SeriesId } from '#lib/contract/playoffs.ts';
import type { RowLayout } from '#lib/schedule/types.ts';

type Listed = { id: SeriesId; games: unknown[] };
type Tappable = { id: SeriesId; complete: boolean; decided: 'both' | 'one' | 'none' };

export type TapResult = 'select' | 'open' | 'none';

export class SeriesSelection {
	picked = $state<SeriesId | null>(null); // the user's pick; null until the user picks

	/** The pick while the feed has it, else on the map the Finals once it has a game; on the tree only the pick. */
	current(series: Listed[], layout: RowLayout): SeriesId | null {
		const picked = this.picked;
		if (picked !== null && series.some((entry) => entry.id === picked)) return picked;
		if (layout !== 'desktop') return null;
		return series.some((entry) => entry.id === 'finals' && entry.games.length > 0)
			? 'finals'
			: null;
	}

	/**
	 * 'select' on a first tap or on an unfinished selected series, 'open' on a second tap of a
	 * complete selected series and 'none' for a series with an undecided side. Sets the pick on 'select'.
	 */
	tap(series: Tappable, current: SeriesId | null): TapResult {
		if (series.decided !== 'both') return 'none';
		if (current === series.id && series.complete) return 'open';
		this.picked = series.id;
		return 'select';
	}
}
