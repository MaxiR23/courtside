<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import Button from '#lib/components/Button.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import NavRow from '#lib/components/NavRow.svelte';
	import PlayerCutout from '#lib/components/PlayerCutout.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import {
		crossfade,
		type CrossfadeParams,
		entrance,
		frameEntrance,
		Glide,
		play,
		progressFill
	} from '#lib/hero/motion.ts';
	import { parallaxAllowed, pointerPosition } from '#lib/hero/parallax.ts';
	import { Slideshow } from '#lib/hero/slideshow.svelte.ts';
	import type { HeroGame, HeroPlayer } from '#lib/hero/types.ts';
	import { m } from '#lib/paraglide/messages.js';

	type Props = {
		games: HeroGame[]; // the games of the day; two stars each rotate on the slideshow
		today: Date;
		scheduleHref: ResolvedPathname;
		onMatchDetails: (gameId: string) => void;
		spoilerFree: boolean;
		onSpoilerFreeToggle: () => void;
		autoplay?: boolean;
	};

	let {
		games,
		today,
		scheduleHref,
		onMatchDetails,
		spoilerFree,
		onSpoilerFreeToggle,
		autoplay = true
	}: Props = $props();

	const watermarkFade = (active: boolean): CrossfadeParams => ({
		active,
		hidden: () => ({ opacity: 0 }),
		shown: { opacity: 1 },
		durationToken: '--hero-watermark-fade-duration'
	});

	// Two slides per game: the away star, then the home star. The count is a primitive, so a
	// new games array of the same length keeps the slideshow and its position.
	const slideCount = $derived(Math.max(1, games.length * 2));
	const slideshow = $derived(new Slideshow(slideCount));
	const gameIndex = $derived(Math.floor(slideshow.current / 2));
	const game = $derived(games[gameIndex]);
	const stars = $derived(games.flatMap((g) => [g.away.star, g.home.star]));
	const indicatorSlides = $derived([gameIndex * 2, gameIndex * 2 + 1]);

	const running = $derived(autoplay && games.length > 0);

	$effect(() => {
		if (running) return slideshow.start();
	});

	const pad = (n: number) => String(n).padStart(2, '0');

	let pointer = $state({ x: 0, y: 0 });
	let section: HTMLElement | undefined;
	let parallax: HTMLElement | undefined = $state();
	let watermarks: HTMLElement | undefined;
	const tilt = new Glide();
	const shift = new Glide();

	// The CSS holds the resting transform; the glides animate towards it.
	$effect(() => {
		void pointer.x;
		void pointer.y;
		if (parallax) tilt.run(parallax, '--hero-tilt-duration');
		if (watermarks) shift.run(watermarks, '--hero-watermark-shift-duration');
	});

	function onmousemove(event: MouseEvent) {
		if (!section || !parallaxAllowed(window.matchMedia?.bind(window))) return;
		pointer = pointerPosition(section.getBoundingClientRect(), event.clientX, event.clientY);
	}

	function onmouseleave() {
		pointer = { x: 0, y: 0 };
	}

	function fullName(p: HeroPlayer): string {
		return `${p.firstName} ${p.lastName}`;
	}

	const blurb = $derived(
		game
			? m.hero_blurb({
					awayStar: fullName(game.away.star),
					homeStar: fullName(game.home.star),
					arena: game.arena
				})
			: ''
	);
</script>

<!-- The pointer only drives a decorative parallax. -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<section
	class="hero"
	bind:this={section}
	{onmousemove}
	{onmouseleave}
	style:--pointer-x={pointer.x}
	style:--pointer-y={pointer.y}
>
	<div class="grid-bg" aria-hidden="true"></div>
	<div class="watermark-layer" aria-hidden="true" bind:this={watermarks}>
		{#each stars as slide, i (i)}
			<span
				class="watermark"
				class:active={i === slideshow.current}
				use:crossfade={watermarkFade(i === slideshow.current)}>{slide.shortName}</span
			>
		{/each}
	</div>

	<div class="content">
		<NavRow {today} {scheduleHref} {spoilerFree} {onSpoilerFreeToggle} />

		{#if game}
			<div class="columns">
				<div class="copy">
					<div class="entrance tag" use:play={entrance('--hero-delay-tag')}>
						<StatusTag status={game.status} />
						<Kicker text={`${game.tipTime} · ${game.arena}`} />
					</div>
					<h1 class="entrance headline" use:play={entrance('--hero-delay-h1')}>
						{game.away.name}<br /><span class="at">{m.hero_at()}</span>
						{game.home.name}
					</h1>
					<p class="entrance blurb" use:play={entrance('--hero-delay-blurb')}>
						{blurb}
					</p>
					<div class="entrance buttons" use:play={entrance('--hero-delay-buttons')}>
						<Button
							variant="primary"
							label={m.hero_match_details()}
							onclick={() => onMatchDetails(game.id)}
						/>
						<Button variant="secondary" label={m.hero_all_games()} href={scheduleHref} />
					</div>
					<div class="entrance indicator" use:play={entrance('--hero-delay-indicator')}>
						{#each indicatorSlides as i (i)}
							{@const slide = stars[i]}
							{@const isActive = i === slideshow.current}
							<button
								type="button"
								class="indicator-item"
								class:active={isActive}
								aria-current={isActive ? 'true' : undefined}
								onclick={() => slideshow.goTo(i)}
							>
								<span class="track">
									{#if isActive && running}
										{#key slideshow.cycle}
											<span class="fill" use:play={progressFill}></span>
										{/key}
									{/if}
								</span>
								<span class="indicator-label">
									<span class="number">{pad((i % 2) + 1)}</span>
									<span>{slide.shortName}</span>
								</span>
							</button>
						{/each}
						{#if games.length > 1}
							<span class="position">{pad(gameIndex + 1)} / {pad(games.length)}</span>
						{/if}
					</div>
				</div>

				<div class="visual">
					<div class="parallax" bind:this={parallax}>
						<div class="frame-entrance" use:play={frameEntrance}>
							<PlayerCutout players={stars} active={slideshow.current} />
						</div>
					</div>
				</div>
			</div>
		{/if}
	</div>
</section>

<style>
	.hero {
		--pointer-x: 0;
		--pointer-y: 0;
		position: relative;
		overflow: hidden;
		padding: var(--side-padding);
	}

	.grid-bg {
		position: absolute;
		inset: 0;
		background-image:
			linear-gradient(var(--color-grid-line) var(--hairline), transparent var(--hairline)),
			linear-gradient(90deg, var(--color-grid-line) var(--hairline), transparent var(--hairline));
		background-size: var(--hero-grid-size) var(--hero-grid-size);
		pointer-events: none;
	}

	.watermark-layer {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: flex-end;
		transform: translate(
			calc(var(--pointer-x) * var(--hero-watermark-shift-x)),
			calc(var(--pointer-y) * var(--hero-watermark-shift-y))
		);
		pointer-events: none;
	}

	.watermark {
		position: absolute;
		font-family: var(--font-heading);
		font-size: var(--hero-watermark-size);
		text-transform: uppercase;
		color: transparent;
		-webkit-text-stroke: var(--hero-watermark-stroke);
		opacity: 0;
	}

	.watermark.active {
		opacity: 1;
	}

	.content {
		position: relative;
		max-width: var(--content-max-width);
		margin: 0 auto;
	}

	.columns {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--hero-column-min)), 1fr));
		align-items: center;
		gap: var(--hero-gap);
		min-height: var(--hero-min-height);
	}

	.copy {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: var(--panel-section-gap);
	}

	.tag {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.headline {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--hero-h1-size);
		line-height: var(--hero-h1-line-height);
		letter-spacing: var(--hero-h1-letter-spacing);
		text-transform: uppercase;
	}

	.at {
		font-size: var(--hero-h1-at-size);
		color: var(--color-muted);
	}

	.blurb {
		margin: 0;
		font-size: var(--body-size-hero);
		color: var(--color-muted);
	}

	.buttons {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.indicator {
		display: flex;
		flex-wrap: wrap;
		gap: var(--panel-section-gap);
	}

	.indicator-item {
		display: flex;
		flex-direction: column;
		justify-content: flex-end;
		gap: var(--game-list-gap);
		min-height: var(--hit-target-size);
		padding: 0;
		background: transparent;
		border: 0;
		font: inherit;
		color: var(--color-muted);
		cursor: pointer;
	}

	.indicator-item.active {
		color: var(--color-ink);
	}

	.track {
		display: block;
		height: var(--progress-track-height);
		background: var(--color-divider);
	}

	.fill {
		display: block;
		height: 100%;
		background: var(--color-accent-light);
		transform-origin: left;
	}

	.position {
		align-self: flex-end;
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		color: var(--color-muted);
	}

	.indicator-label {
		display: flex;
		gap: var(--game-list-gap);
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
	}

	.visual {
		display: flex;
		justify-content: center;
	}

	.parallax {
		width: 100%;
		max-width: var(--hero-frame-max-width);
		transform: perspective(var(--hero-perspective))
			rotateY(calc(var(--pointer-x) * var(--hero-tilt-y)))
			rotateX(calc(var(--pointer-y) * var(--hero-tilt-x)));
	}
</style>
