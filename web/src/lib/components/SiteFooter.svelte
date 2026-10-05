<script lang="ts">
	import { m } from '#lib/paraglide/messages.js';
</script>

<footer class="site-footer">
	<span class="name">{m.site_name()}</span>
	<span class="disclaimer">{m.footer_disclaimer()}</span>
</footer>

<style>
	.site-footer {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--game-list-gap);
		max-width: var(--content-max-width);
		margin: 0 auto;
		padding: var(--side-padding);
		border-top: var(--hairline) solid var(--color-divider);
	}

	.name {
		font-family: var(--font-heading);
		font-size: var(--brand-size);
		letter-spacing: var(--brand-letter-spacing);
		text-transform: uppercase;
	}

	.disclaimer {
		font-size: var(--caption-size);
		color: var(--color-muted);
	}
</style>
