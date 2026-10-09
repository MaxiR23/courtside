<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import NameLink from '#lib/components/NameLink.svelte';
	import PlayerPhoto from '#lib/components/PlayerPhoto.svelte';
	import type { PlayersSection } from '#lib/game/types.ts';

	type Props = {
		players: PlayersSection;
		teamHref: (code: string) => ResolvedPathname;
		playerHref: (id: string) => ResolvedPathname;
	};

	let { players, teamHref, playerHref }: Props = $props();

	// A guest team has no star: its card is not shown.
	const cards = $derived([players.away, players.home].filter((card) => card !== null));
</script>

<div class="players">
	{#each cards as card (card.teamCode)}
		<BlueprintFrame>
			<div class="card">
				<div class="text">
					<span class="tag"><NameLink href={teamHref(card.teamCode)} text={card.teamCode} /></span>
					<a class="name" href={playerHref(card.id)}>
						<span class="first">{card.firstName}</span>
						<span class="last">{card.lastName}</span>
					</a>
					<span class="team"><NameLink href={teamHref(card.teamCode)} text={card.teamName} /></span>
				</div>
				<div class="photo"><PlayerPhoto star player={card} /></div>
			</div>
		</BlueprintFrame>
	{/each}
</div>

<style>
	.players {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--star-card-column-min)), 1fr));
		gap: var(--game-list-gap);
	}

	.card {
		display: grid;
		grid-template-columns: 1fr 1fr;
		min-height: var(--star-card-min-height);
		overflow: hidden;
	}

	.text {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		justify-content: flex-end;
		gap: var(--day-strip-gap);
		min-width: 0;
		padding: var(--game-list-gap);
	}

	.tag {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		border: var(--hairline) solid var(--color-divider);
		padding: var(--tag-padding);
		border-radius: var(--radius);
	}

	.name {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: var(--day-strip-gap);
		color: inherit;
		text-decoration: none;
	}

	.name:hover .last {
		color: var(--color-accent-hover);
	}

	.first {
		font-size: var(--star-first-name-size);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.last {
		font-family: var(--font-heading);
		font-size: var(--star-last-name-size);
		line-height: var(--detail-section-h2-line-height);
		text-transform: uppercase;
		overflow-wrap: normal;
		word-break: keep-all;
	}

	.team {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.photo {
		position: relative;
		min-width: 0;
	}
</style>
