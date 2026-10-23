<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import PlayerAvatar from '#lib/components/PlayerAvatar.svelte';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import type { LeadersSection } from '#lib/team/types.ts';

	type Props = {
		leaders: LeadersSection;
		layout: RowLayout;
		playerHref: (id: string) => ResolvedPathname;
	};

	let { leaders, layout, playerHref }: Props = $props();
</script>

<ul class="leaders">
	{#each leaders.cards as card (card.label)}
		<li>
			<a class="card-link" href={playerHref(card.playerId)}>
				<BlueprintFrame>
					<div class="card" class:mobile={layout === 'mobile'}>
						<span class="cutout">
							<PlayerAvatar name={card.name} photo={card.photo} size="team-leader" />
						</span>
						<div class="text">
							<span class="label">{card.label}</span>
							<span class="value">{card.value}</span>
							<span class="name">{card.name}</span>
							<span class="line">{card.line}</span>
						</div>
					</div>
				</BlueprintFrame>
			</a>
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

	.card-link {
		display: block;
		height: 100%;
		color: inherit;
		text-decoration: none;
	}

	.card-link:hover .name {
		color: var(--color-accent-hover);
	}

	.card {
		position: relative;
		overflow: hidden;
		min-height: var(--team-leader-min-height);
	}

	.card.mobile {
		min-height: var(--team-leader-min-height-mobile);
	}

	.cutout {
		position: absolute;
		top: 0;
		right: 0;
		bottom: 0;
		width: var(--team-leader-cutout-width);
	}

	.text {
		position: relative;
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
