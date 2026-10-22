<script lang="ts">
	import { untrack } from 'svelte';
	import type { ResolvedPathname } from '$app/types';
	import SeriesGameLine from '#lib/components/SeriesGameLine.svelte';
	import SeriesNode from '#lib/components/SeriesNode.svelte';
	import SeriesSheet from '#lib/components/SeriesSheet.svelte';
	import type { SeriesId } from '#lib/contract/playoffs.ts';
	import { play } from '#lib/hero/motion.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { SeriesCamera } from '#lib/playoffs/bracket-camera.svelte.ts';
	import {
		CARD,
		championAt,
		connectors,
		gamesAt,
		MOBILE_GROUPS,
		ROW_HEIGHT,
		SERIES_AT,
		SERIES_IDS,
		WORLD
	} from '#lib/playoffs/bracket-layout.ts';
	import { gamesFade } from '#lib/playoffs/motion.ts';
	import type { PlayoffBracketView, SeriesCardView } from '#lib/playoffs/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		bracket: PlayoffBracketView;
		layout: RowLayout;
		gameHref: (id: string) => ResolvedPathname;
		finalsSelectable: string[]; // the Finals games that have a tab in the series section
		onFinalsGame: (id: string) => void;
	};

	let { bracket, layout, gameHref, finalsSelectable, onFinalsGame }: Props = $props();

	const camera = new SeriesCamera();

	let viewport = $state<HTMLElement>();
	let layer = $state<HTMLElement>();
	let focused = $state<SeriesId | null>(null);
	let sheet = $state<SeriesId | null>(null);
	let opener: HTMLButtonElement | null = null;

	const interactive = $derived(layout === 'desktop');
	const byId = $derived(
		Object.fromEntries(bracket.series.map((series) => [series.id, series])) as Record<
			SeriesId,
			SeriesCardView
		>
	);
	const gameCounts = $derived(
		Object.fromEntries(bracket.series.map((series) => [series.id, series.games.length])) as Record<
			SeriesId,
			number
		>
	);
	const lines = connectors();
	const champion = $derived(bracket.series.find((series) => series.champion));
	const selected = $derived(camera.selected === null ? undefined : byId[camera.selected]);
	const sheetSeries = $derived(sheet === null ? undefined : byId[sheet]);
	const championAnchor = championAt();

	const size = () => ({ width: viewport?.clientWidth ?? 0, height: viewport?.clientHeight ?? 0 });
	const measure = () => camera.resize(size());

	$effect(() => {
		if (!layer) return;
		camera.attach(
			layer,
			size(),
			untrack(() => gameCounts)
		);
		return () => camera.destroy();
	});

	// A new feed changes the number of games; the camera is not moved by it.
	$effect(() => camera.setGames(gameCounts));

	// Focus can scroll the clipped viewport (a Tab onto a card out of view). The scroll goes back to 0
	// and becomes a pan of the camera, so the focused card ends up in view.
	function absorbScroll(event: Event) {
		const target = event.currentTarget as HTMLElement;
		const { scrollLeft, scrollTop } = target;
		if (scrollLeft === 0 && scrollTop === 0) return;
		target.scrollLeft = 0;
		target.scrollTop = 0;
		camera.shift(scrollLeft, scrollTop);
	}

	// A click inside the viewport that is not on a card, the games list or the controls zooms out.
	function onViewportClick(event: MouseEvent) {
		if (camera.level !== 2) return;
		if ((event.target as Element).closest('.slot, .games, .controls')) return;
		camera.overview();
	}

	function onBracketKeydown(event: KeyboardEvent) {
		if (!interactive || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
		if (event.key === 'ArrowRight' || event.key === 'ArrowDown') camera.next();
		else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') camera.prev();
		else return;
		event.preventDefault();
		focusSelected();
	}

	// The arrow keys move the focus with the selection, so the focus ring follows the camera.
	function focusSelected() {
		const id = camera.selected;
		if (id === null || !layer) return;
		const index = SERIES_IDS.indexOf(id);
		const button = layer.querySelectorAll<HTMLButtonElement>('.slot > button')[index];
		if (!button) return;
		button.focus({ preventScroll: true });
		focused = id;
	}

	function onWindowKeydown(event: KeyboardEvent) {
		if (
			event.key === 'Escape' &&
			!event.defaultPrevented &&
			interactive &&
			camera.level === 2 &&
			sheet === null
		) {
			camera.overview();
		}
	}

	function openSheet(id: SeriesId, button: HTMLButtonElement) {
		opener = button;
		sheet = id;
	}

	function closeSheet() {
		sheet = null;
		opener?.focus({ preventScroll: true });
	}

	const focusChange = (id: SeriesId) => (isFocused: boolean) => {
		if (isFocused) focused = id;
		else if (focused === id) focused = null;
	};

	const rowDash = (series: SeriesCardView): number => (series.top.team ? ROW_HEIGHT : 0);
</script>

<svelte:window onresize={measure} onkeydown={onWindowKeydown} />

{#if interactive}
	<!-- Arrow keys act only while focus is inside the bracket, so page keys are not taken over. -->
	<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
	<div class="bracket" role="group" aria-label={m.playoffs_bracket()} onkeydown={onBracketKeydown}>
		<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
		<div class="viewport" bind:this={viewport} onclick={onViewportClick} onscroll={absorbScroll}>
			<div class="layer" bind:this={layer}>
				<svg
					class="lines"
					viewBox="0 0 {WORLD.width} {WORLD.height}"
					aria-hidden="true"
					focusable="false"
				>
					{#each lines as line (line.from)}
						<path
							class="connector"
							class:complete={byId[line.from]?.complete}
							d={line.d}
							vector-effect="non-scaling-stroke"
						/>
					{/each}
					{#each bracket.series as series (series.id)}
						{@const at = SERIES_AT[series.id]}
						<rect
							class="frame"
							class:champion={series.champion}
							class:dashed={series.decided === 'none'}
							x={at.x}
							y={at.y}
							width={CARD.width}
							height={CARD.height}
							vector-effect="non-scaling-stroke"
						/>
						{#if series.decided === 'one'}
							<rect
								class="row-dash"
								x={at.x}
								y={at.y + rowDash(series)}
								width={CARD.width}
								height={ROW_HEIGHT}
								vector-effect="non-scaling-stroke"
							/>
						{/if}
						{#if focused === series.id}
							<rect
								class="focus"
								x={at.x}
								y={at.y}
								width={CARD.width}
								height={CARD.height}
								vector-effect="non-scaling-stroke"
							/>
						{/if}
					{/each}
				</svg>
				{#each SERIES_IDS as id (id)}
					{#if byId[id]}
						<div class="slot" style:left="{SERIES_AT[id].x}px" style:top="{SERIES_AT[id].y}px">
							<SeriesNode
								series={byId[id]}
								framed={false}
								onOpen={(next) => camera.select(next)}
								onFocusChange={focusChange(id)}
							/>
						</div>
					{/if}
				{/each}
				{#if champion}
					<span
						class="champion-label"
						style:left="{championAnchor.x}px"
						style:top="{championAnchor.y}px"
					>
						{m.playoffs_champion()}
					</span>
				{/if}
				{#if camera.level === 2 && selected}
					{#key selected.id}
						{@const list = gamesAt(selected.id)}
						<ol class="games" style:left="{list.x}px" style:top="{list.y}px" use:play={gamesFade}>
							{#each selected.games as game (game.key)}
								<li class="game">
									{#if selected.final && finalsSelectable.includes(game.key)}
										<button
											type="button"
											class="game-button"
											onclick={() => onFinalsGame(game.key)}
										>
											<SeriesGameLine {game} />
											<svg class="ring" aria-hidden="true" focusable="false">
												<rect width="100%" height="100%" vector-effect="non-scaling-stroke" />
											</svg>
										</button>
									{:else}
										<SeriesGameLine {game} />
									{/if}
								</li>
							{/each}
						</ol>
					{/key}
				{/if}
			</div>
			<div class="controls">
				<div class="levels">
					<button
						type="button"
						class="control"
						aria-pressed={camera.level === 1}
						onclick={() => camera.overview()}
					>
						<span class="num">1</span>
						{m.playoffs_level_1()}
					</button>
					<button
						type="button"
						class="control"
						aria-pressed={camera.level === 2}
						onclick={() => camera.seriesLevel()}
					>
						<span class="num">2</span>
						{m.playoffs_level_2()}
					</button>
				</div>
				<div class="steps">
					<button
						type="button"
						class="control"
						aria-label={m.playoffs_prev()}
						onclick={() => camera.prev()}
					>
						←
					</button>
					<button
						type="button"
						class="control"
						aria-label={m.playoffs_next()}
						onclick={() => camera.next()}
					>
						→
					</button>
				</div>
			</div>
		</div>
	</div>
{:else}
	<div class="bracket mobile" role="group" aria-label={m.playoffs_bracket()}>
		{#each MOBILE_GROUPS as group (group[0])}
			{@const first = byId[group[0]]}
			{#if first}
				<section class="round">
					<h3 class="round-title">{first.roundTitle}</h3>
					<div class="cards" class:pairs={group.length === 4}>
						{#each group as id (id)}
							<SeriesNode series={byId[id]} framed={true} onOpen={openSheet} />
						{/each}
					</div>
				</section>
			{/if}
		{/each}
	</div>
	{#if sheetSeries}
		<SeriesSheet series={sheetSeries} {gameHref} onClose={closeSheet} />
	{/if}
{/if}

<style>
	.bracket {
		position: relative;
	}

	.viewport {
		position: relative;
		height: var(--playoffs-viewport-height);
		overflow: hidden;
		border: var(--hairline) solid var(--color-divider);
		background: var(--color-bg);
		user-select: none;
	}

	.layer {
		position: absolute;
		top: 0;
		left: 0;
		width: var(--playoffs-world-width);
		height: var(--playoffs-world-height);
		transform-origin: 0 0;
		will-change: transform;
	}

	.lines {
		position: absolute;
		top: 0;
		left: 0;
		width: 100%;
		height: 100%;
		overflow: visible;
		pointer-events: none;
	}

	.slot {
		position: absolute;
	}

	.connector {
		fill: none;
		stroke: var(--playoffs-line-color);
		stroke-width: var(--hairline);
		vector-effect: non-scaling-stroke;
	}

	.connector.complete {
		stroke: var(--color-accent);
	}

	.frame,
	.row-dash,
	.focus {
		fill: none;
		stroke: var(--color-divider);
		stroke-width: var(--hairline);
		vector-effect: non-scaling-stroke;
	}

	.frame.champion {
		stroke: var(--color-accent);
	}

	.frame.dashed,
	.row-dash {
		stroke-dasharray: var(--standings-line-dash);
	}

	.focus {
		stroke: var(--color-accent);
		stroke-width: var(--bracket-focus-width);
	}

	.champion-label {
		position: absolute;
		transform: translate(-50%, -100%);
		font-family: var(--font-heading);
		font-size: var(--label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-accent-light);
		white-space: nowrap;
		pointer-events: none;
	}

	.games {
		position: absolute;
		width: var(--playoffs-column-width);
		margin: 0;
		padding: 0;
		list-style: none;
		font-size: var(--playoffs-game-text-size);
		color: var(--color-ink);
	}

	.game {
		display: flex;
		align-items: center;
		height: var(--playoffs-game-row-height);
	}

	.game-button {
		display: flex;
		width: 100%;
		height: 100%;
		padding: 0;
		border: 0;
		background: none;
		color: inherit;
		font: inherit;
		cursor: pointer;
	}

	/* The ring is drawn non-scaling, so it keeps its width at every zoom. */
	.game-button {
		position: relative;
	}

	.game-button:focus-visible {
		outline: none;
	}

	.ring {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		overflow: visible;
		display: none;
		pointer-events: none;
	}

	.ring rect {
		fill: none;
		stroke: var(--color-accent);
		stroke-width: var(--bracket-focus-width);
		vector-effect: non-scaling-stroke;
	}

	.game-button:focus-visible .ring {
		display: block;
	}

	.game-button:hover {
		color: var(--color-accent-light);
	}

	.controls {
		position: absolute;
		inset: 0;
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		padding: var(--day-strip-gap);
		pointer-events: none;
	}

	.levels,
	.steps {
		display: flex;
		gap: var(--hairline);
		pointer-events: auto;
	}

	.control {
		min-width: var(--hit-target-size);
		min-height: var(--hit-target-size);
		padding: 0 var(--game-list-gap);
		border: var(--hairline) solid var(--color-divider);
		border-radius: var(--radius);
		background: var(--chip-bg);
		color: var(--color-ink);
		font: inherit;
		font-size: var(--body-size);
		cursor: pointer;
	}

	.control:hover {
		border-color: var(--color-accent);
	}

	.control[aria-pressed='true'] {
		border-color: var(--color-accent);
		color: var(--color-accent-light);
	}

	.num {
		font-family: var(--font-heading);
		color: var(--color-muted);
	}

	.mobile {
		display: grid;
		gap: var(--panel-section-gap);
	}

	.round {
		display: grid;
		gap: var(--day-strip-gap);
	}

	.round-title {
		margin: 0;
		font-size: var(--label-size);
		font-weight: var(--font-weight-semibold);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.cards {
		display: grid;
		gap: var(--day-strip-gap);
	}

	.cards.pairs {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}
</style>
