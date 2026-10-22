<script lang="ts">
	// One outlined word behind the hero, in the side's accent; the word of the active slide shows.
	// A side with no accent uses the neutral one.
	// SEE: docs/design-team-identity.md
	import { crossfade, type CrossfadeParams } from '#lib/hero/motion.ts';

	type Props = {
		text: string;
		accent: string | null;
		active: boolean;
	};

	let { text, accent, active }: Props = $props();

	const fade = (isActive: boolean): CrossfadeParams => ({
		active: isActive,
		hidden: () => ({ opacity: 0 }),
		shown: { opacity: 1 },
		durationToken: '--hero-watermark-fade-duration'
	});
</script>

<span
	class="word"
	class:active
	style:--side-accent={accent ?? 'var(--identity-neutral-accent)'}
	use:crossfade={fade(active)}>{text}</span
>

<style>
	.word {
		position: absolute;
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--hero-watermark-size);
		line-height: var(--identity-word-leading);
		letter-spacing: var(--identity-word-tracking);
		text-transform: uppercase;
		color: transparent;
		-webkit-text-stroke: var(--hairline) var(--side-accent);
		opacity: 0;
	}

	.word.active {
		opacity: 1;
	}
</style>
