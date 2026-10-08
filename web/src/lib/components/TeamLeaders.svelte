<script lang="ts">
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import PlayerAvatar from '#lib/components/PlayerAvatar.svelte';
	import type { LeadersSection } from '#lib/team/types.ts';

	type Props = { leaders: LeadersSection };

	let { leaders }: Props = $props();
</script>

<ul class="leaders">
	{#each leaders.cards as card (card.label)}
		<li>
			<BlueprintFrame>
				<div class="card">
					<div class="text">
						<span class="label">{card.label}</span>
						<span class="value">{card.value}</span>
						<span class="name">{card.name}</span>
						<span class="line">{card.line}</span>
					</div>
					<PlayerAvatar name={card.name} photo={card.photo} size="leader" />
				</div>
			</BlueprintFrame>
		</li>
	{/each}
</ul>

<style>
	.leaders {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--panel-column-min)), 1fr));
		gap: var(--game-list-gap);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.card {
		display: grid;
		grid-template-columns: 1fr var(--team-leader-photo-width);
		min-height: 100%;
	}

	.text {
		display: grid;
		align-content: start;
		gap: var(--day-strip-gap);
		min-width: 0;
		padding: var(--game-list-gap);
	}

	.label {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-accent-light);
	}

	.value {
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--team-leader-value-size);
		line-height: 1;
		font-variant-numeric: tabular-nums;
	}

	.name {
		font-family: var(--font-heading);
		font-size: var(--injury-name-size);
		hyphens: manual;
		overflow-wrap: normal;
	}

	.line {
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}
</style>
