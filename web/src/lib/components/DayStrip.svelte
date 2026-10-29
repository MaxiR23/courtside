<script lang="ts" module>
	export const TODAY_INDEX = 3; // today is the middle cell
</script>

<script lang="ts">
	import Kicker from '#lib/components/Kicker.svelte';
	import { formatDate, formatNumber } from '#lib/format/locale.ts';
	import { m } from '#lib/paraglide/messages.js';

	type Props = {
		days: { date: Date; gameCount: number }[]; // seven days, today minus 3 to today plus 3
		selected: number; // 0 to 6
		compact: boolean; // mobile: counts as numbers only
		onSelect: (index: number) => void;
	};

	let { days, selected, compact, onSelect }: Props = $props();

	const weekday = (date: Date, i: number) =>
		i === TODAY_INDEX ? m.schedule_today() : formatDate(date, { weekday: 'short' });
	const dayNumber = (date: Date) => formatDate(date, { day: 'numeric' });
	const count = (n: number) => (compact ? formatNumber(n) : m.schedule_game_count({ count: n }));
</script>

<div class="day-strip">
	{#each days as day, i (i)}
		<button
			type="button"
			class="day"
			class:selected={i === selected}
			aria-current={i === selected ? 'true' : undefined}
			onclick={() => onSelect(i)}
		>
			<Kicker tone="inherit" contents
				><span class="weekday" class:today={i === TODAY_INDEX}>
					{weekday(day.date, i)}
				</span></Kicker
			>
			<span class="number">{dayNumber(day.date)}</span>
			<Kicker tone="muted" contents
				><span class="count">
					{count(day.gameCount)}
				</span></Kicker
			>
		</button>
	{/each}
</div>

<style>
	.day-strip {
		display: grid;
		grid-template-columns: repeat(7, minmax(0, 1fr));
		gap: var(--day-strip-gap);
	}

	.day {
		display: flex;
		flex-direction: column;
		align-items: center;
		min-height: var(--hit-target-size);
		padding: var(--day-strip-gap);
		background: none;
		border: var(--hairline) solid var(--color-divider);
		border-radius: var(--radius);
		font: inherit;
		color: inherit;
		cursor: pointer;
	}

	.day:hover {
		border-color: var(--color-accent);
	}

	.selected {
		border-color: var(--color-accent);
		background: var(--color-selected-day);
	}

	.today {
		color: var(--color-accent-light);
	}

	.number {
		font-family: var(--font-heading);
		font-size: var(--day-number-size);
	}
</style>
