<script lang="ts">
	// The hero's right column: one card for the slide on screen, with the side's glows, its faded logo,
	// its tricode and its star's cutout, and a strip with the team mark, the player and the team.
	// A side with no accent uses the neutral one; a side with no logo shows its monogram.
	// SEE: docs/design-team-identity.md
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import NameLink from '#lib/components/NameLink.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import { initials } from '#lib/format/initials.ts';
	import { crossfade, type CrossfadeParams, float, floorShadow, play } from '#lib/hero/motion.ts';
	import type { HeroPlayer, HeroSide } from '#lib/hero/types.ts';

	type Props = {
		sides: readonly HeroSide[]; // one per slide, in slide order
		active: number;
		teamHref: (code: string) => ResolvedPathname;
	};

	let { sides, active, teamHref }: Props = $props();

	let failed = $state<Record<string, boolean>>({});

	const accentOf = (side: HeroSide | undefined) => side?.accent ?? 'var(--identity-neutral-accent)';

	const layerFade = (isActive: boolean): CrossfadeParams => ({
		active: isActive,
		hidden: () => ({ opacity: 0 }),
		shown: { opacity: 1 },
		durationToken: '--hero-crossfade-duration'
	});

	// The cutout settles from below, centered on the card.
	const slideFade = (isActive: boolean): CrossfadeParams => ({
		active: isActive,
		hidden: (read) => ({
			opacity: 0,
			transform: `translateX(-50%) translateY(${read('--hero-slide-offset')}) scale(${read('--hero-slide-scale')})`
		}),
		shown: { opacity: 1, transform: 'translateX(-50%)' },
		durationToken: '--hero-crossfade-duration'
	});

	// The logo and the tricode settle the same way, over the identity duration.
	const settleFade = (isActive: boolean): CrossfadeParams => ({
		active: isActive,
		hidden: (read) => ({
			opacity: 0,
			transform: `translateX(-50%) translateY(${read('--hero-slide-offset')}) scale(${read('--hero-slide-scale')})`
		}),
		shown: { opacity: 1, transform: 'translateX(-50%)' },
		durationToken: '--identity-settle-duration'
	});

	const side = $derived(sides[active]);

	// Only the active slide and the next one load their photo; a slide keeps it once shown, so the
	// crossfade out still has its image.
	const next = $derived((active + 1) % Math.max(1, sides.length));
	let shown = $state<Record<number, boolean>>({});

	$effect(() => {
		shown[active] = true;
		shown[next] = true;
	});

	const loads = (index: number) => index === active || index === next || shown[index] === true;

	function fullName(p: HeroPlayer): string {
		return `${p.firstName} ${p.lastName}`;
	}
</script>

<div class="player-card" style:--side-accent={accentOf(side)}>
	<div class="float" use:play={float}>
		<div class="glow"></div>
		<BlueprintFrame>
			<div class="frame">
				{#each sides as s, index (index)}
					<div
						class="slide"
						class:active={index === active}
						aria-hidden={index === active ? undefined : 'true'}
						style:--side-accent={accentOf(s)}
						use:crossfade={layerFade(index === active)}
					>
						<div class="inner-glow"></div>
						<div class="logo-layer" aria-hidden="true" use:crossfade={settleFade(index === active)}>
							<div class="logo-fade">
								<TeamMark team={s} part="tile" size="fill" logo={s.logo} />
							</div>
						</div>
						<div class="tricode" aria-hidden="true" use:crossfade={settleFade(index === active)}>
							{s.code}
						</div>
						<div
							class="cutout"
							class:active={index === active}
							use:crossfade={slideFade(index === active)}
						>
							{#if failed[s.star.photo]}
								<div class="cutout-placeholder" role="img" aria-label={fullName(s.star)}>
									{initials(s.star)}
								</div>
							{:else if loads(index)}
								<img
									src={s.star.photo}
									alt={fullName(s.star)}
									loading="lazy"
									onerror={() => (failed[s.star.photo] = true)}
								/>
							{/if}
						</div>
					</div>
				{/each}
				<div class="scrim"></div>
				{#if side}
					<div class="strip">
						<span class="strip-mark" aria-hidden="true"
							><TeamMark team={side} part="tile" size="fill" logo={side.logo} /></span
						>
						<span class="strip-text">
							<span class="strip-player">{fullName(side.star)}</span>
							<span class="strip-team"
								><NameLink href={teamHref(side.code)} text={side.star.teamName} /></span
							>
						</span>
					</div>
				{/if}
			</div>
		</BlueprintFrame>
	</div>
	<div class="floor-shadow" use:play={floorShadow}></div>
</div>

<style>
	.player-card {
		position: relative;
		margin-top: var(--identity-card-margin-top);
	}

	.float {
		position: relative;
	}

	.glow {
		position: absolute;
		inset: calc(-1 * var(--accent-glow-extent));
		background: radial-gradient(
			circle,
			var(--side-accent),
			transparent var(--identity-glow-falloff)
		);
		opacity: var(--identity-card-glow-outer-alpha);
		pointer-events: none;
	}

	.frame {
		position: relative;
		overflow: hidden;
		aspect-ratio: var(--hero-frame-aspect);
		max-width: var(--hero-frame-max-width);
		background-color: var(--color-frame-fill);
		background-image:
			linear-gradient(var(--identity-card-grid-line) var(--hairline), transparent var(--hairline)),
			linear-gradient(
				90deg,
				var(--identity-card-grid-line) var(--hairline),
				transparent var(--hairline)
			);
		background-size: var(--hero-frame-grid-size) var(--hero-frame-grid-size);
		box-shadow: var(--shadow-hero-frame);
	}

	.slide {
		position: absolute;
		inset: 0;
		opacity: 0;
	}

	.slide.active {
		opacity: 1;
	}

	.inner-glow {
		position: absolute;
		inset: 0;
		background: radial-gradient(
			circle at var(--identity-card-glow-inner-position),
			var(--side-accent),
			transparent var(--identity-glow-falloff)
		);
		opacity: var(--identity-card-glow-inner-alpha);
		pointer-events: none;
	}

	.logo-layer,
	.tricode {
		position: absolute;
		left: 50%;
		transform: translateX(-50%) translateY(var(--hero-slide-offset)) scale(var(--hero-slide-scale));
		transform-origin: bottom center;
		opacity: 0;
		pointer-events: none;
	}

	.slide.active .logo-layer,
	.slide.active .tricode {
		transform: translateX(-50%);
		opacity: 1;
	}

	.logo-layer {
		top: var(--identity-card-logo-top);
		width: var(--identity-card-logo-width);
		aspect-ratio: 1;
	}

	.logo-fade {
		width: 100%;
		height: 100%;
		opacity: var(--identity-card-logo-opacity);
	}

	.tricode {
		bottom: var(--identity-tricode-bottom);
		font-family: var(--font-heading);
		font-weight: var(--font-weight-bold);
		font-size: var(--identity-tricode-size);
		line-height: var(--identity-tricode-leading);
		white-space: nowrap;
		color: var(--side-accent);
	}

	.cutout {
		position: absolute;
		bottom: 0;
		left: 50%;
		width: var(--hero-cutout-width);
		transform: translateX(-50%) translateY(var(--hero-slide-offset)) scale(var(--hero-slide-scale));
		transform-origin: bottom center;
		opacity: 0;
	}

	.cutout.active {
		transform: translateX(-50%);
		opacity: 1;
	}

	.cutout img {
		display: block;
		width: 100%;
		clip-path: var(--hero-cutout-clip);
		filter: var(--hero-cutout-filter);
	}

	.cutout-placeholder {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 100%;
		aspect-ratio: var(--hero-frame-aspect);
		font-family: var(--font-heading);
		font-size: var(--hero-watermark-size);
		color: var(--color-muted);
	}

	.scrim {
		position: absolute;
		inset: auto 0 0;
		height: var(--identity-scrim-height);
		background: var(--identity-scrim);
		pointer-events: none;
	}

	.strip {
		position: absolute;
		left: var(--identity-strip-inset);
		right: var(--identity-strip-inset);
		bottom: var(--identity-strip-bottom);
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.strip-mark {
		display: block;
		flex-shrink: 0;
		width: var(--identity-strip-mark);
		height: var(--identity-strip-mark);
	}

	.strip-text {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.strip-player {
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--identity-strip-name-size);
		letter-spacing: var(--identity-strip-name-tracking);
		text-transform: uppercase;
	}

	.strip-team {
		font-size: var(--caption-size);
		letter-spacing: var(--identity-strip-team-tracking);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.floor-shadow {
		position: absolute;
		top: calc(100% + var(--floor-shadow-offset));
		left: 50%;
		width: var(--floor-shadow-width);
		height: var(--floor-shadow-height);
		translate: -50% 0;
		background: var(--floor-shadow);
		filter: blur(var(--floor-shadow-blur));
	}
</style>
