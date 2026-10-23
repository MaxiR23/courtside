<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { PlayInSlotView, PlayInView } from '#lib/playoffs/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		playIn: PlayInView[];
		collapsed: boolean; // round 1 has started: only the titles and the notes
		layout: RowLayout;
		teamHref: (code: string) => ResolvedPathname;
		gameHref: (id: string) => ResolvedPathname;
	};

	let { playIn, collapsed, layout, teamHref, gameHref }: Props = $props();
</script>

{#snippet slotRow(side: PlayInSlotView, score: string | null)}
	<div class="slot" class:undecided={side.team === null} class:loser={side.loser}>
		{#if side.team}
			<span class="logo">
				<TeamMark team={side.team} part="tile" size="fill" logo={side.team.logo} {teamHref} />
			</span>
			<span class="slot-name">{side.label}</span>
		{:else}
			<span class="slot-text">
				<span class="slot-name">{side.label}</span>
				{#if side.place}<span class="place">{side.place}</span>{/if}
				{#if side.currently}<span class="place">{side.currently}</span>{/if}
			</span>
		{/if}
		{#if score !== null}<span class="score">{score}</span>{/if}
	</div>
{/snippet}

<div class="play-in" class:mobile={layout === 'mobile'}>
	<h3>{m.playoffs_playin_heading()}</h3>
	<div class="strip">
		{#each playIn as card (card.key)}
			<div class="conference">
				<span class="label">{card.title}</span>
				<ul class="games">
					{#each card.games as game (game.key)}
						<li class="game" class:collapsed>
							<span class="game-title">{game.title}</span>
							{#if !collapsed}
								{@render slotRow(game.top, game.score?.top ?? null)}
								{@render slotRow(game.bottom, game.score?.bottom ?? null)}
								{#if game.when}<span class="when">{game.when}</span>{/if}
							{/if}
							{#each game.notes as note (note.text)}
								<span class="note" class:seed={note.kind === 'seed'}>{note.text}</span>
							{/each}
							{#if !collapsed && game.linked}
								<a class="game-link" href={gameHref(game.gameId)}>{m.playoffs_game_page()}</a>
							{/if}
						</li>
					{/each}
				</ul>
			</div>
		{/each}
	</div>
</div>

<style>
	.play-in {
		display: grid;
		gap: var(--game-list-gap);
		min-width: 0;
	}

	h3 {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
	}

	.strip {
		display: grid;
		grid-template-columns: repeat(
			auto-fit,
			minmax(min(100%, var(--playoffs-playin-column-min)), 1fr)
		);
		gap: var(--panel-section-gap);
	}

	.conference {
		display: grid;
		gap: var(--game-list-gap);
		align-content: start;
		min-width: 0;
	}

	.label {
		font-size: var(--playoffs-col-title-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.games {
		display: grid;
		gap: var(--playoffs-games-gap);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.game {
		display: grid;
		gap: var(--day-strip-gap);
		padding: var(--playoffs-card-padding);
		border: var(--hairline) solid var(--playoffs-card-border);
		background: var(--playoffs-card-bg);
	}

	.game-title {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.slot {
		display: flex;
		align-items: center;
		gap: var(--identity-inline-mark-gap);
		min-height: var(--playoffs-card-logo);
	}

	.loser {
		opacity: var(--playoffs-loser-opacity);
	}

	.logo {
		display: block;
		flex: none;
		width: var(--playoffs-card-logo);
		height: var(--playoffs-card-logo);
	}

	.slot-text {
		display: grid;
		min-width: 0;
	}

	.slot-name {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-family: var(--font-heading);
		font-size: var(--playoffs-card-code-size);
	}

	.undecided .slot-name {
		color: var(--color-muted);
	}

	.place {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.score {
		margin-left: auto;
		font-family: var(--font-heading);
		font-size: var(--playoffs-card-code-size);
		font-variant-numeric: tabular-nums;
	}

	.when {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.note {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.note.seed {
		color: var(--color-accent-light);
	}

	.collapsed {
		gap: var(--hairline);
	}

	.game-link {
		display: inline-flex;
		align-items: center;
		min-height: var(--hit-target-size);
		font-size: var(--body-size-small);
		color: var(--color-accent-light);
	}

	.game-link:hover {
		color: var(--color-accent-hover);
	}
</style>
