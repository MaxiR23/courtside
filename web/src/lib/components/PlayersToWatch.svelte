<script lang="ts">
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import PlayerPhoto from '#lib/components/PlayerPhoto.svelte';
	import type { PlayersSection } from '#lib/game/types.ts';

	type Props = { players: PlayersSection };

	let { players }: Props = $props();

	const cards = $derived([players.away, players.home]);
</script>

<div class="players">
	{#each cards as card (card.teamCode)}
		<BlueprintFrame>
			<div class="card">
				<div class="text">
					<span class="tag">{card.teamCode}</span>
					<span class="first">{card.firstName}</span>
					<span class="last">{card.lastName}</span>
					<span class="team">{card.teamName}</span>
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
