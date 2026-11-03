<script lang="ts">
	// A note's photo, 16:9. No photo, or one that fails to load, draws nothing: no box, no alt text.
	// A failure is reported through onFail so the card can drop the wrapper around the photo.
	type Props = {
		photo: { url: string; width: number; height: number } | null;
		alt: string; // the note's headline
		onFail?: () => void; // called once when the image fails to load
	};

	let { photo, alt, onFail }: Props = $props();

	// Keyed by photo URL, so a new URL tries again after a failure.
	let failedPhoto = $state<string | null>(null);
</script>

{#if photo && photo.url !== failedPhoto}
	<img
		class="photo"
		src={photo.url}
		width={photo.width}
		height={photo.height}
		{alt}
		loading="lazy"
		onerror={() => {
			failedPhoto = photo.url;
			onFail?.();
		}}
	/>
{/if}

<style>
	.photo {
		display: block;
		width: 100%;
		height: auto;
		aspect-ratio: var(--news-photo-aspect);
		object-fit: cover;
	}
</style>
