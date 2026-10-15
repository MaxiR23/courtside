<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import { monthGrid } from '#lib/calendar/month.ts';
	import { formatDate } from '#lib/format/locale.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		month: string; // 'YYYY-MM'
		days: Set<string>; // the days with games
		today: string | null;
		selected: string | null;
		canPrevious: boolean;
		canNext: boolean;
		onPrevious: () => void;
		onNext: () => void;
		dayHref: (date: string) => ResolvedPathname;
		layout: RowLayout;
	};

	let {
		month,
		days,
		today,
		selected,
		canPrevious,
		canNext,
		onPrevious,
		onNext,
		dayHref,
		layout
	}: Props = $props();

	const grid = $derived(monthGrid(month));
	const weekdays = $derived(m.past_weekdays().split(' '));
	const utcDate = (isoDate: string) => new Date(`${isoDate}T00:00:00Z`);
	const monthName = $derived(
		formatDate(utcDate(`${month}-01`), { month: 'long', year: 'numeric', timeZone: 'UTC' })
	);
	const dayLabel = (isoDate: string) =>
		formatDate(utcDate(isoDate), {
			month: 'long',
			day: 'numeric',
			year: 'numeric',
			timeZone: 'UTC'
		});
</script>

<div class="month" class:mobile={layout === 'mobile'}>
	<div class="month-row">
		<button
			type="button"
			class="arrow"
			aria-label={m.past_month_prev()}
			disabled={!canPrevious}
			onclick={onPrevious}
		>
			<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M8 2 4 6l4 4" /></svg>
		</button>
		<h2 class="month-name">{monthName}</h2>
		<button
			type="button"
			class="arrow"
			aria-label={m.past_month_next()}
			disabled={!canNext}
			onclick={onNext}
		>
			<svg viewBox="0 0 12 12" aria-hidden="true"><path d="m4 2 4 4-4 4" /></svg>
		</button>
	</div>
	<div class="week weekdays" aria-hidden="true">
		{#each weekdays as weekday, i (i)}
			<span class="weekday">{weekday}</span>
		{/each}
	</div>
	{#each grid as week, w (w)}
		<div class="week">
			{#each week as date, d (d)}
				{#if date === null}
					<span class="day blank"></span>
				{:else if days.has(date)}
					<a
						class="day has-games"
						class:today={date === today}
						class:selected={date === selected}
						href={dayHref(date)}
						aria-label={dayLabel(date)}
						aria-current={date === selected ? 'date' : undefined}
					>
						{Number(date.slice(8))}
					</a>
				{:else}
					<span
						class="day off"
						class:today={date === today}
						class:selected={date === selected}
						aria-current={date === selected ? 'date' : undefined}
					>
						{Number(date.slice(8))}
					</span>
				{/if}
			{/each}
		</div>
	{/each}
</div>

<style>
	.month {
		display: grid;
		gap: var(--day-strip-gap);
	}

	.month-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--game-list-gap);
	}

	.month-name {
		margin: 0;
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--past-month-size);
		text-transform: uppercase;
	}

	.arrow {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: var(--past-arrow-size);
		height: var(--past-arrow-size);
		padding: 0;
		border: var(--hairline) solid var(--past-select-border);
		border-radius: var(--radius);
		background: none;
		color: var(--color-ink);
		cursor: pointer;
	}

	.arrow:hover:not(:disabled) {
		border-color: var(--color-accent);
	}

	.arrow:disabled {
		color: var(--past-day-off-ink);
		cursor: default;
	}

	svg {
		width: var(--past-chevron-size);
		height: var(--past-chevron-size);
		fill: none;
		stroke: currentColor;
		stroke-width: var(--icon-stroke-width);
		stroke-linecap: round;
		stroke-linejoin: round;
	}

	.week {
		display: grid;
		grid-template-columns: repeat(7, 1fr);
		justify-items: center;
	}

	.weekday {
		font-size: var(--past-weekday-size);
		letter-spacing: var(--past-weekday-letter-spacing);
		color: var(--color-muted);
	}

	.day {
		position: relative;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		box-sizing: border-box;
		width: var(--past-day-cell);
		height: var(--past-day-cell);
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--past-day-size);
		text-decoration: none;
	}

	.mobile .day {
		width: var(--past-day-cell-mobile);
		height: var(--past-day-cell-mobile);
	}

	.has-games {
		color: var(--color-ink);
	}

	.has-games::after {
		content: '';
		position: absolute;
		bottom: var(--hairline);
		width: var(--past-day-mark);
		height: var(--past-day-mark);
		background: var(--color-accent);
	}

	.has-games:hover {
		color: var(--color-accent-light);
	}

	.off {
		color: var(--past-day-off-ink);
	}

	.today {
		outline: var(--hairline) solid var(--color-accent-light);
	}

	.selected {
		background: var(--color-accent);
	}

	.selected,
	.selected:hover {
		color: var(--color-bg);
	}

	.selected.has-games::after {
		background: var(--color-bg);
	}
</style>
