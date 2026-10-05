<script lang="ts">
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { HighlightVideo } from '#lib/schedule/types.ts';

	type Props = {
		platform: string;
		searchUrl: string;
		videos: HighlightVideo[];
		playingId?: string | null;
		onPlay?: (videoId: string) => void;
	};

	let { platform, searchUrl, videos, playingId = null, onPlay }: Props = $props();
	const searchLabel = $derived(m.panel_highlights_search({ platform }));

	// The video the user just started: its player takes focus once, so the
	// focus does not stay on the thumbnail that is replaced.
	let startedId = $state<string | null>(null);

	function focusIfStarted(node: HTMLIFrameElement, id: string) {
		if (startedId === id) {
			node.focus();
			startedId = null;
		}
	}
</script>

<div class="highlights">
	<div class="head">
		<Kicker text={m.panel_highlights_kicker()} />
		<span class="platform">{platform}</span>
	</div>
	{#if videos.length > 0}
		<ul class="grid">
			{#each videos as video (video.id)}
				<li>
					<BlueprintFrame>
						<div class="video">
							<div class="media">
								{#if playingId === video.id}
									<iframe
										use:focusIfStarted={video.id}
										src={video.embedUrl}
										title={video.title}
										allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
										allowfullscreen
									></iframe>
								{:else}
									<button
										type="button"
										class="thumb"
										aria-label={m.panel_highlights_play({ title: video.title })}
										onclick={() => {
											startedId = video.id;
											onPlay?.(video.id);
										}}
									>
										<img src={video.thumbnail} alt="" loading="lazy" />
										<span class="play" aria-hidden="true">
											<svg viewBox="0 0 24 24"><polygon points="6 3 20 12 6 21 6 3" /></svg>
										</span>
									</button>
								{/if}
							</div>
							<div class="text">
								<p class="title">{video.title}</p>
								<p class="channel">{video.channel}</p>
							</div>
						</div>
					</BlueprintFrame>
				</li>
			{/each}
		</ul>
	{:else}
		<BlueprintFrame>
			<div class="pending">
				<p class="pending-text">{m.panel_highlights_pending()}</p>
				<a class="ghost" href={searchUrl} target="_blank" rel="external noopener noreferrer">
					{searchLabel}
					<svg viewBox="0 0 24 24" aria-hidden="true">
						<path d="M15 3h6v6" />
						<path d="M10 14 21 3" />
						<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
					</svg>
				</a>
			</div>
		</BlueprintFrame>
	{/if}
</div>

<style>
	.highlights {
		display: grid;
		gap: var(--game-list-gap);
	}

	.head {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: baseline;
		gap: var(--game-list-gap);
	}

	.platform {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--highlight-column-min)), 1fr));
		gap: var(--game-list-gap);
		list-style: none;
		padding: 0;
		margin: 0;
	}

	.video:hover {
		opacity: var(--highlight-hover-opacity);
	}

	.media {
		position: relative;
		aspect-ratio: var(--video-aspect);
		background: var(--color-frame-fill);
	}

	iframe {
		display: block;
		width: 100%;
		height: 100%;
		border: 0;
	}

	.thumb {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		padding: 0;
		border: 0;
		background: none;
		cursor: pointer;
	}

	.thumb img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.play {
		position: absolute;
		top: 50%;
		left: 50%;
		translate: -50% -50%;
		display: flex;
		align-items: center;
		justify-content: center;
		width: var(--play-button-size);
		height: var(--play-button-size);
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

	.text {
		padding: var(--game-list-gap);
	}

	.title {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--highlight-title-size);
	}

	.channel {
		margin: var(--day-strip-gap) 0 0;
		font-size: var(--body-size-small);
		color: var(--color-muted);
	}

	.pending {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--game-list-gap);
		padding: var(--game-list-gap);
	}

	.pending-text {
		margin: 0;
		font-size: var(--body-size);
		color: var(--color-muted);
	}

	.ghost {
		display: inline-flex;
		align-items: center;
		gap: var(--day-strip-gap);
		min-height: var(--hit-target-size);
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		text-decoration: none;
		color: var(--color-accent-light);
	}

	.ghost:hover {
		color: var(--color-accent-hover);
	}

	.ghost svg {
		width: var(--body-size);
		height: var(--body-size);
		fill: none;
		stroke: currentColor;
		stroke-width: var(--icon-stroke-width);
		stroke-linecap: round;
		stroke-linejoin: round;
	}
</style>
