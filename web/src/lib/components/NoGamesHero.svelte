<script lang="ts">
	import ComingUp from '#lib/components/ComingUp.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import StatusTag from '#lib/components/StatusTag.svelte';
	import { entrance, play } from '#lib/hero/motion.ts';
	import type { NoGamesView } from '#lib/home/types.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = { view: NoGamesView; layout: RowLayout };

	let { view, layout }: Props = $props();

	// The card sits in the hero's right column on desktop; on mobile the page draws it as a section.
	const card = $derived(layout === 'desktop' ? view.comingUp : null);

	// The TV network follows the tip-off only when the feed names one.
	const next = $derived(
		view.broadcast ? `${view.nextTipOff} · ${view.broadcast}` : view.nextTipOff
	);
</script>

<div class="columns" class:with-card={card !== null} class:mobile={layout === 'mobile'}>
	<div class="copy">
		<div class="tag" use:play={entrance('--hero-delay-tag')}>
			{#if view.tag}<StatusTag text={view.tag} />{/if}
			<Kicker text={view.date} />
		</div>
		<h1 class="title" use:play={entrance('--hero-delay-h1')}>{m.home_no_games_title()}</h1>
		{#if view.paragraph}
			<p class="paragraph" use:play={entrance('--hero-delay-blurb')}>{view.paragraph}</p>
		{/if}
		{#if view.nextTipOff}
			<p class="next" use:play={entrance('--hero-delay-buttons')}>{next}</p>
		{/if}
	</div>
	{#if card}
		<ComingUp items={card} layout="desktop" />
	{/if}
</div>

<style>
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

	.title {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--home-no-games-title-size);
		line-height: var(--hero-h1-line-height);
		letter-spacing: var(--hero-h1-letter-spacing);
		text-transform: uppercase;
		text-wrap: balance;
	}

	.mobile .title {
		font-size: var(--home-no-games-title-size-mobile);
	}

	.paragraph,
	.next {
		margin: 0;
		font-size: var(--body-size-hero);
		color: var(--color-muted);
	}
</style>
