export type Side = 'away' | 'home';

function check(...values: number[]): void {
	for (const value of values) {
		if (!Number.isFinite(value) || value < 0) throw new RangeError(`Invalid stat value: ${value}`);
	}
}

/** The side that leads a stat; for lower-is-better stats (turnovers) the lower value leads. A tie leads no side. */
export function leadingSide(away: number, home: number, lowerIsBetter: boolean): Side | null {
	check(away, home);
	if (away === home) return null;
	return away < home === lowerIsBetter ? 'away' : 'home';
}

/** Each bar's share of its half: value / max(away, home); both 0 when both values are 0. */
export function barShares(away: number, home: number): { away: number; home: number } {
	check(away, home);
	const max = Math.max(away, home);
	if (max === 0) return { away: 0, home: 0 };
	return { away: away / max, home: home / max };
}
