<script lang="ts">
	import Tag from '#lib/components/Tag.svelte';

	type Props = { text: string }; // "NBA Cup · Group play", already written

	let { text }: Props = $props();
</script>

<Tag {text} variant="accent" truncate />
