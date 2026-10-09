<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import { untrack } from 'svelte';
	import SearchResultRow from '#lib/components/SearchResultRow.svelte';
	import { toSearchPlayerRow, toSearchTeamRow } from '#lib/feed/search-props.ts';
	import { formatNumber } from '#lib/format/locale.ts';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import { keepFocusInside, lockBodyScroll } from '#lib/search/dialog.ts';
	import type { SearchFeedStore } from '#lib/search/feed.svelte.ts';
	import { moveActive } from '#lib/search/keys.ts';
	import { capPlayers, PLAYER_CAP, searchIndex } from '#lib/search/match.ts';
	import { backdropFade, panelRise, playReverse } from '#lib/search/motion.ts';

	type Props = {
		feed: SearchFeedStore;
		layout: RowLayout;
		teamHref: (code: string) => ResolvedPathname;
		playerHref: (id: string) => ResolvedPathname;
		onClose: () => void;
	};

	let { feed, layout, teamHref, playerHref, onClose }: Props = $props();

	let query = $state('');
	let showAll = $state(false);
	let active = $state(0);
	let input: HTMLInputElement;
	let panel: HTMLElement;
	let backdrop: HTMLElement;
	let closing = false;

	// Opening is mounting: each open loads (or revalidates) the index once, and typing never does.
	$effect(() => {
		untrack(() => feed.open());
		input.focus();
		return lockBodyScroll(document.body);
	});

	const trimmed = $derived(query.trim());
	const found = $derived(feed.index && trimmed ? searchIndex(feed.index, trimmed) : null);
	const capped = $derived(found ? capPlayers(found.players, PLAYER_CAP[layout], showAll) : null);
	const teams = $derived(found ? found.teams.map(toSearchTeamRow) : []);
	const players = $derived(capped ? capped.shown.map(toSearchPlayerRow) : []);
	const hidden = $derived(capped?.hidden ?? 0);
	const rowCount = $derived(teams.length + players.length + (hidden > 0 ? 1 : 0));
	const current = $derived(rowCount === 0 ? -1 : Math.min(active, rowCount - 1));
	// Built here: the markup test cannot read a message call with an object inside a { } expression.
	const noResults = $derived(m.search_no_results({ q: trimmed }));
	const teamsLabel = $derived(m.search_teams({ n: formatNumber(teams.length) }));
	const playersLabel = $derived(m.search_players({ n: formatNumber(found?.players.length ?? 0) }));
	const showAllLabel = $derived(m.search_show_all({ n: formatNumber(found?.players.length ?? 0) }));
	const rowId = (i: number) => `search-row-${i}`;

	function resetNavigation() {
		showAll = false;
		active = 0;
	}

	function clear() {
		query = '';
		resetNavigation();
		input.focus();
	}

	// Esc, the Esc button, the backdrop and Cancel all close with the motion played backwards.
	async function requestClose() {
		if (closing) return;
		closing = true;
		await Promise.all([playReverse(backdrop, backdropFade), playReverse(panel, panelRise)]);
		onClose();
	}

	// A row opens a page: close at once, with no motion, so a navigation never runs under the overlay.
	function open() {
		closing = true;
		onClose();
	}

	function showEverything() {
		showAll = true;
		input.focus();
	}

	function onkeydown(event: KeyboardEvent) {
		if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
			event.preventDefault();
			active = moveActive(current, event.key === 'ArrowDown' ? 1 : -1, rowCount);
		} else if (event.key === 'Enter') {
			if (event.target !== input || current < 0) return;
			event.preventDefault();
			document.getElementById(rowId(current))?.click();
		} else if (event.key === 'Escape') {
			event.preventDefault();
			void requestClose();
		} else if (event.key === 'Tab') {
			keepFocusInside(event, panel);
		}
	}
</script>

<div class="overlay" class:sheet={layout === 'mobile'}>
	<!-- Esc and the Esc button are the keyboard path to close. -->
	<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
	<div class="backdrop" bind:this={backdrop} use:play={backdropFade} onclick={requestClose}></div>
	<!-- A click on plain content focuses the panel, so the keys keep reaching it. -->
	<div
		class="panel"
		tabindex="-1"
		bind:this={panel}
		use:play={panelRise}
		role="dialog"
		aria-modal="true"
		aria-label={m.search_trigger_label()}
		{onkeydown}
	>
		<div class="input-row">
			<svg viewBox="0 0 24 24" aria-hidden="true">
				<circle cx="11" cy="11" r="7" />
				<path d="m20 20-3.5-3.5" />
			</svg>
			<input
				type="text"
				bind:this={input}
				bind:value={query}
				oninput={resetNavigation}
				placeholder={m.search_placeholder()}
				aria-label={m.search_trigger_label()}
				autocomplete="off"
				spellcheck="false"
			/>
			{#if query !== ''}
				<button type="button" class="clear" aria-label={m.search_clear()} onclick={clear}>
					<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" /></svg>
				</button>
			{/if}
			<button type="button" class="esc" onclick={requestClose}>
				{layout === 'mobile' ? m.search_cancel() : m.search_esc()}
			</button>
		</div>

		<div class="results">
			{#if feed.unavailable && !feed.index}
				<p class="message">{m.feed_unavailable()}</p>
			{:else if found}
				{#if rowCount === 0}
					<p class="message">{noResults}</p>
				{/if}
				{#if teams.length > 0}
					<h2 class="label">{teamsLabel}</h2>
					{#each teams as team, i (team.code)}
						<SearchResultRow
							row={{ kind: 'team', team }}
							href={teamHref(team.code)}
							{layout}
							id={rowId(i)}
							active={current === i}
							onHover={() => (active = i)}
							onOpen={open}
						/>
					{/each}
				{/if}
				{#if found.players.length > 0}
					<h2 class="label">{playersLabel}</h2>
					{#each players as player, j (player.id)}
						{@const i = teams.length + j}
						<SearchResultRow
							row={{ kind: 'player', player }}
							href={playerHref(player.id)}
							{layout}
							id={rowId(i)}
							active={current === i}
							onHover={() => (active = i)}
							onOpen={open}
						/>
					{/each}
					{#if hidden > 0}
						{@const i = teams.length + players.length}
						<button
							type="button"
							class="show-all"
							class:active={current === i}
							aria-current={current === i ? 'true' : undefined}
							id={rowId(i)}
							onmouseenter={() => (active = i)}
							onclick={showEverything}
						>
							{showAllLabel}
						</button>
					{/if}
				{/if}
			{/if}
		</div>
	</div>
</div>

<style>
	.overlay {
		position: fixed;
		inset: 0;
		z-index: var(--search-z-index);
		display: flex;
		align-items: flex-start;
		justify-content: center;
		padding: var(--search-panel-top) var(--game-list-gap);
	}

	.overlay.sheet {
		padding: 0;
	}

	.backdrop {
		position: absolute;
		inset: 0;
		background: var(--search-backdrop);
		backdrop-filter: blur(var(--search-backdrop-blur));
	}

	.panel {
		position: relative;
		display: flex;
		flex-direction: column;
		width: 100%;
		max-width: var(--search-panel-max-width);
		max-height: 100%;
		background: var(--search-panel-bg);
		border: var(--hairline) solid var(--color-divider);
		border-radius: var(--search-panel-radius);
		box-shadow: var(--search-panel-shadow);
		overflow: hidden;
	}

	.panel:focus {
		outline: none;
	}

	.sheet .panel {
		max-width: none;
		height: 100%;
		border: 0;
		border-radius: 0;
	}

	.input-row {
		display: flex;
		flex: none;
		align-items: center;
		gap: var(--game-list-gap);
		height: var(--search-input-row-height);
		padding: 0 var(--game-list-gap);
		border-bottom: var(--hairline) solid var(--color-divider);
	}

	svg {
		flex: none;
		width: var(--nav-icon-size);
		height: var(--nav-icon-size);
		fill: none;
		stroke: currentColor;
		stroke-width: var(--icon-stroke-width);
		stroke-linecap: round;
		stroke-linejoin: round;
		color: var(--color-muted);
	}

	input {
		flex: 1;
		min-width: 0;
		background: none;
		border: 0;
		outline: 0;
		font-family: var(--font-heading);
		font-weight: var(--font-weight-medium);
		font-size: var(--search-input-size);
		color: var(--color-ink);
	}

	input::placeholder {
		color: var(--color-muted);
	}

	.clear,
	.esc {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		background: none;
		border: 0;
		font: inherit;
		color: var(--color-muted);
		cursor: pointer;
	}

	.esc {
		padding: var(--tag-padding);
		border: var(--hairline) solid var(--color-divider);
		border-radius: var(--search-esc-radius);
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
	}

	.sheet .esc {
		min-height: var(--hit-target-size);
		padding: 0 var(--search-row-inset);
		border: 0;
	}

	.clear:hover,
	.esc:hover {
		color: var(--color-ink);
	}

	.results {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
	}

	.message {
		margin: 0;
		padding: var(--game-list-gap);
		font-size: var(--body-size);
		color: var(--color-muted);
	}

	.label {
		margin: 0;
		padding: var(--game-list-gap) var(--game-list-gap) var(--search-row-inset);
		font-size: var(--label-size);
		font-weight: var(--font-weight-regular);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-accent-light);
	}

	.show-all {
		display: block;
		width: calc(100% - 2 * var(--search-row-inset));
		margin-inline: var(--search-row-inset);
		padding: var(--game-list-gap);
		background: none;
		border: 0;
		font: inherit;
		font-size: var(--body-size);
		text-align: left;
		color: var(--color-accent-light);
		cursor: pointer;
	}

	.show-all.active {
		background: var(--search-active-row);
		border-radius: var(--search-radius);
	}

	.clear:focus-visible,
	.esc:focus-visible,
	.show-all:focus-visible {
		outline: var(--focus-ring-width) solid var(--color-accent);
		outline-offset: var(--focus-ring-offset);
	}
</style>
