<script lang="ts">
	// The power ranking section of the standings page: a header, a table on desktop, expandable
	// rows on mobile, the top 10 by default with a toggle for all the teams.
	// SEE: docs/design-standings-search.md, Power ranking
	import Kicker from '#lib/components/Kicker.svelte';
	import SectionHead from '#lib/components/SectionHead.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import { TOP_ROWS } from '#lib/feed/power-ranking-props.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { PowerRankingView } from '#lib/standings/types.ts';

	type Props = {
		view: PowerRankingView;
		layout: RowLayout;
	};

	let { view, layout }: Props = $props();

	const uid = $props.id();
	const detailsId = (code: string) => `${uid}-${code}`;

	let expanded = $state(false);
	let openCode = $state<string | null>(null);
	const rows = $derived(expanded ? view.teams : view.teams.slice(0, TOP_ROWS));

	const columns: (() => string)[] = [
		m.power_ranking_col_team,
		m.power_ranking_col_record,
		m.power_ranking_col_rating,
		m.power_ranking_col_offense,
		m.power_ranking_col_defense,
		m.power_ranking_col_projected,
		m.power_ranking_col_playoffs,
		m.power_ranking_col_title
	];

	function toggleAll() {
		expanded = !expanded;
		if (!expanded) openCode = null;
	}

	function toggleRow(code: string) {
		openCode = openCode === code ? null : code;
	}
</script>

<section class="power-ranking" aria-label={m.power_ranking_title()}>
	<Kicker text={m.power_ranking_kicker()} />
	<SectionHead title={m.power_ranking_title()} meta={m.power_ranking_note()} />

	{#if layout === 'desktop'}
		<div class="scroll">
			<div class="table" role="table">
				<Kicker as="div" tone="muted" contents
					><div class="row head" role="row">
						<span class="cell" role="columnheader">#</span>
						{#each columns as label, i (i)}
							<span class="cell" role="columnheader">{label()}</span>
						{/each}
					</div></Kicker
				>
				{#each rows as row (row.code)}
					<div class="row body" role="row">
						<span class="cell rank" class:tied={row.tied} role="cell">{row.rank}</span>
						<span class="cell team" role="rowheader">
							<TeamMark team={row.team} part="tile" size="standings" logo={row.team.logo} />
							<TeamMark team={row.team} part="name" />
							{#if row.team.city}<span class="city">{row.team.city}</span>{/if}
						</span>
						<span class="cell" role="cell">{row.record}</span>
						<span class="cell rating" class:muted={row.ratingMuted} role="cell">{row.rating}</span>
						<span class="cell" role="cell">{row.offense}</span>
						<span class="cell" role="cell">{row.defense}</span>
						<span class="cell" role="cell">{row.projected}</span>
						<span class="cell playoffs" class:muted={row.playoffsMuted} role="cell"
							>{row.playoffs}</span
						>
						<span class="cell title" role="cell">
							<span class="track" aria-hidden="true"
								><span class="bar" style:--share={row.titleShare}></span></span
							>
							{row.title}
						</span>
					</div>
				{/each}
			</div>
		</div>
	{:else}
		<Kicker as="div" tone="muted" contents
			><div class="labels" aria-hidden="true">
				<span class="label-team">{m.power_ranking_col_team()}</span>
				<span class="label-value">{m.power_ranking_col_wl()}</span>
				<span class="label-value">{m.power_ranking_col_title_chance()}</span>
			</div></Kicker
		>
		<ul class="list">
			{#each rows as row (row.code)}
				{@const open = openCode === row.code}
				<li class="item" class:open>
					<button
						type="button"
						class="summary"
						aria-expanded={open}
						aria-controls={detailsId(row.code)}
						onclick={() => toggleRow(row.code)}
					>
						<span class="rank" class:tied={row.tied}>{row.rank}</span>
						<span class="team">
							<TeamMark team={row.team} part="tile" size="small" logo={row.team.logo} />
							<TeamMark team={row.team} part="name" />
						</span>
						<span class="record">{row.record}</span>
						<span class="title-text">{row.title}</span>
						<svg class="chevron" viewBox="0 0 24 24" aria-hidden="true"
							><path d="m6 9 6 6 6-6" /></svg
						>
					</button>
					{#if open}
						<dl
							id={detailsId(row.code)}
							class="details"
							aria-label={m.power_ranking_details({ team: row.team.name ?? row.code })}
						>
							<div class="pair">
								<dt>{m.power_ranking_col_rating()}</dt>
								<dd class:muted={row.ratingMuted}>{row.rating}</dd>
							</div>
							<div class="pair">
								<dt>{m.power_ranking_col_projected()}</dt>
								<dd>{row.projected}</dd>
							</div>
							<div class="pair">
								<dt>{m.power_ranking_col_playoffs()}</dt>
								<dd class:muted={row.playoffsMuted}>{row.playoffs}</dd>
							</div>
							<div class="pair">
								<dt>{m.power_ranking_off_def()}</dt>
								<dd>{row.offense} / {row.defense}</dd>
							</div>
						</dl>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}

	{#if view.teams.length > TOP_ROWS}
		<button type="button" class="chip toggle" aria-expanded={expanded} onclick={toggleAll}>
			{expanded ? view.showTopLabel : view.showAllLabel}
		</button>
	{/if}
</section>

<style>
	.power-ranking {
		display: grid;
		gap: var(--game-list-gap);
		align-content: start;
	}

	.scroll {
		overflow-x: auto;
	}

	.table {
		font-variant-numeric: tabular-nums;
	}

	.row {
		display: grid;
		grid-template-columns:
			minmax(var(--box-column-min), 1fr)
			minmax(var(--standings-team-column-page-min), 4fr)
			repeat(6, minmax(var(--box-column-min), 1fr))
			minmax(max-content, 1fr);
		align-items: center;
		border-bottom: var(--hairline) solid var(--color-row-rule);
	}

	.cell {
		padding: var(--day-strip-gap);
		text-align: left;
		white-space: nowrap;
	}

	.body:hover {
		background: var(--box-row-hover);
	}

	.cell.team {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
		min-width: 0;
	}

	.rank {
		color: var(--color-muted);
	}

	.tied {
		color: var(--color-ink);
	}

	.muted,
	.city {
		color: var(--color-muted);
	}

	.city {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.cell.title {
		display: flex;
		align-items: center;
		gap: var(--day-strip-gap);
	}

	.track {
		display: inline-block;
		flex-shrink: 0;
		width: var(--power-ranking-bar-width);
		height: var(--stat-bar-height);
		background: var(--color-bar-neutral);
	}

	.bar {
		display: block;
		height: 100%;
		width: calc(var(--share) * 100%);
		background: var(--color-accent);
	}

	.labels {
		display: grid;
		grid-template-columns:
			auto minmax(0, 1fr) var(--power-ranking-record-width)
			var(--power-ranking-title-width) var(--chevron-size);
		gap: var(--game-list-gap);
	}

	.label-team {
		grid-column: 1 / 3;
	}

	.label-value,
	.record,
	.title-text {
		text-align: right;
	}

	.list {
		display: grid;
		margin: 0;
		padding: 0;
		list-style: none;
		font-variant-numeric: tabular-nums;
	}

	.item {
		border-bottom: var(--hairline) solid var(--color-row-rule);
	}

	.summary {
		display: grid;
		grid-template-columns:
			auto minmax(0, 1fr) var(--power-ranking-record-width)
			var(--power-ranking-title-width) var(--chevron-size);
		align-items: center;
		gap: var(--game-list-gap);
		width: 100%;
		min-height: var(--hit-target-size);
		padding: 0;
		border: 0;
		background: none;
		font: inherit;
		text-align: left;
		color: inherit;
		cursor: pointer;
	}

	.summary:focus-visible,
	.toggle:focus-visible {
		outline: var(--focus-ring-width) solid var(--color-accent);
		outline-offset: var(--focus-ring-offset);
	}

	.summary .team {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
		min-width: 0;
	}

	.details {
		display: grid;
		gap: var(--day-strip-gap);
		margin: 0;
		padding: var(--day-strip-gap) 0 var(--game-list-gap);
	}

	.pair {
		display: flex;
		justify-content: space-between;
	}

	.pair dt {
		color: var(--color-muted);
	}

	.pair dd {
		margin: 0;
	}

	.chevron {
		width: var(--chevron-size);
		height: var(--chevron-size);
		fill: none;
		stroke: currentColor;
		stroke-width: var(--icon-stroke-width);
		stroke-linecap: round;
		stroke-linejoin: round;
	}

	.open .chevron {
		rotate: var(--chevron-open-rotation);
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

	.toggle {
		justify-self: start;
	}
</style>
