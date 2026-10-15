<script lang="ts">
	import { m } from '#lib/paraglide/messages.js';

	type Props = {
		seasons: { season: number; seasonLabel: string }[]; // newest first
		value: number; // the end year on show
		onChange: (season: number) => void;
		full?: boolean; // full width, with a hit target (the mobile header)
	};

	let { seasons, value, onChange, full = false }: Props = $props();
</script>

<select
	class="select"
	class:full
	aria-label={m.past_season_select()}
	{value}
	onchange={(event) => onChange(Number(event.currentTarget.value))}
>
	{#each seasons as item (item.season)}
		<option value={item.season}>{item.seasonLabel}</option>
	{/each}
</select>

<style>
	.select {
		height: var(--past-select-height);
		padding: 0 var(--game-list-gap);
		border: var(--hairline) solid var(--past-select-border);
		border-radius: var(--radius);
		background: var(--color-surface);
		color: var(--color-ink);
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--past-select-size);
		letter-spacing: var(--past-select-letter-spacing);
		text-transform: uppercase;
		cursor: pointer;
	}

	.full {
		width: 100%;
		height: var(--hit-target-size);
	}

	.select:hover {
		border-color: var(--color-accent);
	}
</style>
