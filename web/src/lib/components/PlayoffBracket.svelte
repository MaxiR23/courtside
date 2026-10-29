<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import SectionHead from '#lib/components/SectionHead.svelte';
	import SeriesGameLine from '#lib/components/SeriesGameLine.svelte';
	import SeriesNode from '#lib/components/SeriesNode.svelte';
	import SeriesSheet from '#lib/components/SeriesSheet.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { SeriesId } from '#lib/contract/playoffs.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { BRACKET_GROUPS, treeSpan } from '#lib/playoffs/bracket-grid.ts';
	import { SeriesSelection } from '#lib/playoffs/selection.svelte.ts';
	import type { PlayoffBracketView, SeriesCardView } from '#lib/playoffs/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		bracket: PlayoffBracketView;
		layout: RowLayout; // desktop: the seven-column map; mobile: the tree
		gameHref: (id: string) => ResolvedPathname;
		seriesHref: (id: SeriesId) => ResolvedPathname;
		openSeries: (id: SeriesId) => void;
	};

	let { bracket, layout, gameHref, seriesHref, openSeries }: Props = $props();

	const selection = new SeriesSelection();

	let sheet = $state<SeriesId | null>(null);
	let opener: HTMLButtonElement | null = null;

	const byId = $derived(
		Object.fromEntries(bracket.series.map((series) => [series.id, series])) as Record<
			SeriesId,
			SeriesCardView
		>
	);
	const current = $derived(selection.current(bracket.series, layout));
	const result = $derived(layout === 'desktop' && current !== null ? byId[current] : undefined);
	const sheetSeries = $derived(layout === 'mobile' && sheet !== null ? byId[sheet] : undefined);
	const other = (series: SeriesCardView) => series[series.lead === 'top' ? 'bottom' : 'top'];

	function onTap(id: SeriesId, button: HTMLButtonElement) {
		const outcome = selection.tap(byId[id], current);
		if (outcome === 'open') openSeries(id);
		else if (outcome === 'select' && layout === 'mobile') {
			opener = button;
			sheet = id;
		}
	}

	function closeSheet() {
		sheet = null;
		opener?.focus({ preventScroll: true });
	}
</script>

<div class="bracket">
	<header class="head">
		<SectionHead
			kicker={bracket.kicker}
			title={m.playoffs_bracket()}
			titleSize="var(--playoffs-bracket-title-size)"
			kickerSize="var(--playoffs-bracket-kicker-size)"
			kickerGap="var(--day-strip-gap)"
		/>
		<p class="help">{m.playoffs_bracket_help()}</p>
	</header>

	{#if layout === 'desktop'}
		<div class="map" role="group" aria-label={m.playoffs_bracket()}>
			{#each BRACKET_GROUPS as group (group.key)}
				<section class="group">
					<h3 class="title" class:finals={group.finals}>{group.title()}</h3>
					<div class="cards">
						{#each group.ids as id (id)}
							{#if byId[id]}
								<SeriesNode series={byId[id]} {layout} selected={current === id} {onTap} />
							{/if}
						{/each}
					</div>
				</section>
			{/each}
		</div>
		{#if result}
			{@const lead = result[result.lead]}
			{@const rest = other(result)}
			<BlueprintFrame>
				<section class="result" aria-label={result.roundTitle}>
					<div class="top">
						{#if lead.team}
							<span class="lead-logo" aria-hidden="true">
								<TeamMark team={lead.team} part="tile" size="fill" logo={lead.team.logo} />
							</span>
						{/if}
						<div class="summary">
							<span class="round">{result.roundTitle}</span>
							<span class="headline">{result.headline}</span>
						</div>
						{#if rest.team}
							<span class="other-logo" aria-hidden="true">
								<TeamMark team={rest.team} part="tile" size="fill" logo={rest.team.logo} />
							</span>
						{/if}
						<a class="full" href={seriesHref(result.id)}>{m.playoffs_full_series()}</a>
					</div>
					<ol class="games">
						{#each result.games as game (game.key)}
							<li class="game">
								{#if game.linked}
									<a class="game-row link" href={gameHref(game.gameId)}>
										<SeriesGameLine {game} />
									</a>
								{:else}
									<div class="game-row">
										<SeriesGameLine {game} />
									</div>
								{/if}
							</li>
						{/each}
					</ol>
				</section>
			</BlueprintFrame>
		{/if}
	{:else}
		<div class="tree" role="group" aria-label={m.playoffs_bracket()}>
			{#each BRACKET_GROUPS as group (group.key)}
				<section class="row">
					<h3 class="label" class:finals={group.finals}>{group.title()}</h3>
					<div class="grid">
						{#each group.ids as id (id)}
							{#if byId[id]}
								<div class="slot" style:grid-column={treeSpan(id)}>
									<SeriesNode series={byId[id]} {layout} selected={current === id} {onTap} />
								</div>
							{/if}
						{/each}
					</div>
				</section>
			{/each}
		</div>
		{#if sheetSeries}
			<SeriesSheet series={sheetSeries} {gameHref} {seriesHref} onClose={closeSheet} />
		{/if}
	{/if}
</div>

<style>
	.bracket {
		display: grid;
		gap: var(--game-list-gap);
		min-width: 0;
	}

	.head {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-end;
		justify-content: space-between;
		gap: var(--game-list-gap);
	}

	.help {
		margin: 0;
		font-size: var(--playoffs-bracket-help-size);
		color: var(--color-muted);
	}

	.map {
		display: grid;
		grid-template-columns: var(--playoffs-bracket-columns);
		gap: var(--playoffs-bracket-gap);
	}

	.group {
		display: flex;
		flex-direction: column;
		gap: var(--day-strip-gap);
		min-width: 0;
	}

	.title,
	.label {
		margin: 0;
		font-size: var(--playoffs-col-title-size);
		font-weight: var(--font-weight-semibold);
		letter-spacing: var(--label-letter-spacing);
		text-align: center;
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.title {
		padding-bottom: var(--day-strip-gap);
		border-bottom: var(--hairline) solid var(--color-divider);
	}

	.title.finals,
	.label.finals {
		color: var(--color-accent-light);
	}

	.cards {
		display: flex;
		flex: 1;
		flex-direction: column;
		justify-content: space-around;
		gap: var(--playoffs-bracket-gap);
	}

	.tree {
		display: grid;
		gap: var(--game-list-gap);
	}

	.row {
		display: grid;
		gap: var(--playoffs-tree-gap);
		min-width: 0;
	}

	.label {
		font-size: var(--playoffs-tree-label-size);
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(8, minmax(0, 1fr));
		gap: var(--playoffs-tree-gap);
	}

	.slot {
		display: grid;
		min-width: 0;
	}

	.result {
		display: grid;
		gap: var(--game-list-gap);
		padding: var(--game-list-gap);
	}

	.top {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.lead-logo,
	.other-logo {
		display: block;
		flex: none;
	}

	.lead-logo {
		width: var(--playoffs-result-logo);
		height: var(--playoffs-result-logo);
	}

	.other-logo {
		width: var(--playoffs-result-other-logo);
		height: var(--playoffs-result-other-logo);
		opacity: var(--playoffs-result-other-opacity);
	}

	.summary {
		display: grid;
		gap: var(--hairline);
		min-width: 0;
	}

	.round {
		font-size: var(--playoffs-result-round-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.headline {
		font-family: var(--font-heading);
		font-size: var(--playoffs-result-headline-size);
		line-height: 1;
		text-transform: uppercase;
	}

	.full {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		margin-left: auto;
		min-height: var(--hit-target-size);
		padding: 0 var(--game-list-gap);
		background: var(--color-accent);
		color: var(--color-bg);
		font-family: var(--font-heading);
		font-size: var(--playoffs-result-button-size);
		letter-spacing: var(--label-letter-spacing);
		text-decoration: none;
		text-transform: uppercase;
	}

	.full:hover {
		background: var(--color-accent-light);
	}

	.games {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(var(--playoffs-games-min), 1fr));
		gap: var(--playoffs-games-gap);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.game {
		display: grid;
		min-width: 0;
	}

	.game-row {
		display: flex;
		align-items: stretch;
		box-sizing: border-box;
		min-width: 0;
		border: var(--hairline) solid var(--playoffs-card-border);
		color: var(--color-ink);
		text-decoration: none;
	}

	.game-row.link:hover {
		border-color: var(--color-accent);
	}
</style>
