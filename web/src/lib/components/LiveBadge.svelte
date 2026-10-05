<script lang="ts">
	import { m } from '#lib/paraglide/messages.js';
</script>

<span class="live-badge">{m.live_badge()}</span>

<style>
	.live-badge {
		display: inline-block;
		font-size: var(--live-badge-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-accent-light);
		border: var(--hairline) solid var(--color-accent);
		padding: var(--tag-padding);
		border-radius: var(--radius);
	}
</style>
