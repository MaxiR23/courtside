<script lang="ts">
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import PlayerAvatar from '#lib/components/PlayerAvatar.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { FinalsMvpView } from '#lib/playoffs/types.ts';

	type Props = { mvp: NonNullable<FinalsMvpView> };

	let { mvp }: Props = $props();
</script>

<BlueprintFrame>
	<div class="finals-mvp">
		<div class="photo">
			<PlayerAvatar name={mvp.name} photo={mvp.photo} size="playoffs-card" />
		</div>
		<div class="who">
			<span class="name">{mvp.name}</span>
			<span class="label">{m.playoffs_finals_mvp()}</span>
		</div>
		<dl class="stats">
			{#each mvp.stats as stat (stat.key)}
				<div class="stat" class:accent={stat.accent}>
					<dt>{stat.label}</dt>
					<dd>{stat.value}</dd>
				</div>
			{/each}
		</dl>
	</div>
</BlueprintFrame>

<style>
	.finals-mvp {
		display: grid;
		justify-items: center;
		gap: var(--game-list-gap);
		padding: var(--panel-section-gap) var(--game-list-gap);
		background: radial-gradient(var(--color-selected-day), transparent);
	}

	.photo {
		display: grid;
		place-items: center;
	}

	.who {
		display: grid;
		justify-items: center;
		text-align: center;
	}

	.name {
		font-family: var(--font-heading);
		font-size: var(--player-name-size);
		text-transform: uppercase;
	}

	.label {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-accent-light);
	}

	.stats {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: var(--game-list-gap);
		width: 100%;
		margin: 0;
	}

	.stat {
		display: grid;
		gap: var(--day-strip-gap);
	}

	dt {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	dd {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--detail-info-value-size);
		font-variant-numeric: tabular-nums;
	}

	.stat.accent dd {
		color: var(--color-accent-light);
	}
</style>
