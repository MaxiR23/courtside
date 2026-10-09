<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { ScheduleRowView, ScheduleSection } from '#lib/team/types.ts';

	type Props = {
		schedule: ScheduleSection;
		layout: RowLayout;
		gameHref: (id: string) => ResolvedPathname;
	};

	let { schedule, layout, gameHref }: Props = $props();

	// Not kept between visits; a key the feed no longer has falls back to the feed's default.
	let selected = $state<string | null>(null);
	const current = $derived(
		schedule.groups.some((group) => group.key === selected) ? selected : schedule.defaultKey
	);
	const rows = $derived(schedule.groups.find((group) => group.key === current)?.rows ?? []);
</script>

{#snippet rowBody(row: ScheduleRowView)}
	<span class="date">
		<span class="weekday">{row.weekday}</span>
		<span class="day">{row.date}</span>
	</span>
	<span class="game">
		<span class="opponent"
			><TeamMark
				part="label"
				team={row.opponent.team}
				versus={row.opponent.isHome ? 'home' : 'away'}
			/></span
		>
		{#each row.tags as tag, i (i)}
			<StatusTag text={tag} accent={row.next && i === row.tags.length - 1} />
		{/each}
	</span>
	<span class="outcome">
		{#if row.outcome.kind === 'played'}
			<span class="result"
				><span class:win={row.outcome.result === 'win'}>{row.outcome.resultLabel}</span>
				{row.outcome.score ?? ''}</span
			>
			<span class="sub">{row.outcome.side}</span>
		{:else}
			<span class="result">{row.outcome.time}</span>
			{#if row.outcome.broadcast}<span class="sub">{row.outcome.broadcast}</span>{/if}
		{/if}
	</span>
{/snippet}

<div class="schedule">
	<div class="chips" role="group" aria-label={m.team_schedule_months()}>
		{#each schedule.groups as group (group.key)}
			<button
				type="button"
				class="chip"
				class:active={group.key === current}
				aria-pressed={group.key === current}
				onclick={() => (selected = group.key)}
			>
				{group.label}
			</button>
		{/each}
	</div>
	<ul class="rows" class:mobile={layout === 'mobile'}>
		{#each rows as row (row.gameId)}
			<li>
				{#if row.linked}
					<a class="row link" class:next={row.next} href={gameHref(row.gameId)}>
						{@render rowBody(row)}
					</a>
				{:else}
					<div class="row" class:next={row.next}>
						{@render rowBody(row)}
					</div>
				{/if}
			</li>
		{/each}
	</ul>
</div>

<style>
	.schedule {
		display: grid;
		gap: var(--game-list-gap);
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: var(--day-strip-gap);
	}

	.chip {
		min-width: var(--hit-target-size);
		min-height: var(--hit-target-size);
		padding: 0 var(--game-list-gap);
		border: var(--hairline) solid var(--color-divider);
		background: none;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
		cursor: pointer;
	}

	.chip.active {
		border-color: var(--color-accent);
		background: var(--color-selected-day);
		color: var(--color-ink);
	}

	.rows {
		display: grid;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.row {
		display: grid;
		grid-template-columns: var(--schedule-date-column) 1fr auto;
		align-items: center;
		gap: var(--game-list-gap);
		padding: var(--game-list-gap);
		border-bottom: var(--hairline) solid var(--color-row-rule);
		color: inherit;
		text-decoration: none;
	}

	.mobile .row {
		grid-template-columns: var(--schedule-date-column-mobile) 1fr auto;
	}

	.link:hover {
		background: var(--box-row-hover);
	}

	.next {
		background: var(--next-game-tint);
	}

	.date,
	.outcome {
		display: flex;
		flex-direction: column;
	}

	.outcome {
		align-items: flex-end;
		text-align: right;
	}

	.weekday,
	.sub {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.day {
		font-family: var(--font-heading);
		font-size: var(--body-size);
		white-space: nowrap;
	}

	.game {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--day-strip-gap);
		min-width: 0;
	}

	.opponent {
		font-family: var(--font-heading);
		font-size: var(--injury-name-size);
	}

	.result {
		font-family: var(--font-heading);
		font-size: var(--body-size);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.win {
		color: var(--color-accent-light);
	}
</style>
