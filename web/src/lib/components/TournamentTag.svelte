<script lang="ts">
	import Tag from '#lib/components/Tag.svelte';

	type Props = { text: string; finals: boolean }; // "Play-In", "NBA Finals"; finals: the solid accent tag

	let { text, finals }: Props = $props();

	const variant = $derived(finals ? ('solid' as const) : ('outline' as const));
	const borderColor = $derived(finals ? undefined : 'var(--playoffs-tag-border)');
	const color = $derived(finals ? undefined : 'var(--color-ink)');
</script>

<!-- A Tag with the playoffs border and the ink text, and a solid variant for the Finals.
	Plain text: no link, no hover. -->
<Tag {text} {variant} {borderColor} {color} truncate />
