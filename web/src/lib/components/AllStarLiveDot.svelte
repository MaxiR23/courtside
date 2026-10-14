<script lang="ts">
	import { livePulse } from '#lib/all-star/motion.ts';
	import { play } from '#lib/hero/motion.ts';
</script>

<span class="live-dot" aria-hidden="true" use:play={livePulse}></span>

<style>
	.live-dot {
		display: inline-block;
		flex: none;
		width: var(--allstar-live-dot-size);
		height: var(--allstar-live-dot-size);
		border-radius: 50%;
		background: var(--color-accent-light);
	}
</style>
