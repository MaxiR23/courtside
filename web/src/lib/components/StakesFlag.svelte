<script lang="ts">
	import Tag from '#lib/components/Tag.svelte';

	type Props = { text: string }; // "Can clinch", already written

	let { text }: Props = $props();
</script>

<Tag {text} variant="accent" truncate />
