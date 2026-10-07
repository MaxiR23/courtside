<script lang="ts">
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import type { VideosSection } from '#lib/game/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = { videos: VideosSection; layout: RowLayout };

	let { videos, layout }: Props = $props();
</script>

<ul class="videos {layout}">
	{#each videos as video, i (i)}
		<li>
			<a class="video" href={video.href} target="_blank" rel="external noopener noreferrer">
				<BlueprintFrame hoverable>
					<span class="thumb">
						{#if video.thumbnail}
							<img src={video.thumbnail} alt="" loading="lazy" />
						{:else}
							<span class="bare-grid"></span>
						{/if}
						<span class="play" aria-hidden="true">
							<svg viewBox="0 0 24 24"><polygon points="6 3 20 12 6 21 6 3" /></svg>
						</span>
						<span class="duration">{video.duration}</span>
					</span>
					<span class="text">
						<span class="title">{video.title}</span>
						<svg class="arrow" viewBox="0 0 24 24" aria-hidden="true">
							<path d="M7 7h10v10" />
							<path d="M7 17 17 7" />
						</svg>
					</span>
				</BlueprintFrame>
			</a>
		</li>
	{/each}
</ul>

<style>
	.videos {
		display: grid;
		gap: var(--game-list-gap);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.desktop {
		grid-template-columns: repeat(auto-fill, minmax(var(--video-column-min), 1fr));
	}

	.mobile {
		grid-template-columns: repeat(2, 1fr);
	}

	.video {
		display: block;
		color: inherit;
		text-decoration: none;
	}

	.thumb {
		position: relative;
		display: block;
		overflow: hidden;
		aspect-ratio: var(--video-aspect);
	}

	.thumb img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.bare-grid {
		position: absolute;
		inset: 0;
		background-image:
			linear-gradient(var(--color-grid-line) var(--hairline), transparent var(--hairline)),
			linear-gradient(90deg, var(--color-grid-line) var(--hairline), transparent var(--hairline));
		background-size: var(--hero-frame-grid-size) var(--hero-frame-grid-size);
	}

	.play {
		position: absolute;
		top: 50%;
		left: 50%;
		translate: -50% -50%;
		display: flex;
		align-items: center;
		justify-content: center;
		width: var(--video-play-size);
		height: var(--video-play-size);
		background: var(--color-accent);
		color: var(--color-bg);
	}

	.play svg {
		width: var(--play-icon-size);
		height: var(--play-icon-size);
		fill: currentColor;
		stroke: currentColor;
		stroke-width: var(--icon-stroke-width);
		stroke-linejoin: round;
	}

	.duration {
		position: absolute;
		right: var(--day-strip-gap);
		bottom: var(--day-strip-gap);
		padding: var(--tag-padding);
		background: var(--color-bg);
		font-size: var(--caption-size);
		font-variant-numeric: tabular-nums;
	}

	.text {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: var(--day-strip-gap);
		padding: var(--game-list-gap);
	}

	.title {
		font-family: var(--font-heading);
		font-size: var(--video-title-size);
	}

	.arrow {
		flex: none;
		width: var(--nav-icon-size);
		height: var(--nav-icon-size);
		fill: none;
		stroke: currentColor;
		stroke-width: var(--icon-stroke-width);
		stroke-linecap: round;
		stroke-linejoin: round;
	}
</style>
