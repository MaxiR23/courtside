const QUARTERS = 4;

export type PeriodColumn =
	{ kind: 'quarter'; number: number } | { kind: 'overtime'; number: number };

/** Four quarters, plus one column per overtime period either team has played. */
export function periodColumns(away: number[], home: number[]): PeriodColumn[] {
	const count = Math.max(QUARTERS, away.length, home.length);
	return Array.from({ length: count }, (_, i) =>
		i < QUARTERS
			? { kind: 'quarter', number: i + 1 }
			: { kind: 'overtime', number: i - QUARTERS + 1 }
	);
}

/** The points for each column, null for a period not played yet. */
export function periodCells(periods: number[], columns: number): (number | null)[] {
	for (const points of periods) {
		if (!Number.isInteger(points) || points < 0) throw new RangeError(`Invalid score: ${points}`);
	}
	return Array.from({ length: columns }, (_, i) => periods[i] ?? null);
}
