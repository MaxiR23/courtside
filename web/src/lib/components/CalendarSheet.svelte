<script lang="ts">
	import { untrack } from 'svelte';
	import CalendarMonth from '#lib/components/CalendarMonth.svelte';
	import MessageRow from '#lib/components/MessageRow.svelte';
	import SeasonSelect from '#lib/components/SeasonSelect.svelte';
	import { calendarSheetSlide } from '#lib/calendar/motion.ts';
	import { CalendarSheetState } from '#lib/calendar/sheet.svelte.ts';
	import type { DateCalendar } from '#lib/calendar/types.ts';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import { keepFocusInside, lockBodyScroll } from '#lib/search/dialog.ts';

	type Props = {
		calendar: DateCalendar;
		layout: RowLayout;
		onClose: () => void;
		anchor?: HTMLElement; // desktop: a click inside it (the date button) does not close the panel
	};

	let { calendar, layout, onClose, anchor }: Props = $props();

	// The loader never changes while the sheet is open.
	const sheet = new CalendarSheetState(untrack(() => calendar.load));
	const season = $derived(calendar.season);
	const selectedDay = $derived(calendar.selectedDay);
	const mobile = $derived(layout === 'mobile');
	const days = $derived(new Set(sheet.feed?.days ?? []));

	let root = $state<HTMLElement>();
	let closeButton = $state<HTMLButtonElement>();
	let placed = false; // focus moves once, to the select or to Close when the load failed

	$effect(() => {
		void sheet.open(season, selectedDay);
	});

	$effect(() => {
		if (placed) return;
		if (sheet.feed) {
			root?.querySelector<HTMLElement>('select')?.focus();
			placed = true;
		} else if (sheet.failed) {
			closeButton?.focus();
			placed = true;
		}
	});

	$effect(() => {
		if (mobile) return lockBodyScroll(document.body);
	});

	function onKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') onClose();
		else if (mobile && root) keepFocusInside(event, root);
	}

	function onWindowClick(event: MouseEvent) {
		if (mobile) return;
		const target = event.target as Node;
		if (root?.contains(target) || anchor?.contains(target)) return;
		onClose();
	}
</script>

<svelte:window onkeydown={onKeydown} onclick={onWindowClick} />

{#snippet content()}
	<div class="bar">
		{#if sheet.feed}
			<SeasonSelect
				seasons={sheet.feed.seasons}
				value={sheet.feed.season}
				onChange={(next) => void sheet.changeSeason(String(next), selectedDay)}
			/>
		{/if}
		<button type="button" class="close" bind:this={closeButton} onclick={onClose}>
			{m.past_calendar_close()}
		</button>
	</div>
	{#if sheet.feed && sheet.month}
		<CalendarMonth
			month={sheet.month}
			{days}
			today={calendar.today}
			selected={selectedDay}
			canPrevious={sheet.canPrevious}
			canNext={sheet.canNext}
			onPrevious={() => sheet.previous()}
			onNext={() => sheet.next()}
			dayHref={calendar.dayHref}
			{layout}
		/>
	{:else if sheet.failed}
		<MessageRow text={m.feed_unavailable()} />
	{/if}
{/snippet}

{#if mobile}
	<!-- Esc and the Close button are the keyboard path to close. -->
	<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
	<div class="scrim" onclick={onClose}></div>
	<div
		class="sheet"
		role="dialog"
		tabindex="-1"
		aria-modal="true"
		aria-label={m.past_calendar_title()}
		bind:this={root}
		use:play={calendarSheetSlide}
	>
		{@render content()}
	</div>
{:else}
	<div
		class="panel"
		role="dialog"
		tabindex="-1"
		aria-label={m.past_calendar_title()}
		bind:this={root}
	>
		{@render content()}
	</div>
{/if}

<style>
	.scrim {
		position: fixed;
		inset: 0;
		z-index: var(--past-panel-z-index);
		background: var(--past-sheet-scrim);
	}

	.sheet,
	.panel {
		display: grid;
		align-content: start;
		gap: var(--game-list-gap);
		box-sizing: border-box;
		padding: var(--game-list-gap);
		border: var(--hairline) solid var(--color-divider);
		background: var(--color-surface);
		color: var(--color-ink);
		text-align: start;
	}

	.sheet {
		position: fixed;
		right: 0;
		bottom: 0;
		left: 0;
		z-index: var(--past-panel-z-index);
		max-height: var(--past-sheet-max-height);
		overflow-y: auto;
	}

	.panel {
		position: absolute;
		top: 100%;
		inset-inline-end: 0;
		z-index: var(--past-panel-z-index);
		width: var(--past-panel-width);
	}

	.bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--game-list-gap);
	}

	.close {
		min-height: var(--hit-target-size);
		margin-inline-start: auto;
		padding: 0 var(--game-list-gap);
		border: var(--hairline) solid var(--color-divider);
		border-radius: var(--radius);
		background: transparent;
		color: var(--color-ink);
		font: inherit;
		font-size: var(--body-size);
		cursor: pointer;
	}

	.close:hover {
		border-color: var(--color-accent);
	}
</style>
