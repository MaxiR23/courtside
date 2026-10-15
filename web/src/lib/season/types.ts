/** One season of the selector: the end year and the label the calendar feed gives it. */
export type SeasonOption = { season: number; seasonLabel: string };

/** What `SeasonSelect` takes: the seasons, the one on show and the change handler. */
export type SeasonControl = {
	seasons: SeasonOption[];
	value: number;
	onChange: (season: number) => void;
};
