import type { CalendarFeed } from '#lib/contract/calendar.ts';
import type { DayFeed } from '#lib/contract/days.ts';
import { FeedLoadError } from '#lib/feed/load.ts';

/**
 * The day page's loads, each made once and never polled (ADR 0042): the day feed, then the
 * calendar of the day's season for the arrows and the sheet. A 404 for a date the games feed
 * shows is not an error: the home has that day, so `onWindowDay` gets the date and sends the page there. Any other
 * failure is unavailable. Every start goes back to loading and drops the old day and calendar. An answer that arrives after the cleanup is dropped.
 */
export class DayLoader {
	kind = $state<'loading' | 'ready' | 'unavailable'>('loading');
	feed = $state.raw<DayFeed | null>(null);
	calendar = $state.raw<CalendarFeed | null>(null);
	calendarFailed = $state(false);

	readonly #loadDay: () => Promise<DayFeed>;
	readonly #loadWindow: (() => Promise<string[]>) | undefined;
	readonly #loadCalendar: ((season: string) => Promise<CalendarFeed>) | undefined;
	readonly #onWindowDay: (date: string) => void;
	#run = 0; // changes on every start and every cleanup, to drop the answer of an old load

	constructor(
		loadDay: () => Promise<DayFeed>,
		loadWindow: (() => Promise<string[]>) | undefined,
		loadCalendar: ((season: string) => Promise<CalendarFeed>) | undefined,
		onWindowDay: (date: string) => void
	) {
		this.#loadDay = loadDay;
		this.#loadWindow = loadWindow;
		this.#loadCalendar = loadCalendar;
		this.#onWindowDay = onWindowDay;
	}

	/** Loads the day for `date` once. Call from $effect, in the browser only. Returns the cleanup. */
	start(date: string): () => void {
		this.kind = 'loading';
		this.feed = null;
		this.calendar = null;
		this.calendarFailed = false;
		const run = ++this.#run;
		void this.#load(date, run);
		return () => {
			this.#run++;
		};
	}

	async #load(date: string, run: number): Promise<void> {
		let feed: DayFeed;
		try {
			feed = await this.#loadDay();
		} catch (error) {
			if (run !== this.#run) return;
			if (error instanceof FeedLoadError && error.reason === 'not-found' && this.#loadWindow) {
				await this.#checkWindow(date, run, this.#loadWindow);
			} else {
				this.kind = 'unavailable';
			}
			return;
		}
		if (run !== this.#run) return;
		this.feed = feed;
		this.kind = 'ready';
		await this.#loadSeason(String(feed.season), run);
	}

	async #checkWindow(date: string, run: number, loadWindow: () => Promise<string[]>) {
		try {
			const dates = await loadWindow();
			if (run !== this.#run) return;
			if (dates.includes(date)) this.#onWindowDay(date);
			else this.kind = 'unavailable';
		} catch {
			if (run !== this.#run) return;
			this.kind = 'unavailable';
		}
	}

	async #loadSeason(season: string, run: number): Promise<void> {
		if (!this.#loadCalendar) {
			this.calendarFailed = true;
			return;
		}
		try {
			const calendar = await this.#loadCalendar(season);
			if (run !== this.#run) return;
			this.calendar = calendar;
		} catch {
			if (run !== this.#run) return;
			this.calendarFailed = true;
		}
	}
}
