<script lang="ts">
	// One of the two slide selectors of the hero: the team's mark and name under a track that fills
	// in the side's accent while the slide is on screen. A side with no accent uses the neutral one.
	// SEE: docs/design-team-identity.md
	import TeamMark from '#lib/components/TeamMark.svelte';
	import { play, progressFill } from '#lib/hero/motion.ts';
	import type { HeroSide } from '#lib/hero/types.ts';
	import { m } from '#lib/paraglide/messages.js';

	type Props = {
		side: HeroSide;
		place: 'away' | 'home';
		active: boolean;
		running: boolean; // the slideshow advances on its own: the track fills
		cycle: number; // changes with every slide, so the fill starts again
		onselect: () => void;
	};

	let { side, place, active, running, cycle, onselect }: Props = $props();
</script>

<button
	type="button"
	class="selector"
	class:active
	aria-current={active ? 'true' : undefined}
	aria-label={place === 'away'
		? m.identity_hero_slide_away({ team: side.name })
		: m.identity_hero_slide_home({ team: side.name })}
	style:--side-accent={side.accent ?? 'var(--identity-neutral-accent)'}
	onclick={onselect}
>
	<span class="track">
		{#if active && running}
			{#key cycle}
				<span class="track-fill" use:play={progressFill}></span>
			{/key}
		{/if}
	</span>
	<span class="label">
		<span class="mark"><TeamMark team={side} part="tile" size="fill" logo={side.logo} /></span>
		<span class="name">{side.name}</span>
	</span>
</button>

<style>
	.selector {
		display: flex;
		flex-direction: column;
		justify-content: flex-end;
		gap: var(--game-list-gap);
		min-width: 0;
		min-height: var(--hit-target-size);
		padding: 0;
		background: transparent;
		border: 0;
		font: inherit;
		color: var(--color-muted);
		cursor: pointer;
	}

	.selector.active {
		color: var(--color-ink);
	}

	.track {
		display: block;
		height: var(--progress-track-height);
		background: var(--identity-selector-track-ink);
	}

	.track-fill {
		display: block;
		height: 100%;
		background: var(--side-accent);
		transform-origin: left;
	}

	.label {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
		min-width: 0;
	}

	.mark {
		display: block;
		flex-shrink: 0;
		width: var(--identity-selector-mark);
		height: var(--identity-selector-mark);
	}

	.name {
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--identity-selector-name-size);
		letter-spacing: var(--identity-selector-name-tracking);
		text-transform: uppercase;
	}
</style>
