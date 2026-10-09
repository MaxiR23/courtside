<script lang="ts">
	import { initials as initialsOf } from '#lib/format/initials.ts';

	type Props = { name: string; photo: string | null; size: 'roster' | 'leader' | 'search' };

	let { name, photo, size }: Props = $props();

	// Keyed by photo URL, so a new URL tries again after a failure.
	let failedPhoto = $state<string | null>(null);
	const showPhoto = $derived(photo !== null && photo !== failedPhoto);
	const initials = $derived(initialsOf(name));
</script>

<span class="avatar {size}">
	{#if photo && showPhoto}
		<img src={photo} alt={name} loading="lazy" onerror={() => (failedPhoto = photo)} />
	{:else}
		<span class="photo-placeholder" role="img" aria-label={name}>{initials}</span>
	{/if}
</span>

<style>
	.avatar {
		position: relative;
		display: block;
		flex: none;
		overflow: hidden;
		background: var(--color-frame-fill);
	}

	.roster {
		width: var(--roster-photo-size);
		height: var(--roster-photo-size);
	}

	.leader {
		align-self: stretch;
		width: var(--team-leader-photo-width);
		height: 100%;
	}

	.search {
		width: var(--search-tile-size);
		height: var(--search-tile-size);
		border-radius: var(--search-tile-radius);
	}

	img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.leader img {
		position: absolute;
		bottom: 0;
		left: 0;
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
		font-size: var(--body-size);
		color: var(--color-muted);
	}

	.leader .photo-placeholder {
		font-size: var(--player-name-size);
	}
</style>
