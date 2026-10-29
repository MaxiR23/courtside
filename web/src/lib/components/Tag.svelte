<script lang="ts">
	import type { Snippet } from 'svelte';

	import Kicker from '#lib/components/Kicker.svelte';

	type Props = {
		text?: string; // the tag text, when no children are given
		children?: Snippet; // the tag content, such as a team link
		variant?: 'outline' | 'accent' | 'solid' | 'muted' | 'live'; // default outline
		label?: boolean; // default true: the label type through Kicker; false: the tag keeps the surrounding type
		size?: string; // a token reference for the font size; set with tracking when label is on
		tracking?: string; // a token reference for the letter spacing
		padding?: string; // a token reference for the padding; default --tag-padding
		borderColor?: string; // a token reference that replaces the variant's border color
		color?: string; // a token reference that replaces the variant's text color
		heading?: boolean; // heading font at semibold (the past season tag)
		truncate?: boolean; // one line with an ellipsis, at most the container width
		wrap?: 'nowrap' | 'normal'; // white-space; default inherited
		borderless?: boolean; // no border (the All-Star MVP plate's solid tag)
	};

	let {
		text,
		children,
		variant = 'outline',
		label = true,
		size,
		tracking,
		padding,
		borderColor,
		color,
		heading = false,
		truncate = false,
		wrap,
		borderless = false
	}: Props = $props();
</script>

{#snippet box()}
	<span
		class="tag {variant}"
		class:heading
		class:truncate
		class:nowrap={wrap === 'nowrap'}
		class:normal={wrap === 'normal'}
		class:borderless
		style:--tag-size={size}
		style:--tag-tracking={tracking}
		style:--tag-inset={padding}
		style:--tag-border={borderColor}
		style:--tag-color={color}
		>{#if children}{@render children()}{:else}{text}{/if}</span
	>
{/snippet}

{#if label}<Kicker tone="inherit" contents>{@render box()}</Kicker>{:else}{@render box()}{/if}

<style>
	.tag {
		display: inline-block;
		padding: var(--tag-inset, var(--tag-padding));
		border: var(--hairline) solid var(--tag-border, var(--color-divider));
		border-radius: var(--radius);
		font-size: var(--tag-size, inherit);
		letter-spacing: var(--tag-tracking, inherit);
		color: var(--tag-color, inherit);
	}

	.accent {
		border-color: var(--tag-border, var(--color-accent));
		color: var(--tag-color, var(--color-accent-light));
	}

	.solid {
		background: var(--color-accent);
		border-color: var(--color-accent);
		color: var(--color-bg);
	}

	.muted {
		color: var(--tag-color, var(--color-muted));
	}

	.live {
		border-color: var(--color-accent);
		color: var(--color-accent-light);
		font-size: var(--live-badge-size);
		letter-spacing: var(--label-letter-spacing);
	}

	.heading {
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
	}

	.truncate {
		max-width: 100%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		vertical-align: middle;
	}

	.nowrap {
		white-space: nowrap;
	}

	.normal {
		white-space: normal;
	}

	.borderless {
		border: 0;
	}
</style>
