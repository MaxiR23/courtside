<script lang="ts">
	type Props = {
		width?: string; // a token reference for the inline size; default auto
		height?: string; // a token reference for the block size; default auto
		aspect?: string; // an aspect ratio, a token reference or a unitless ratio; default auto
	};

	let { width, height, aspect }: Props = $props();
</script>

<span
	class="bone"
	style:--bone-width={width}
	style:--bone-height={height}
	style:--bone-aspect={aspect}
></span>

<style>
	.bone {
		display: block;
		width: var(--bone-width, auto);
		height: var(--bone-height, auto);
		aspect-ratio: var(--bone-aspect, auto);
		background: var(--color-surface);
		border-radius: var(--radius);
	}
</style>
