<script lang="ts">
	import Tag from '#lib/components/Tag.svelte';

	type Props = { text: string }; // "Season 2004-05"

	let { text }: Props = $props();
</script>

<Tag
	{text}
	variant="accent"
	heading
	size="var(--past-tag-size)"
	tracking="var(--past-tag-letter-spacing)"
	wrap="nowrap"
/>
