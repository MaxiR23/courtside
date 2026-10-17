<script lang="ts">
	import { afterNavigate } from '$app/navigation';
	import CalendarSheet from '#lib/components/CalendarSheet.svelte';
	import type { DateCalendar } from '#lib/calendar/types.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		text: string; // the visible label: the date on the home, "Calendar" on the day page
		datetime: string | null; // 'YYYY-MM-DD'; set: the label is a <time>
		calendar: DateCalendar;
		layout: RowLayout;
	};

	let { text, datetime, calendar, layout }: Props = $props();

	let open = $state(false);
	let wrapper = $state<HTMLElement>();
	let button = $state<HTMLButtonElement>();

	// A navigation (a day link, the arrows) closes the sheet, as it closes the search.
	afterNavigate(() => {
		open = false;
	});

	function close() {
		open = false;
		button?.focus();
	}
</script>

<div class="date-button" bind:this={wrapper}>
	<button
		type="button"
		class="trigger"
		aria-label={m.past_calendar_open()}
		aria-haspopup="dialog"
		aria-expanded={open}
		bind:this={button}
		onclick={() => (open = !open)}
	>
		{#if datetime}
			<time {datetime}>{text}</time>
		{:else}
			<span>{text}</span>
		{/if}
		<svg viewBox="0 0 12 12" aria-hidden="true"><path d="m2 4 4 4 4-4" /></svg>
	</button>
	{#if open}
		<CalendarSheet {calendar} {layout} onClose={close} anchor={wrapper} />
	{/if}
</div>

<style>
	.date-button {
		position: relative;
		display: inline-flex;
	}

	.trigger {
		display: inline-flex;
		align-items: center;
		gap: var(--day-strip-gap);
		min-height: var(--hit-target-size);
		padding: 0;
		border: 0;
		background: none;
		font: inherit;
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		color: var(--color-muted);
		cursor: pointer;
	}

	.trigger:hover,
	.trigger[aria-expanded='true'] {
		color: var(--color-ink);
	}

	svg {
		flex: none;
		width: var(--past-chevron-size);
		height: var(--past-chevron-size);
		fill: none;
		stroke: currentColor;
		stroke-width: var(--icon-stroke-width);
		stroke-linecap: round;
		stroke-linejoin: round;
	}
</style>
