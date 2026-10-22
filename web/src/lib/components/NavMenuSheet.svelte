<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import { play } from '#lib/hero/motion.ts';
	import { navSheetSlide } from '#lib/nav/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { keepFocusInside, lockBodyScroll, moveToBody } from '#lib/search/dialog.ts';

	type NavMenuLink = { label: string; href: ResolvedPathname; current: boolean };
	type Props = {
		links: NavMenuLink[]; // in order: Games (or All games), Standings, then the seasonal links
		home?: {
			dateText: string;
			datetime: string; // 'YYYY-MM-DD'
			onDate?: () => void; // set: the date row is a button that opens the calendar
			spoilerFree: boolean;
			onSpoilerFreeToggle: () => void;
		};
		onClose: () => void;
	};

	let { links, home, onClose }: Props = $props();

	let sheet = $state<HTMLElement>();
	let closeButton = $state<HTMLButtonElement>();

	// Opening is mounting: focus starts on Close, and the page does not scroll under the sheet.
	$effect(() => closeButton?.focus());
	$effect(() => lockBodyScroll(document.body));

	function onKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') onClose();
		else if (sheet) keepFocusInside(event, sheet);
	}
</script>

<svelte:window onkeydown={onKeydown} />

<div class="nav-menu" use:moveToBody>
	<!-- Esc and the Close button are the keyboard path to close. -->
	<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
	<div class="scrim" onclick={onClose}></div>
	<div
		class="sheet"
		role="dialog"
		tabindex="-1"
		aria-modal="true"
		aria-label={m.nav_menu_title()}
		bind:this={sheet}
		use:play={navSheetSlide}
	>
		<div class="bar">
			<h2 class="title">{m.nav_menu_title()}</h2>
			<button type="button" class="close" bind:this={closeButton} onclick={onClose}>
				{m.nav_menu_close()}
			</button>
		</div>
		<ul class="rows">
			{#each links as link (link.href)}
				<li>
					<a
						class="row"
						class:current={link.current}
						aria-current={link.current ? 'page' : undefined}
						href={link.href}
						onclick={onClose}
					>
						{link.label}
					</a>
				</li>
			{/each}
			{#if home}
				<li>
					{#if home.onDate}
						<button
							type="button"
							class="row"
							aria-label={m.past_calendar_open()}
							aria-haspopup="dialog"
							onclick={home.onDate}
						>
							<time datetime={home.datetime}>{home.dateText}</time>
						</button>
					{:else}
						<time class="row date" datetime={home.datetime}>{home.dateText}</time>
					{/if}
				</li>
				<li>
					<button
						type="button"
						class="row spoiler-free"
						aria-pressed={home.spoilerFree}
						onclick={home.onSpoilerFreeToggle}
					>
						{m.nav_spoiler_free()}
					</button>
				</li>
			{/if}
		</ul>
	</div>
</div>

<style>
	.scrim {
		position: fixed;
		inset: 0;
		z-index: var(--nav-menu-z-index);
		background: var(--nav-sheet-scrim);
	}

	.sheet {
		position: fixed;
		right: 0;
		bottom: 0;
		left: 0;
		z-index: var(--nav-menu-z-index);
		display: grid;
		align-content: start;
		gap: var(--game-list-gap);
		box-sizing: border-box;
		max-height: var(--nav-sheet-max-height);
		padding: var(--game-list-gap);
		overflow-y: auto;
		border-top: var(--hairline) solid var(--color-divider);
		background: var(--search-panel-bg);
		color: var(--color-ink);
	}

	.bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--game-list-gap);
	}

	.title {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--team-name-size);
		font-weight: var(--font-weight-semibold);
	}

	.close {
		min-height: var(--hit-target-size);
		padding: 0 var(--game-list-gap);
		border: var(--hairline) solid var(--color-divider);
		border-radius: var(--radius);
		background: transparent;
		color: var(--color-ink);
		font: inherit;
		font-size: var(--body-size);
		cursor: pointer;
	}

	.close:hover {
		border-color: var(--color-accent);
	}

	.rows {
		display: grid;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.row {
		display: flex;
		align-items: center;
		box-sizing: border-box;
		width: 100%;
		min-height: var(--nav-sheet-row);
		padding: 0;
		border: 0;
		border-top: var(--hairline) solid var(--color-divider);
		background: none;
		font: inherit;
		font-size: var(--nav-link-size);
		letter-spacing: var(--nav-link-letter-spacing);
		text-transform: uppercase;
		text-decoration: none;
		color: var(--color-muted);
		cursor: pointer;
	}

	.row:hover {
		color: var(--color-ink);
	}

	.row.current {
		color: var(--color-ink);
		text-decoration: underline;
		text-decoration-color: var(--color-accent);
		text-decoration-thickness: var(--hairline);
	}

	.date {
		cursor: default;
	}

	.spoiler-free {
		color: var(--color-ink);
	}

	.spoiler-free[aria-pressed='true'] {
		color: var(--color-accent-light);
	}
</style>
