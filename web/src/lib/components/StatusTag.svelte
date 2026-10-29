<script lang="ts">
	import type { InjuryTagStatus } from '#lib/game/types.ts';
	import type { HeroStatus } from '#lib/hero/types.ts';
	import Tag from '#lib/components/Tag.svelte';
	import { m } from '#lib/paraglide/messages.js';

	type Props =
		{ status: HeroStatus } | { injury: InjuryTagStatus } | { text: string; accent?: boolean }; // free text, such as a game tag

	let props: Props = $props();

	const labels: Record<HeroStatus, () => string> = {
		tonight: m.status_tonight,
		live: m.status_live,
		final: m.status_final,
		delayed: m.status_delayed,
		postponed: m.status_postponed,
		canceled: m.status_canceled
	};

	const injuryLabels: Record<InjuryTagStatus, () => string> = {
		out: m.injury_status_out,
		doubtful: m.injury_status_doubtful,
		questionable: m.injury_status_questionable,
		probable: m.injury_status_probable,
		'day-to-day': m.injury_status_day_to_day
	};

	// out: accent; doubtful and questionable: the ink text; probable and day-to-day: muted
	const injuryLook = $derived.by(() => {
		if (!('injury' in props)) return null;
		if (props.injury === 'out') return { variant: 'accent' as const, color: undefined };
		if (props.injury === 'doubtful' || props.injury === 'questionable')
			return { variant: 'outline' as const, color: 'var(--color-ink)' };
		return { variant: 'muted' as const, color: undefined };
	});
</script>

{#if 'injury' in props && injuryLook}
	<Tag
		text={injuryLabels[props.injury]()}
		variant={injuryLook.variant}
		size="var(--injury-tag-size)"
		tracking="var(--injury-tag-letter-spacing)"
		wrap="nowrap"
		color={injuryLook.color}
	/>
{:else if 'text' in props}
	<Tag text={props.text} variant={props.accent ? 'accent' : 'outline'} />
{:else if 'status' in props}
	<Tag text={labels[props.status]()} />
{/if}
