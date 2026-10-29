<script lang="ts">
	import Kicker from '#lib/components/Kicker.svelte';

	type Props = {
		title: string;
		meta?: string | null;
		emphasis?: boolean;
		size?: 'detail' | 'home' | 'mvp'; // default detail: the detail section h2; home: the home section h2; mvp: the Finals MVP title
		id?: string; // the h2 id, for a section's aria-labelledby
		kicker?: string; // the label above the title, drawn by Kicker
		titleSize?: string; // a token reference that replaces the size's font size
		kickerSize?: string; // a token reference for the kicker's font size; default the label size
		kickerGap?: string; // a token reference for the gap between kicker and title; default none
	};

	let {
		title,
		meta = null,
		emphasis = false,
		size = 'detail',
		id,
		kicker,
		titleSize,
		kickerSize,
		kickerGap
	}: Props = $props();
</script>

{#snippet head()}
	<div class="section-head">
		<h2
			{id}
			class:home={size === 'home'}
			class:mvp={size === 'mvp'}
			style:--section-head-size={titleSize}
		>
			{title}
		</h2>
		{#if meta}<span class="meta" class:emphasis>{meta}</span>{/if}
	</div>
{/snippet}

{#if kicker}
	<div class="titled" style:--section-head-kicker-gap={kickerGap}>
		<Kicker contents
			><span class="kicker-text" style:--section-head-kicker-size={kickerSize}>{kicker}</span
			></Kicker
		>
		{@render head()}
	</div>
{:else}
	{@render head()}
{/if}

<style>
	.titled {
		display: grid;
		gap: var(--section-head-kicker-gap, 0);
	}

	.kicker-text {
		font-size: var(--section-head-kicker-size, var(--label-size));
		letter-spacing: var(--label-letter-spacing);
	}

	.section-head {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: baseline;
		gap: var(--game-list-gap);
	}

	.section-head h2 {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--section-head-size, var(--detail-section-h2-size));
		line-height: var(--detail-section-h2-line-height);
		text-transform: uppercase;
	}

	.section-head h2.home {
		font-size: var(--section-head-size, var(--section-h2-size));
		line-height: var(--section-h2-line-height);
	}

	.section-head h2.mvp {
		font-size: var(--section-head-size, var(--playoffs-mvp-title-size));
	}

	.meta {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}

	.meta.emphasis {
		font-family: var(--font-heading);
		font-size: var(--win-prob-meta-size);
		color: var(--color-accent-light);
	}
</style>
