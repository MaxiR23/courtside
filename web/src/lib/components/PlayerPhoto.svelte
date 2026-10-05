<script lang="ts">
	import type { PanelPlayer } from '#lib/schedule/types.ts';

	type Props = { player: PanelPlayer };

	let { player }: Props = $props();

	// Keyed by photo URL, so a new URL tries again after a failure.
	let failedPhoto = $state<string | null>(null);
	const failed = $derived(failedPhoto === player.photo);
	const fullName = $derived(`${player.firstName} ${player.lastName}`);
	const initials = $derived(`${player.firstName.charAt(0)}${player.lastName.charAt(0)}`);
</script>

<span class="photo-frame">
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

	img {
		position: absolute;
		bottom: 0;
		left: 50%;
		translate: -50% 0;
		display: block;
		width: var(--leader-photo-scale);
		filter: var(--leader-photo-filter);
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
