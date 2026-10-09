<script lang="ts">
	import type { PanelPlayer } from '#lib/schedule/types.ts';

	type Props = { player: Pick<PanelPlayer, 'firstName' | 'lastName' | 'photo'>; star?: boolean };

	let { player, star = false }: Props = $props();

	// Keyed by photo URL, so a new URL tries again after a failure.
	let failedPhoto = $state<string | null>(null);
	// No photo (a guest player without a headshot) shows the initials, as a failed photo does.
	const failed = $derived(player.photo === null || failedPhoto === player.photo);
	const fullName = $derived(`${player.firstName} ${player.lastName}`);
	const initials = $derived(`${player.firstName.charAt(0)}${player.lastName.charAt(0)}`);
</script>

<span class="photo-frame" class:star>
	{#if failed}
		<span class="photo-placeholder" role="img" aria-label={fullName}>{initials}</span>
	{:else}
		<img
			src={player.photo}
			alt={fullName}
			loading="lazy"
			onerror={() => (failedPhoto = player.photo)}
		/>
	{/if}
</span>

<style>
	.photo-frame {
		position: relative;
		display: block;
		flex: none;
		width: var(--leader-photo-width);
		height: var(--leader-photo-height);
		overflow: hidden;
		background: var(--color-frame-fill);
		border: var(--hairline) solid var(--color-divider);
	}

	.star {
		width: 100%;
		height: 100%;
		border: 0;
		border-left: var(--hairline) solid var(--color-divider);
		background: var(--star-glow), var(--color-frame-fill);
	}

	img {
		position: absolute;
		bottom: 0;
		left: 50%;
		translate: -50% 0;
		display: block;
		width: var(--leader-photo-scale);
		filter: var(--leader-photo-filter);
	}

	.star img {
		width: auto;
		height: 100%;
		max-width: 100%;
		object-fit: contain;
		object-position: bottom;
	}

	.photo-placeholder {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 100%;
		height: 100%;
		font-family: var(--font-heading);
		font-size: var(--player-name-size);
		color: var(--color-muted);
	}
</style>
