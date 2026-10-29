<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import Kicker from '#lib/components/Kicker.svelte';
	import { tick } from 'svelte';
	import PlayerAvatar from '#lib/components/PlayerAvatar.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import type { PlayerCardView } from '#lib/cup/types.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		players: PlayerCardView[];
		index: number;
		layout: RowLayout;
		playerHref: (id: string) => ResolvedPathname;
		onIndex: (index: number) => void;
		onClose: () => void;
	};

	let { players, index, layout, playerHref, onIndex, onClose }: Props = $props();

	const NO_VALUE = '—';

	let closeButton = $state<HTMLButtonElement>();
	let prevButton = $state<HTMLButtonElement>();
	let nextButton = $state<HTMLButtonElement>();

	// A step button that turns disabled would drop focus to the page: hand it to the other one.
	async function stepBack() {
		onIndex(index - 1);
		if (index - 1 <= 0) {
			await tick();
			nextButton?.focus();
		}
	}

	async function stepForward() {
		onIndex(index + 1);
		if (index + 1 >= players.length - 1) {
			await tick();
			prevButton?.focus();
		}
	}

	// Opening is mounting: focus starts on Close.
	$effect(() => closeButton?.focus());

	const player = $derived(players[index]);
	const identity = $derived(
		player ? [player.number, player.position].filter((part) => part !== null).join(' · ') : ''
	);
	const stats = $derived(
		player
			? [
					{ label: m.box_points(), value: player.points },
					{ label: m.box_rebounds(), value: player.rebounds },
					{ label: m.box_assists(), value: player.assists }
				]
			: []
	);
	const facts = $derived(
		player
			? [
					{ label: m.player_profile_height(), value: player.height },
					{ label: m.player_profile_weight(), value: player.weight },
					{ label: m.team_roster_age(), value: player.age },
					{ label: m.cup_card_hometown(), value: player.hometown },
					{ label: m.team_roster_college(), value: player.college },
					{ label: m.cup_card_experience(), value: player.experience }
				]
			: []
	);
</script>

{#if player}
	<div class="card" class:mobile={layout === 'mobile'} role="dialog" aria-label={player.name}>
		<div class="top">
			<PlayerAvatar name={player.name} photo={player.photo} size="cup-card" />
			<button type="button" class="close" bind:this={closeButton} onclick={onClose}>
				{m.cup_close()}
			</button>
		</div>
		<h3 class="name">{player.name}</h3>
		<p class="line">{player.team}</p>
		{#if identity}<p class="line">{identity}</p>{/if}
		{#if player.injury}<span class="injury"><StatusTag injury={player.injury} /></span>{/if}
		<dl class="stats">
			{#each stats as stat (stat.label)}
				<div class="stat">
					<Kicker as="dt" tone="muted" text={stat.label} />
					<dd>{stat.value}</dd>
				</div>
			{/each}
		</dl>
		<dl class="facts">
			{#each facts as fact (fact.label)}
				<div class="fact">
					<Kicker as="dt" tone="muted" text={fact.label} />
					<dd>{fact.value ?? NO_VALUE}</dd>
				</div>
			{/each}
		</dl>
		<a class="page-link" href={playerHref(player.id)}>{m.cup_player_page()}</a>
		<div class="steps">
			<button
				type="button"
				class="step"
				bind:this={prevButton}
				disabled={index <= 0}
				onclick={stepBack}
			>
				{m.cup_player_prev()}
			</button>
			<button
				type="button"
				class="step"
				bind:this={nextButton}
				disabled={index >= players.length - 1}
				onclick={stepForward}
			>
				{m.cup_player_next()}
			</button>
		</div>
	</div>
{/if}

<style>
	.card {
		position: fixed;
		top: 0;
		bottom: 0;
		left: 0;
		z-index: var(--cup-panel-z-index);
		display: grid;
		align-content: start;
		gap: var(--day-strip-gap);
		box-sizing: border-box;
		width: var(--cup-card-width);
		max-width: 100%;
		padding: var(--game-list-gap);
		overflow-y: auto;
		border-right: var(--hairline) solid var(--color-divider);
		background: var(--search-panel-bg);
		color: var(--color-ink);
	}

	.card.mobile {
		right: 0;
		width: auto;
		border-right: 0;
	}

	.top {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: var(--game-list-gap);
	}

	.name {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--team-name-size);
		font-weight: var(--font-weight-semibold);
	}

	.line {
		margin: 0;
		font-size: var(--body-size);
		color: var(--color-muted);
	}

	.injury {
		justify-self: start;
	}

	.stats,
	.facts {
		display: grid;
		gap: var(--day-strip-gap);
		margin: 0;
	}

	.stats {
		grid-template-columns: repeat(3, 1fr);
	}

	.stat,
	.fact {
		display: grid;
		gap: var(--hairline);
	}

	.fact {
		grid-template-columns: 1fr 2fr;
		align-items: baseline;
	}

	dd {
		margin: 0;
		font-size: var(--body-size);
	}

	.stat dd {
		font-family: var(--font-heading);
		font-size: var(--score-size-mobile);
		font-variant-numeric: tabular-nums;
	}

	.page-link {
		display: inline-flex;
		align-items: center;
		min-height: var(--hit-target-size);
		font-size: var(--body-size);
		color: var(--color-accent-light);
	}

	.page-link:hover {
		color: var(--color-accent-hover);
	}

	.steps {
		display: flex;
		gap: var(--day-strip-gap);
	}

	.step,
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

	.step {
		flex: 1;
	}

	.step:hover:not(:disabled),
	.close:hover {
		border-color: var(--color-accent);
	}

	.step:disabled {
		opacity: var(--dimmed-opacity);
		cursor: default;
	}
</style>
