<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import Button from '#lib/components/Button.svelte';
	import type { EmptyDayView } from '#lib/home/types.ts';

	type Props = {
		view: EmptyDayView;
		windowHref: (date: string) => ResolvedPathname; // a day of the games feed: /?day=YYYY-MM-DD
	};

	let { view, windowHref }: Props = $props();
</script>

<BlueprintFrame>
	<div class="empty-day">
		<h3 class="title">{view.title}</h3>
		<p class="text">{view.text}</p>
		{#if view.goTo}
			<Button variant="secondary" href={windowHref(view.goTo.date)} label={view.goTo.label} />
		{/if}
	</div>
</BlueprintFrame>

<style>
	.empty-day {
		display: grid;
		justify-items: start;
		gap: var(--game-list-gap);
		padding: var(--game-list-gap);
	}

	.title {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--injury-name-size);
		text-transform: uppercase;
	}

	.text {
		margin: 0;
		font-size: var(--body-size);
		color: var(--color-muted);
	}
</style>
