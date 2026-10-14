<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import SeriesGameLine from '#lib/components/SeriesGameLine.svelte';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { sheetSlide } from '#lib/playoffs/motion.ts';
	import type { SeriesCardView } from '#lib/playoffs/types.ts';
	import { keepFocusInside, lockBodyScroll } from '#lib/search/dialog.ts';

	type Props = {
		series: SeriesCardView;
		gameHref: (id: string) => ResolvedPathname;
		onClose: () => void;
	};

	let { series, gameHref, onClose }: Props = $props();

	let sheet = $state<HTMLElement>();
	let closeButton = $state<HTMLButtonElement>();

	// Opening is mounting: focus starts on Close, and the page does not scroll under the sheet.
	$effect(() => closeButton?.focus());
	$effect(() => lockBodyScroll(document.body));

	function onKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') onClose();
		else if (sheet) keepFocusInside(event, sheet);
	}
</script>

<svelte:window onkeydown={onKeydown} />

<!-- Esc and the Close button are the keyboard path to close. -->
<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="scrim" onclick={onClose}></div>
<div
	class="sheet"
	role="dialog"
	tabindex="-1"
	aria-modal="true"
	aria-label={series.roundTitle}
	bind:this={sheet}
	use:play={sheetSlide}
>
	<div class="bar">
		<h2 class="title">{series.roundTitle}</h2>
		<button type="button" class="close" bind:this={closeButton} onclick={onClose}>
			{m.playoffs_sheet_close()}
		</button>
	</div>
	<div class="sides">
		{#each [series.top, series.bottom] as side, i (i)}
			<p class="side" class:loser={side.loser}>
				{#if side.team}
					<span class="seed">{side.seed}</span>
					<span class="code">{side.label}</span>
					<span class="wins">{side.wins}</span>
				{:else}
					<span class="code">{side.label}</span>
					{#if side.note}<span class="note">{side.note}</span>{/if}
				{/if}
			</p>
		{/each}
		<p class="score">{series.score}</p>
	</div>
	<ol class="games">
		{#each series.games as game (game.key)}
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
</div>

<style>
	.scrim {
		position: fixed;
		inset: 0;
		z-index: var(--cup-panel-z-index);
		background: var(--playoffs-sheet-scrim);
	}

	.sheet {
		position: fixed;
		right: 0;
		bottom: 0;
		left: 0;
		z-index: var(--cup-panel-z-index);
		display: grid;
		align-content: start;
		gap: var(--game-list-gap);
		box-sizing: border-box;
		max-height: var(--playoffs-sheet-max-height);
		padding: var(--game-list-gap);
		overflow-y: auto;
		border-top: var(--hairline) solid var(--color-divider);
		background: var(--search-panel-bg);
		color: var(--color-ink);
	}

	.bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--game-list-gap);
	}

	.title {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--team-name-size);
		font-weight: var(--font-weight-semibold);
	}

	.close {
		min-height: var(--hit-target-size);
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

	.sides {
		display: grid;
		gap: var(--day-strip-gap);
	}

	.side {
		display: flex;
		align-items: baseline;
		gap: var(--day-strip-gap);
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--body-size);
	}

	.loser,
	.seed,
	.note {
		color: var(--color-muted);
	}

	.code {
		flex: 1;
	}

	.wins {
		font-variant-numeric: tabular-nums;
	}

	.score {
		margin: 0;
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.games {
		display: grid;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.game-row {
		display: flex;
		align-items: center;
		box-sizing: border-box;
		min-height: var(--playoffs-sheet-row);
		border-top: var(--hairline) solid var(--color-divider);
		color: var(--color-ink);
		font-size: var(--body-size-small);
		text-decoration: none;
	}

	.game-row.link:hover {
		color: var(--color-accent-light);
	}
</style>
