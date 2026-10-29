<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import Button from '#lib/components/Button.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import NameLink from '#lib/components/NameLink.svelte';
	import NoGamesHero from '#lib/components/NoGamesHero.svelte';
	import NavRow from '#lib/components/NavRow.svelte';
	import HeroBackgroundWord from '#lib/components/HeroBackgroundWord.svelte';
	import HeroPlayerCard from '#lib/components/HeroPlayerCard.svelte';
	import HeroSlideSelector from '#lib/components/HeroSlideSelector.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { DateCalendar } from '#lib/calendar/types.ts';
	import { entrance, frameEntrance, Glide, play } from '#lib/hero/motion.ts';
	import { parallaxAllowed, pointerPosition } from '#lib/hero/parallax.ts';
	import { Slideshow } from '#lib/hero/slideshow.svelte.ts';
	import type { HeroGame, HeroPlayer } from '#lib/hero/types.ts';
	import type { NoGamesView } from '#lib/home/types.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import { shimmer } from '#lib/skeleton/motion.ts';
	import SkeletonBone from '#lib/components/SkeletonBone.svelte';

	type Props = {
		games: HeroGame[]; // the games in the rotation; two stars each rotate on the slideshow
		today: Date;
		scheduleHref: ResolvedPathname;
		standingsHref: ResolvedPathname;
		layout: RowLayout;
		onMatchDetails: (gameId: string) => void;
		spoilerFree: boolean;
		onSpoilerFreeToggle: () => void;
		autoplay?: boolean;
		teamHref: (code: string) => ResolvedPathname;
		loading?: boolean; // the first feed has not loaded yet: show the skeleton
		calendar?: DateCalendar; // the date opens the calendar sheet
		noGames?: NoGamesView | null; // a loaded day with no games: the no-games hero
	};

	let {
		games,
		today,
		scheduleHref,
		standingsHref,
		layout,
		onMatchDetails,
		spoilerFree,
		onSpoilerFreeToggle,
		autoplay = true,
		teamHref,
		loading = false,
		calendar,
		noGames = null
	}: Props = $props();

	// Two slides per game: the away star, then the home star. The count is a primitive, so a
	// new games array of the same length keeps the slideshow and its position.
	const slideCount = $derived(Math.max(1, games.length * 2));
	const slideshow = $derived(new Slideshow(slideCount));
	const gameIndex = $derived(Math.floor(slideshow.current / 2));
	const game = $derived(games[gameIndex]);
	const slides = $derived(games.flatMap((g) => [g.away, g.home]));

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

	const kicker = $derived(
		game
			? `${game.status === 'delayed' ? m.hero_kicker_scheduled({ tipTime: game.tipTime }) : game.tipTime}${game.arena ? ` · ${game.arena}` : ''}`
			: ''
	);

	const blurb = $derived(
		game?.arena
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
	aria-busy={loading && !game ? 'true' : undefined}
	style:--pointer-x={pointer.x}
	style:--pointer-y={pointer.y}
>
	<div class="grid-bg" aria-hidden="true"></div>
	<div class="watermark-layer" aria-hidden="true" bind:this={watermarks}>
		{#each slides as slide, i (i)}
			<HeroBackgroundWord
				text={slide.star.shortName}
				accent={slide.accent}
				active={i === slideshow.current}
			/>
		{/each}
	</div>

	<div class="content">
		<NavRow
			page="home"
			gamesHref={scheduleHref}
			{standingsHref}
			{layout}
			home={{ today, spoilerFree, onSpoilerFreeToggle, calendar }}
		/>

		{#if game}
			<div class="columns">
				<div class="copy">
					<div class="entrance tag" use:play={entrance('--hero-delay-tag')}>
						<StatusTag status={game.status} />
						<Kicker text={kicker} />
					</div>
					<h1 class="entrance headline" use:play={entrance('--hero-delay-h1')}>
						<span class="title-logo" aria-hidden="true"
							><TeamMark team={game.away} part="tile" size="fill" logo={game.away.logo} /></span
						><NameLink href={teamHref(game.away.code)} text={game.away.name} /><br /><span
							class="at">{m.hero_at()}</span
						>
						<span class="title-logo" aria-hidden="true"
							><TeamMark team={game.home} part="tile" size="fill" logo={game.home.logo} /></span
						><NameLink href={teamHref(game.home.code)} text={game.home.name} />
					</h1>
					{#if blurb}
						<p class="entrance blurb" use:play={entrance('--hero-delay-blurb')}>
							{blurb}
						</p>
					{/if}
					<div class="entrance buttons" use:play={entrance('--hero-delay-buttons')}>
						<Button
							variant="primary"
							label={m.hero_match_details()}
							onclick={() => onMatchDetails(game.id)}
						/>
						<Button variant="secondary" label={m.hero_all_games()} href={scheduleHref} />
					</div>
					<div class="entrance indicator" use:play={entrance('--hero-delay-indicator')}>
						{#each [gameIndex * 2, gameIndex * 2 + 1] as i (i)}
							<HeroSlideSelector
								side={slides[i]}
								place={i % 2 === 0 ? 'away' : 'home'}
								active={i === slideshow.current}
								{running}
								cycle={slideshow.cycle}
								onselect={() => slideshow.goTo(i)}
							/>
						{/each}
						{#if games.length > 1}
							<span class="position">{pad(gameIndex + 1)} / {pad(games.length)}</span>
						{/if}
					</div>
				</div>

				<div class="visual">
					<div class="parallax" bind:this={parallax}>
						<div class="frame-entrance" use:play={frameEntrance}>
							<HeroPlayerCard sides={slides} active={slideshow.current} {teamHref} />
						</div>
					</div>
				</div>
			</div>
		{:else if loading}
			<div class="columns hero-skeleton" aria-hidden="true" use:play={shimmer}>
				<div class="copy">
					<div class="tag">
						<SkeletonBone width="var(--skeleton-tag-width)" height="var(--label-size)" />
						<SkeletonBone width="var(--skeleton-button-width)" height="var(--label-size)" />
					</div>
					<SkeletonBone
						width="var(--skeleton-long-width)"
						height="calc(var(--hero-h1-size) * var(--hero-h1-line-height))"
					/>
					<SkeletonBone
						width="var(--skeleton-short-width)"
						height="calc(var(--hero-h1-size) * var(--hero-h1-line-height))"
					/>
					<SkeletonBone width="var(--skeleton-long-width)" height="var(--body-size-hero)" />
					<div class="buttons">
						<SkeletonBone width="var(--skeleton-button-width)" height="var(--hit-target-size)" />
						<SkeletonBone width="var(--skeleton-button-width)" height="var(--hit-target-size)" />
					</div>
					<div class="indicator">
						<SkeletonBone width="var(--skeleton-tag-width)" height="var(--hit-target-size)" />
						<SkeletonBone width="var(--skeleton-tag-width)" height="var(--hit-target-size)" />
					</div>
				</div>
				<div class="visual">
					<div class="frame-bone-wrap">
						<BlueprintFrame><SkeletonBone aspect="var(--hero-frame-aspect)" /></BlueprintFrame>
					</div>
				</div>
			</div>
		{:else if noGames}
			<NoGamesHero view={noGames} {layout} />
		{/if}
	</div>
</section>

<style>
	.hero {
		--pointer-x: 0;
		--pointer-y: 0;
		position: relative;
		overflow: hidden;
		padding: var(--identity-hero-pad-top) var(--side-padding) var(--identity-hero-pad-bottom);
		border-bottom: var(--hairline) solid var(--color-divider);
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
		opacity: var(--identity-word-stroke-alpha);
		pointer-events: none;
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
		gap: var(--identity-left-gap);
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

	.title-logo {
		display: inline-block;
		width: var(--identity-title-logo-size);
		height: var(--identity-title-logo-size);
		margin-right: var(--identity-title-logo-gap);
		vertical-align: baseline;
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
		display: grid;
		grid-template-columns: repeat(2, minmax(0, var(--identity-selector-max-width)));
		gap: var(--identity-selector-gap);
	}

	.position {
		grid-column: 1 / -1;
		align-self: end;
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		color: var(--color-muted);
	}

	.visual {
		display: flex;
		justify-content: center;
	}

	.frame-bone-wrap {
		width: 100%;
		max-width: var(--hero-frame-max-width);
	}

	.parallax {
		width: 100%;
		max-width: var(--hero-frame-max-width);
		transform: perspective(var(--hero-perspective))
			rotateY(calc(var(--pointer-x) * var(--hero-tilt-y)))
			rotateX(calc(var(--pointer-y) * var(--hero-tilt-x)));
	}
</style>
