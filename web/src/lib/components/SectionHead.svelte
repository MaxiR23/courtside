<script lang="ts">
	type Props = { title: string; meta?: string | null; emphasis?: boolean };

	let { title, meta = null, emphasis = false }: Props = $props();
</script>

<div class="section-head">
	<h2>{title}</h2>
	{#if meta}<span class="meta" class:emphasis>{meta}</span>{/if}
</div>

<style>
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
		font-size: var(--detail-section-h2-size);
		line-height: var(--detail-section-h2-line-height);
		text-transform: uppercase;
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
