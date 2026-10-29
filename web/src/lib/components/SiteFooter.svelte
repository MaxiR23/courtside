<script lang="ts">
	import PageContainer from '#lib/components/PageContainer.svelte';
	import { m } from '#lib/paraglide/messages.js';
</script>

<PageContainer divider>
	<footer class="site-footer">
		<span class="name">{m.site_name()}</span>
		<span class="disclaimer">{m.identity_footer_disclaimer()}</span>
	</footer>
</PageContainer>

<style>
	.site-footer {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--game-list-gap);
	}

	.name {
		font-family: var(--font-heading);
		font-size: var(--footer-brand-size);
		letter-spacing: var(--brand-letter-spacing);
		text-transform: uppercase;
	}

	.disclaimer {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}
</style>
