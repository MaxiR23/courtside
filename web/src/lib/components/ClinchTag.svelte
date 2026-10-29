<script lang="ts">
	import Tag from '#lib/components/Tag.svelte';
	import type { ClinchView } from '#lib/standings/types.ts';

	type Props = { clinch: ClinchView };

	let { clinch }: Props = $props();

	// accent: accent border and text; ink: divider border, ink text; muted: divider border, muted text
	const variant = $derived(
		clinch.tone === 'accent'
			? ('accent' as const)
			: clinch.tone === 'muted'
				? ('muted' as const)
				: ('outline' as const)
	);
	const color = $derived(clinch.tone === 'ink' ? 'var(--color-ink)' : undefined);
</script>

<Tag
	text={clinch.code}
	label={false}
	size="var(--injury-tag-size)"
	wrap="nowrap"
	{variant}
	{color}
/>
