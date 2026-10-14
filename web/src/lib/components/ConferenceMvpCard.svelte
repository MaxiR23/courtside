<script lang="ts">
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import PlayerAvatar from '#lib/components/PlayerAvatar.svelte';
	import type { ConferenceMvpView } from '#lib/playoffs/types.ts';

	type Props = { mvp: ConferenceMvpView };

	let { mvp }: Props = $props();
</script>

<BlueprintFrame>
	<div class="conference-mvp">
		<PlayerAvatar name={mvp.name} photo={mvp.photo} size="roster" />
		<div class="who">
			<span class="name">{mvp.name}</span>
			<span class="label">{mvp.label}</span>
		</div>
		<span class="team">{mvp.team}</span>
	</div>
</BlueprintFrame>

<style>
	.conference-mvp {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
		padding: var(--game-list-gap);
	}

	.who {
		display: grid;
		flex: 1;
		min-width: 0;
	}

	.name {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
	}

	.label {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.team {
		font-family: var(--font-heading);
		font-size: var(--box-name-size);
		color: var(--color-accent-light);
	}
</style>
