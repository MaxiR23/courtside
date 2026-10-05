<script lang="ts">
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import { crossfade, type CrossfadeParams, float, floorShadow, play } from '#lib/hero/motion.ts';
	import type { HeroPlayer } from '#lib/hero/types.ts';

	type Props = { players: readonly HeroPlayer[]; active: number };

	let { players, active }: Props = $props();

	let failed = $state<Record<string, boolean>>({});

	const slideFade = (isActive: boolean): CrossfadeParams => ({
		active: isActive,
		hidden: (read) => ({
			opacity: 0,
			transform: `translateX(-50%) translateY(${read('--hero-slide-offset')}) scale(${read('--hero-slide-scale')})`
		}),
		shown: { opacity: 1, transform: 'translateX(-50%)' },
		durationToken: '--hero-crossfade-duration'
	});

	const player = $derived(players[active]);

	function fullName(p: HeroPlayer): string {
		return `${p.firstName} ${p.lastName}`;
	}

	function initials(p: HeroPlayer): string {
		return `${p.firstName.charAt(0)}${p.lastName.charAt(0)}`;
	}
</script>

<div class="player-cutout">
	<div class="float" use:play={float}>
		<div class="glow"></div>
		<BlueprintFrame>
			<div class="frame">
				{#each players as p, index (index)}
					<div
						class="cutout"
						class:active={index === active}
						aria-hidden={index === active ? undefined : 'true'}
						use:crossfade={slideFade(index === active)}
					>
						{#if failed[p.photo]}
							<div class="cutout-placeholder" role="img" aria-label={fullName(p)}>
								{initials(p)}
							</div>
						{:else}
							<img
								src={p.photo}
								alt={fullName(p)}
								loading="lazy"
								onerror={() => (failed[p.photo] = true)}
							/>
						{/if}
					</div>
				{/each}
				<div class="fade"></div>
			</div>
		</BlueprintFrame>
		{#if player}
			<div class="chip">
				<BlueprintFrame>
					<div class="chip-box">
						<span class="chip-code">{player.teamCode}</span>
						<span class="chip-first">{player.firstName}</span>
						<span class="chip-last">{player.lastName}</span>
						<span class="chip-team">{player.teamName}</span>
					</div>
				</BlueprintFrame>
			</div>
		{/if}
	</div>
	<div class="floor-shadow" use:play={floorShadow}></div>
</div>

<style>
	.player-cutout {
		position: relative;
	}

	.float {
		position: relative;
	}

	.glow {
		position: absolute;
		inset: calc(-1 * var(--accent-glow-extent));
		background: var(--accent-glow);
		pointer-events: none;
	}

	.frame {
		position: relative;
		aspect-ratio: var(--hero-frame-aspect);
		max-width: var(--hero-frame-max-width);
		background-color: var(--color-frame-fill);
		background-image:
			linear-gradient(var(--color-grid-line) var(--hairline), transparent var(--hairline)),
			linear-gradient(90deg, var(--color-grid-line) var(--hairline), transparent var(--hairline));
		background-size: var(--hero-frame-grid-size) var(--hero-frame-grid-size);
		box-shadow: var(--shadow-hero-frame);
	}

	.cutout {
		position: absolute;
		bottom: 0;
		left: 50%;
		width: var(--hero-cutout-width);
	}

	.cutout {
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

	.fade {
		position: absolute;
		inset: auto 0 0;
		height: var(--hero-fade-height);
		background: var(--hero-fade);
		pointer-events: none;
	}

	.chip {
		position: absolute;
		left: var(--chip-left);
		bottom: var(--chip-bottom);
	}

	.chip-box {
		display: flex;
		flex-direction: column;
		padding: var(--game-list-gap);
		background: var(--chip-bg);
		backdrop-filter: blur(var(--chip-blur));
	}

	.chip-code {
		font-family: var(--font-heading);
		font-size: var(--chip-code-size);
		color: var(--color-accent-light);
	}

	.chip-first {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.chip-last {
		font-family: var(--font-heading);
		font-size: var(--chip-last-name-size);
		text-transform: uppercase;
	}

	.chip-team {
		font-size: var(--caption-size);
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
