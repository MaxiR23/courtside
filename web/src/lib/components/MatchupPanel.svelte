<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import MatchupTeamBlock from '#lib/components/MatchupTeamBlock.svelte';
	import MessageRow from '#lib/components/MessageRow.svelte';
	import PlayerCard from '#lib/components/PlayerCard.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { MatchupPanelState, OpenCard } from '#lib/cup/types.ts';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import { keepFocusInside, lockBodyScroll } from '#lib/search/dialog.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';

	type Props = {
		state: MatchupPanelState;
		layout: RowLayout;
		gameHref: (id: string) => ResolvedPathname;
		playerHref: (id: string) => ResolvedPathname;
		card: OpenCard | null;
		onCard: (card: OpenCard | null) => void;
		onClose: () => void;
	};

	// `state` is renamed so the `$state` rune is not read as a store of the prop.
	let { state: page, layout, gameHref, playerHref, card, onCard, onClose }: Props = $props();

	const BONES = [0, 1, 2, 3];

	let panel = $state<HTMLElement>();
	let closeButton = $state<HTMLButtonElement>();
	let lastRow: HTMLElement | null = null;
	let cardWasOpen = false;

	const mobile = $derived(layout === 'mobile');

	// Opening is mounting: focus starts on Close.
	$effect(() => closeButton?.focus());

	// The sheet covers the page, so the page does not scroll under it.
	$effect(() => (mobile ? lockBodyScroll(document.body) : undefined));

	// Closing the card, from its button or Esc, returns the focus to the row that opened it.
	$effect(() => {
		const open = card !== null;
		if (!open && cardWasOpen) lastRow?.focus();
		cardWasOpen = open;
	});

	const label = $derived(
		page.kind === 'ready'
			? page.view.header.round
			: page.kind === 'loading'
				? m.cup_matchup_loading()
				: m.feed_unavailable()
	);
	const cardPlayers = $derived(
		page.kind === 'ready' && card ? page.view.sides[card.side].roster.map((p) => p.card) : []
	);

	const playerOpener = (side: number) => (index: number, row: HTMLElement) => {
		lastRow = row;
		onCard({ side: side === 0 ? 0 : 1, index });
	};

	const closeCard = () => onCard(null);

	function stepCard(index: number) {
		if (card) onCard({ side: card.side, index });
	}

	function onKeydown(event: KeyboardEvent) {
		if (mobile && panel) keepFocusInside(event, panel);
	}
</script>

<div
	class="panel"
	class:mobile
	role="dialog"
	tabindex="-1"
	aria-modal={mobile ? 'true' : undefined}
	aria-label={label}
	aria-busy={page.kind === 'loading' ? 'true' : undefined}
	bind:this={panel}
	onkeydown={onKeydown}
>
	<div class="bar">
		{#if page.kind === 'ready'}
			<h2 class="round">{page.view.header.round}</h2>
		{:else}
			<span></span>
		{/if}
		<button type="button" class="close" bind:this={closeButton} onclick={onClose}>
			{m.cup_close()}
		</button>
	</div>
	{#if page.kind === 'loading'}
		<div class="bones" aria-hidden="true" use:play={shimmer}>
			{#each BONES as i (i)}
				<span class="bone"></span>
			{/each}
		</div>
	{:else if page.kind === 'unavailable'}
		<MessageRow text={m.feed_unavailable()} />
	{:else}
		{@const view = page.view}
		<div class="facts">
			{#if view.header.date}<span>{view.header.date}</span>{/if}
			{#if view.header.venue}<span>{view.header.venue}</span>{/if}
			{#if view.header.broadcast}<span>{view.header.broadcast}</span>{/if}
			{#if view.header.neutral}<StatusTag text={m.cup_neutral()} />{/if}
			{#if view.header.gameLink?.linked}
				<a class="game-link" href={gameHref(view.header.gameLink.gameId)}>{m.cup_game_page()}</a>
			{/if}
		</div>
		<BlueprintFrame>
			<div class="teams">
				{#each view.sides as side, i (i)}
					<div class="team-line">
						{#if side.team}<TeamMark team={side.team} part="tile" size="small" />{/if}
						<span class="team-name">{side.name}</span>
						{#if side.score !== null}<span class="score">{side.score}</span>{/if}
					</div>
					{#if i === 0}
						<div class="status">
							{#if view.status.kind === 'final'}
								{view.status.text}
							{:else if view.status.kind === 'vs'}
								{m.cup_vs()}
							{:else}
								<StatusTag status={view.status.status} />
							{/if}
						</div>
					{/if}
				{/each}
			</div>
		</BlueprintFrame>
		{#each view.sides as side, i (i)}
			<MatchupTeamBlock {side} {gameHref} onPlayer={playerOpener(i)} />
		{/each}
		{#if view.note}<p class="note">{m.cup_final_note()}</p>{/if}
	{/if}
</div>

{#if card && cardPlayers.length > 0}
	<PlayerCard
		players={cardPlayers}
		index={card.index}
		{layout}
		{playerHref}
		onIndex={stepCard}
		onClose={closeCard}
	/>
{/if}

<style>
	.panel {
		position: fixed;
		top: 0;
		right: 0;
		bottom: 0;
		z-index: var(--cup-panel-z-index);
		display: grid;
		align-content: start;
		gap: var(--game-list-gap);
		box-sizing: border-box;
		width: var(--cup-panel-width);
		max-width: 100%;
		padding: var(--game-list-gap);
		overflow-y: auto;
		border-left: var(--hairline) solid var(--color-divider);
		background: var(--search-panel-bg);
		color: var(--color-ink);
	}

	.panel.mobile {
		left: 0;
		width: auto;
		border-left: 0;
	}

	.bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--game-list-gap);
	}

	.round {
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

	.facts {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--day-strip-gap) var(--game-list-gap);
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.game-link {
		color: var(--color-accent-light);
	}

	.game-link:hover {
		color: var(--color-accent-hover);
	}

	.teams {
		display: grid;
		gap: var(--day-strip-gap);
		padding: var(--game-list-gap);
	}

	.team-line {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.team-name {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		font-family: var(--font-heading);
		font-size: var(--team-name-size);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.score {
		font-family: var(--font-heading);
		font-size: var(--score-size-mobile);
		font-variant-numeric: tabular-nums;
	}

	.status {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.note {
		margin: 0;
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.bones {
		display: grid;
		gap: var(--game-list-gap);
	}

	.bone {
		display: block;
		height: var(--hit-target-size);
		background: var(--color-surface);
		border-radius: var(--radius);
	}
</style>
