<script lang="ts">
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import PlayerAvatar from '#lib/components/PlayerAvatar.svelte';
	import Tag from '#lib/components/Tag.svelte';
	import type { AwardView } from '#lib/playoffs/types.ts';

	type Props = { award: AwardView };

	let { award }: Props = $props();
</script>

<BlueprintFrame>
	<article class="award-card {award.kind}">
		{#if award.kind === 'player'}
			{#if award.code}<Tag text={award.code} variant="accent" />{/if}
			{#each award.winners as winner (winner.id)}
				<PlayerAvatar name={winner.name} photo={winner.photo} size="playoffs-card" />
				<h3 class="award-name">{award.name}</h3>
				<span class="winner-name">{winner.name}</span>
				<span class="winner-team">{winner.team}</span>
			{/each}
		{:else}
			<h3 class="award-name">{award.name}</h3>
			<ul class="winners">
				{#each award.winners as winner (winner.id)}
					<li class="winner">
						<PlayerAvatar name={winner.name} photo={winner.photo} size="playoffs-avatar" />
						<span class="winner-name">{winner.name}</span>
						<span class="winner-team">{winner.team}</span>
					</li>
				{/each}
			</ul>
		{/if}
	</article>
</BlueprintFrame>

<style>
	.award-card {
		display: grid;
		gap: var(--day-strip-gap);
		align-content: start;
		padding: var(--game-list-gap);
	}

	.award-card.player {
		justify-items: start;
	}

	.award-name {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.winner-name {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-family: var(--font-heading);
		font-size: var(--player-name-size);
	}

	.winner-team {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		color: var(--color-accent-light);
	}

	.winners {
		display: grid;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.winner {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
		padding: var(--day-strip-gap) 0;
		border-bottom: var(--hairline) solid var(--color-row-rule);
	}

	.winner .winner-name {
		flex: 1;
		font-size: var(--box-name-size);
	}
</style>
