import { clampedMonth, lastLinkedDay, monthsBetween, openingMonth } from '#lib/calendar/month.ts';
import type { CalendarFeed } from '#lib/contract/calendar.ts';

/**
 * The calendar sheet's state: the season's calendar feed, the month on show and whether the load
 * failed. The feed is loaded once per season and not polled. A load that answers after a newer
 * one started is dropped. With no loader (no URL configured) the sheet is failed at once. No month
 * after today's is offered: the last month is the earlier of the season's last day and today.
 */
export class CalendarSheetState {
	feed = $state.raw<CalendarFeed | null>(null);
	failed = $state(false);
	month = $state<string | null>(null);

	readonly #load: ((season: string) => Promise<CalendarFeed>) | undefined;
	readonly #today: string; // 'YYYY-MM-DD'
	#run = 0; // changes on every load, to drop the answer of an old one

	constructor(load: ((season: string) => Promise<CalendarFeed>) | undefined, today: string) {
		this.#load = load;
		this.#today = today;
	}

	get months(): string[] {
		return this.feed ? monthsBetween(this.feed.firstDay, this.#lastDay(this.feed)) : [];
	}

	get canPrevious(): boolean {
		const months = this.months;
		return this.month !== null && months.length > 0 && this.month > months[0];
	}

	get canNext(): boolean {
		const months = this.months;
		return this.month !== null && months.length > 0 && this.month < months[months.length - 1];
	}

	previous(): void {
		if (!this.canPrevious) return;
		this.month = this.months[this.months.indexOf(this.month as string) - 1];
	}

	next(): void {
		if (!this.canNext) return;
		this.month = this.months[this.months.indexOf(this.month as string) + 1];
	}

	/** Loads the season and shows the selected day's month, clamped to the season's months. */
	open(season: string, selected: string | null): Promise<void> {
		return this.#show(season, (feed) => clampedMonth(selected, feed.firstDay, this.#lastDay(feed)));
	}

	/** Loads another season and shows the selected day's month when it is in it, else its first. */
	changeSeason(season: string, selected: string | null): Promise<void> {
		return this.#show(season, (feed) => openingMonth(selected, feed.firstDay, this.#lastDay(feed)));
	}

	#lastDay(feed: CalendarFeed): string {
		return lastLinkedDay(feed.firstDay, feed.lastDay, this.#today);
	}

	async #show(season: string, monthOf: (feed: CalendarFeed) => string): Promise<void> {
		const run = ++this.#run;
		if (!this.#load) {
			this.#fail();
			return;
		}
		try {
			const feed = await this.#load(season);
			if (run !== this.#run) return;
			this.feed = feed;
			this.failed = false;
			this.month = monthOf(feed);
		} catch {
			if (run !== this.#run) return;
			this.#fail();
		}
	}

	#fail(): void {
		this.feed = null;
		this.month = null;
		this.failed = true;
	}
}
