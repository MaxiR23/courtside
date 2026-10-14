// The game selected in the All-Star games section and the team tab of its box score.
// SEE: docs/design-all-star.md, Interactions and motion

type Selectable = { games: { id: string }[]; defaultGame: string | null };

export type BoxTab = 'away' | 'home';

export class GameSelection {
	selected = $state<string | null>(null); // the user's pick; null until the user picks
	tab = $state<BoxTab>('away');

	/** The picked game while the feed still has it, else the feed's default game. */
	current(view: Selectable): string | null {
		const picked = this.selected;
		if (picked !== null && view.games.some((game) => game.id === picked)) return picked;
		return view.defaultGame;
	}

	/** Selects a game; the box score goes back to the first team. */
	select(id: string): void {
		this.selected = id;
		this.tab = 'away';
	}

	showBox(side: BoxTab): void {
		this.tab = side;
	}
}
