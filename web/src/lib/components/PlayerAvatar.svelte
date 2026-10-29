<script lang="ts">
	import { initials as initialsOf } from '#lib/format/initials.ts';

	type Props = {
		name: string | { firstName: string; lastName: string }; // the object form where the feed carries both names
		photo: string | null;
		size:
			| 'roster'
			| 'leader'
			| 'team-leader'
			| 'search'
			| 'cup-card'
			| 'playoffs-avatar'
			| 'playoffs-card'
			| 'allstar-box'
			| 'allstar-top5'
			| 'allstar-top5-mobile'
			| 'allstar-roster'
			| 'allstar-roster-mobile'
			| 'allstar-mvp'
			| 'allstar-plate'
			| 'allstar-plate-cover'
			| 'playoffs-mvp'
			| 'playoffs-conference-mvp';
		clip?: 'all' | 'bottom'; // bottom: out of flow, so the image never sets the cell height; a taller one loses only its bottom
	};

	let { name, photo, size, clip = 'all' }: Props = $props();

	// Keyed by photo URL, so a new URL tries again after a failure.
	let failedPhoto = $state<string | null>(null);
	const showPhoto = $derived(photo !== null && photo !== failedPhoto);
	const label = $derived(typeof name === 'string' ? name : `${name.firstName} ${name.lastName}`);
	const initials = $derived(initialsOf(name));
</script>

<span class="avatar {size}" class:clip-bottom={clip === 'bottom'}>
	{#if photo && showPhoto}
		<img src={photo} alt={label} loading="lazy" onerror={() => (failedPhoto = photo)} />
	{:else}
		<span class="photo-placeholder" role="img" aria-label={label}>{initials}</span>
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

	.team-leader {
		width: 100%;
		height: 100%;
		background: none;
	}

	.team-leader img {
		position: absolute;
		right: 0;
		bottom: 0;
		object-fit: contain;
		object-position: bottom right;
		filter: var(--hero-cutout-filter);
	}

	.team-leader .photo-placeholder {
		font-size: var(--player-name-size);
	}

	.playoffs-mvp,
	.playoffs-conference-mvp {
		width: 100%;
		height: 100%;
		background: none;
	}

	.playoffs-mvp img,
	.playoffs-conference-mvp img {
		position: absolute;
		bottom: 0;
		left: 50%;
		translate: -50% 0;
		height: auto;
		object-fit: contain;
		filter: var(--playoffs-mvp-cutout-filter);
	}

	.playoffs-mvp img {
		width: var(--playoffs-mvp-photo-width);
	}

	.playoffs-conference-mvp img {
		width: var(--playoffs-conf-photo-width);
	}

	.avatar.clip-bottom {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		justify-content: safe flex-end;
		align-items: center;
	}

	.avatar.clip-bottom img {
		position: static;
		flex: none;
		translate: none;
	}

	.search {
		width: var(--search-tile-size);
		height: var(--search-tile-size);
		border-radius: var(--search-tile-radius);
	}

	.cup-card {
		width: var(--cup-card-photo-size);
		height: var(--cup-card-photo-size);
	}

	.playoffs-card {
		width: var(--playoffs-card-photo-size);
		height: var(--playoffs-card-photo-size);
	}

	.playoffs-avatar {
		width: var(--playoffs-avatar-size);
		height: var(--playoffs-avatar-size);
	}

	.allstar-box {
		width: var(--allstar-box-photo-size);
		height: var(--allstar-box-photo-size);
	}

	.allstar-top5 {
		width: var(--allstar-top5-photo-size);
		height: var(--allstar-top5-photo-size);
	}

	.allstar-top5-mobile {
		width: var(--allstar-top5-photo-size-mobile);
		height: var(--allstar-top5-photo-size-mobile);
	}

	.allstar-roster {
		width: 100%;
		aspect-ratio: 1;
	}

	.allstar-roster-mobile {
		width: var(--allstar-roster-tile-mobile);
		height: var(--allstar-roster-tile-mobile);
	}

	.allstar-mvp {
		width: 100%;
		height: 100%;
	}

	.allstar-plate {
		width: 100%;
		height: var(--allstar-plate-photo-height);
		background: none;
	}

	.allstar-plate img {
		object-fit: contain;
		object-position: bottom;
	}

	.allstar-plate-cover {
		width: 100%;
		height: var(--allstar-plate-cover-height);
		background: none;
	}

	.allstar-plate-cover img {
		object-fit: cover;
		object-position: bottom center;
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
