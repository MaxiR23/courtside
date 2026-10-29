<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import SeriesGameLine from '#lib/components/SeriesGameLine.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { SeriesId } from '#lib/contract/playoffs.ts';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { sheetSlide } from '#lib/playoffs/motion.ts';
	import type { SeriesCardView } from '#lib/playoffs/types.ts';
	import { keepFocusInside, lockBodyScroll } from '#lib/search/dialog.ts';
	import Kicker from '#lib/components/Kicker.svelte';

	type Props = {
		series: SeriesCardView;
		gameHref: (id: string) => ResolvedPathname;
		seriesHref: (id: SeriesId) => ResolvedPathname;
		onClose: () => void;
	};

	let { series, gameHref, seriesHref, onClose }: Props = $props();

	let sheet = $state<HTMLElement>();
	let closeButton = $state<HTMLButtonElement>();

	// Opening is mounting: focus starts on Close, and the page does not scroll under the sheet.
	$effect(() => closeButton?.focus());
	$effect(() => lockBodyScroll(document.body));

	function onKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') onClose();
		else if (sheet) keepFocusInside(event, sheet);
	}

	const lead = $derived(series[series.lead]);
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
		{#if lead.team}
			<span class="logo" aria-hidden="true">
				<TeamMark team={lead.team} part="tile" size="fill" logo={lead.team.logo} />
			</span>
		{/if}
		<div class="titles">
			<Kicker tone="muted" contents><span class="round">{series.roundTitle}</span></Kicker>
			<h2 class="headline">{series.headline}</h2>
		</div>
		<button type="button" class="close" bind:this={closeButton} onclick={onClose}>
			{m.playoffs_sheet_close()}
		</button>
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
	<a class="full" href={seriesHref(series.id)}>{m.playoffs_full_series()}</a>
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
		border-top: var(--hairline) solid var(--color-accent);
		background: var(--playoffs-sheet-bg);
		color: var(--color-ink);
	}

	.bar {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.logo {
		display: block;
		flex: none;
		width: var(--playoffs-sheet-logo);
		height: var(--playoffs-sheet-logo);
	}

	.titles {
		display: grid;
		flex: 1;
		gap: var(--hairline);
		min-width: 0;
	}

	.headline {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--playoffs-sheet-headline-size);
		font-weight: var(--font-weight-semibold);
		line-height: 1;
		text-transform: uppercase;
	}

	.close {
		flex: none;
		min-width: var(--playoffs-sheet-close-size);
		min-height: var(--playoffs-sheet-close-size);
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

	.games {
		display: grid;
		grid-template-columns: repeat(var(--playoffs-sheet-games-columns), minmax(0, 1fr));
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

	.full {
		display: flex;
		align-items: center;
		justify-content: center;
		box-sizing: border-box;
		min-height: var(--playoffs-sheet-button-height);
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
</style>
