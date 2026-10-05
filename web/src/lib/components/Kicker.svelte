<script lang="ts">
	type Props = { text: string };

	let { text }: Props = $props();
</script>

<span class="kicker">{text}</span>

<style>
	.kicker {
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-accent-light);
	}
</style>
