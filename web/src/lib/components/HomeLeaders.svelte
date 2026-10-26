<script lang="ts">
	// The per-game leaders of the home with no games: one row per category the feed sends (one to
	// four), with the player's photo, the category and team, the name and the value. Not the game
	// panel's Leaders (a top performer per team).
	// SEE: docs/design.md, Home with no games
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import PlayerAvatar from '#lib/components/PlayerAvatar.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { HomeLeadersView } from '#lib/home/types.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		view: HomeLeadersView;
		layout: RowLayout;
	};

	let { view, layout }: Props = $props();

	const headingId = $props.id();
	const mobile = $derived(layout === 'mobile');
</script>

<section class="home-leaders" class:mobile aria-labelledby={headingId}>
	<header class="heading">
		<Kicker text={m.home_leaders_kicker()} />
		<h2 id={headingId}>{view.title}</h2>
	</header>
	<ul class="leaders">
		{#each view.leaders as leader (leader.key)}
			<li class="leader">
				<BlueprintFrame>
					<div class="row">
						<span class="photo">
							<PlayerAvatar name={leader.name} photo={leader.photo} size="leader" />
						</span>
						<div class="who">
							<span class="meta">
								{leader.category}{#if leader.team}
									<span aria-hidden="true">·</span>
									<TeamMark team={leader.team} part="label" />{/if}
							</span>
							<span class="name">{leader.name}</span>
						</div>
						<span class="value">{leader.value}</span>
					</div>
				</BlueprintFrame>
			</li>
		{/each}
	</ul>
</section>

<style>
	.home-leaders {
		display: grid;
		gap: var(--game-list-gap);
		min-width: 0;
		align-content: start;
	}

	.heading {
		display: grid;
	}

	h2 {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--section-h2-size);
		line-height: var(--section-h2-line-height);
		text-transform: uppercase;
	}

	.leaders {
		display: grid;
		gap: var(--game-list-gap);
		list-style: none;
		padding: 0;
		margin: 0;
	}

	.row {
		display: grid;
		grid-template-columns: var(--team-leader-photo-width) minmax(0, 1fr) auto;
		align-items: center;
		gap: var(--game-list-gap);
		min-height: var(--home-leaders-row-height);
		padding-right: var(--game-list-gap);
	}

	.photo {
		position: relative;
		align-self: stretch;
		display: flex;
	}

	.who {
		display: grid;
		min-width: 0;
	}

	.meta {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.name {
		font-family: var(--font-heading);
		font-size: var(--player-name-size);
		text-transform: uppercase;
	}

	.value {
		font-family: var(--font-heading);
		font-size: var(--score-size-mobile);
		font-variant-numeric: tabular-nums;
	}
</style>
