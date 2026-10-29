<script lang="ts">
	import Tag from '#lib/components/Tag.svelte';
	import type { TitleView } from '#lib/playoffs/types.ts';

	type Props = { title: TitleView };

	let { title }: Props = $props();
</script>

<!-- A title of the team this season (ADR 0035). Plain text: no link. It wraps at spaces. -->
<Tag text={title.text} variant={title.solid ? 'solid' : 'accent'} wrap="normal" />
