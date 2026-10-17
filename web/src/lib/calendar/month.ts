// Pure helpers for the calendar sheet and the day page: the month layout and the lookups of
// the dates of a season. Dates are 'YYYY-MM-DD' strings and months 'YYYY-MM'; the arithmetic
// uses UTC dates so no time zone shifts a day.

const TIME_ZONE = 'America/New_York';

/** The 'YYYY-MM' month of a 'YYYY-MM-DD' date. */
export function monthOf(date: string): string {
	return date.slice(0, 7);
}

/** Every 'YYYY-MM' month from the month of `firstDay` to the month of `lastDay`, inclusive. */
export function monthsBetween(firstDay: string, lastDay: string): string[] {
	const [firstYear, firstMonth] = monthOf(firstDay).split('-').map(Number);
	const [lastYear, lastMonth] = monthOf(lastDay).split('-').map(Number);
	const months: string[] = [];
	let year = firstYear;
	let month = firstMonth;
	while (year < lastYear || (year === lastYear && month <= lastMonth)) {
		months.push(`${year}-${String(month).padStart(2, '0')}`);
		month += 1;
		if (month > 12) {
			month = 1;
			year += 1;
		}
	}
	return months;
}

/** The weeks of a month, Sunday first, 7 cells each: a date, or null for the padding. */
export function monthGrid(month: string): (string | null)[][] {
	const [year, monthNumber] = month.split('-').map(Number);
	const offset = new Date(Date.UTC(year, monthNumber - 1, 1)).getUTCDay();
	const length = new Date(Date.UTC(year, monthNumber, 0)).getUTCDate();
	const cells: (string | null)[] = Array.from({ length: offset }, () => null);
	for (let day = 1; day <= length; day += 1) cells.push(`${month}-${String(day).padStart(2, '0')}`);
	while (cells.length % 7 !== 0) cells.push(null);
	const weeks: (string | null)[][] = [];
	for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));
	return weeks;
}

/** The month a season opens on: the selected day's month when it is in the season, else the first. */
export function openingMonth(selected: string | null, firstDay: string, lastDay: string): string {
	if (selected !== null && selected >= firstDay && selected <= lastDay) return monthOf(selected);
	return monthOf(firstDay);
}

/** The selected day's month, clamped to the first or last month of the season. */
export function clampedMonth(selected: string | null, firstDay: string, lastDay: string): string {
	const first = monthOf(firstDay);
	const last = monthOf(lastDay);
	if (selected === null) return last;
	const month = monthOf(selected);
	if (month < first) return first;
	if (month > last) return last;
	return month;
}

/** The last day before the date and the first day after it, in a sorted list of dates. */
export function neighbours(
	days: readonly string[],
	date: string
): { previous: string | null; next: string | null } {
	let previous: string | null = null;
	let next: string | null = null;
	for (const day of days) {
		if (day < date) previous = day;
		else if (day > date) {
			next = day;
			break;
		}
	}
	return { previous, next };
}

/** The last day a calendar links: the earlier of the season's last day and today, never before the first day. */
export function lastLinkedDay(firstDay: string, lastDay: string, today: string): string {
	const last = today < lastDay ? today : lastDay;
	return last < firstDay ? firstDay : last;
}

/**
 * Whether a day is on the home: one of the games feed's days when that feed is loaded, else one
 * of the calendar feed's window days.
 */
export function isWindowDay(
	date: string,
	gamesDays: readonly string[] | null,
	windowDays: readonly string[]
): boolean {
	return (gamesDays ?? windowDays).includes(date);
}

/** The US Eastern date of an instant, as 'YYYY-MM-DD'. */
export function easternToday(now: Date): string {
	return new Intl.DateTimeFormat('en-CA', {
		timeZone: TIME_ZONE,
		year: 'numeric',
		month: '2-digit',
		day: '2-digit'
	}).format(now);
}
