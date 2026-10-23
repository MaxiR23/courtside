<script lang="ts">
	import type { ResolvedPathname } from '$app/types';
	import BracketNode from '#lib/components/BracketNode.svelte';
	import CupBracketTree from '#lib/components/CupBracketTree.svelte';
	import MatchupPanel from '#lib/components/MatchupPanel.svelte';
	import type { SlotId } from '#lib/contract/cup.ts';
	import {
		championAnchor,
		connectors,
		DESKTOP_WORLD,
		NODE,
		nodesOf,
		roundLabels,
		TICK_SIZE
	} from '#lib/cup/bracket-layout.ts';
	import { BracketCamera } from '#lib/cup/camera.svelte.ts';
	import type { CupMatchupStore } from '#lib/cup/matchup.svelte.ts';
	import type { BracketView, MatchupPanelState, OpenCard } from '#lib/cup/types.ts';
	import { toMatchupView } from '#lib/feed/cup-matchup-props.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = {
		bracket: BracketView;
		layout: RowLayout;
		matchup: CupMatchupStore;
		gameHref: (id: string) => ResolvedPathname;
		playerHref: (id: string) => ResolvedPathname;
	};

	let { bracket, layout, matchup, gameHref, playerHref }: Props = $props();

	const camera = new BracketCamera();

	let viewport = $state<HTMLElement>();
	let layer = $state<HTMLElement>();
	let focused = $state<SlotId | null>(null);
	let card = $state<OpenCard | null>(null);
	let opener: HTMLButtonElement | null = null;

	const interactive = $derived(layout === 'desktop');
	const world = DESKTOP_WORLD;
	const nodes = $derived(nodesOf(world));
	const lines = $derived(connectors(world));
	const labels = $derived(roundLabels(world));
	const champion = $derived(championAnchor(world));
	const level = $derived(camera.level);
	const finalNode = $derived(bracket.nodes.find((node) => node.final));

	const panelState = $derived<MatchupPanelState>(
		matchup.feed
			? { kind: 'ready', view: toMatchupView(matchup.feed, { past: matchup.past }) }
			: matchup.failed
				? { kind: 'unavailable' }
				: { kind: 'loading' }
	);

	const size = () => ({ width: viewport?.clientWidth ?? 0, height: viewport?.clientHeight ?? 0 });
	const measure = () => camera.resize(size());

	$effect(() => {
		if (!layer) return;
		camera.attach(layer, world, size(), interactive);
		return () => camera.destroy();
	});

	// Not passive, so a zoom or a pan can keep the page from scrolling.
	$effect(() => {
		const target = viewport;
		if (!target || !interactive) return;
		const onWheel = (event: WheelEvent) => camera.wheel(event, target.getBoundingClientRect());
		target.addEventListener('wheel', onWheel, { passive: false });
		return () => target.removeEventListener('wheel', onWheel);
	});

	// The click that ends a drag is not a click on a node.
	function swallowDragClick(event: MouseEvent) {
		if (!camera.suppressClick) return;
		camera.suppressClick = false;
		event.stopPropagation();
		event.preventDefault();
	}

	// Focus can scroll the clipped viewport: hand that offset to the camera and keep the scroll at 0.
	function absorbScroll(event: Event) {
		const target = event.currentTarget as HTMLElement;
		const { scrollLeft, scrollTop } = target;
		if (scrollLeft === 0 && scrollTop === 0) return;
		target.scrollLeft = 0;
		target.scrollTop = 0;
		camera.shift(scrollLeft, scrollTop);
	}

	const stopPointer = (event: Event) => event.stopPropagation();

	function open(id: SlotId, button: HTMLButtonElement) {
		opener = button;
		card = null;
		matchup.open(id);
	}

	function closePanel() {
		card = null;
		matchup.close();
		opener?.focus({ preventScroll: true });
	}

	function onKeydown(event: KeyboardEvent) {
		if (event.key !== 'Escape' || matchup.openId === null) return;
		if (card) card = null;
		else closePanel();
	}

	const focusChange = (id: SlotId) => (isFocused: boolean) => {
		if (isFocused) focused = id;
		else if (focused === id) focused = null;
	};

	const ticks = (x: number, y: number): string[] => {
		const right = x + NODE.width;
		const bottom = y + NODE.height;
		return [
			`M ${x} ${y + TICK_SIZE} V ${y} H ${x + TICK_SIZE}`,
			`M ${right - TICK_SIZE} ${y} H ${right} V ${y + TICK_SIZE}`,
			`M ${x} ${bottom - TICK_SIZE} V ${bottom} H ${x + TICK_SIZE}`,
			`M ${right - TICK_SIZE} ${bottom} H ${right} V ${bottom - TICK_SIZE}`
		];
	};
</script>

<svelte:window onresize={measure} onkeydown={onKeydown} />

{#if interactive}
	<div class="bracket">
		<div
			class="viewport"
			role="group"
			aria-label={m.cup_bracket()}
			class:interactive
			bind:this={viewport}
			onpointerdown={(event) => camera.pointerDown(event)}
			onpointermove={(event) => camera.pointerMove(event)}
			onpointerup={(event) => camera.pointerUp(event)}
			onpointercancel={(event) => camera.pointerUp(event)}
			onclickcapture={swallowDragClick}
			onscroll={absorbScroll}
		>
			<div class="layer" bind:this={layer}>
				<svg
					class="lines"
					viewBox="0 0 {world.width} {world.height}"
					aria-hidden="true"
					focusable="false"
				>
					{#each lines as line (line.from)}
						<path
							class="connector"
							class:known={bracket.known[`${line.to}:${line.side}`]}
							d={line.d}
							vector-effect="non-scaling-stroke"
						/>
					{/each}
					{#each bracket.nodes as node (node.id)}
						{@const at = nodes[node.id]}
						<rect
							class="frame"
							class:final={node.final}
							x={at.x}
							y={at.y}
							width={NODE.width}
							height={NODE.height}
							vector-effect="non-scaling-stroke"
						/>
						{#each ticks(at.x, at.y) as d (d)}
							<path class="tick" {d} vector-effect="non-scaling-stroke" />
						{/each}
						{#if focused === node.id}
							<rect
								class="focus"
								x={at.x}
								y={at.y}
								width={NODE.width}
								height={NODE.height}
								vector-effect="non-scaling-stroke"
							/>
						{/if}
					{/each}
				</svg>
				{#each bracket.nodes as node (node.id)}
					<div class="slot" style:left="{nodes[node.id].x}px" style:top="{nodes[node.id].y}px">
						<BracketNode {node} {level} onOpen={open} onFocusChange={focusChange(node.id)} />
					</div>
				{/each}
				{#if level === 1}
					{#each labels as label, i (i)}
						<span class="round-label" style:left="{label.x}px" style:top="{label.y}px">
							{bracket.rounds[label.key]}
						</span>
					{/each}
					{#if bracket.champion && finalNode}
						<span class="champion" style:left="{champion.x}px" style:top="{champion.y}px">
							<span class="champion-label">{m.cup_champion()}</span>
							{bracket.champion}
						</span>
					{/if}
				{/if}
			</div>
			{#if interactive}
				<div class="controls" role="group" onpointerdown={stopPointer}>
					<div class="levels">
						<button
							type="button"
							class="control"
							aria-pressed={camera.level === 1}
							onclick={() => camera.goToLevel(1)}
						>
							<span class="num">1</span>
							{m.cup_level_1()}
						</button>
						<button
							type="button"
							class="control"
							aria-pressed={camera.level === 2}
							onclick={() => camera.goToLevel(2)}
						>
							<span class="num">2</span>
							{m.cup_level_2()}
						</button>
					</div>
					<div class="zoom">
						<button
							type="button"
							class="control"
							aria-label={m.cup_zoom_in()}
							onclick={() => camera.zoomIn()}
						>
							+
						</button>
						<button
							type="button"
							class="control"
							aria-label={m.cup_zoom_out()}
							onclick={() => camera.zoomOut()}
						>
							−
						</button>
						<button type="button" class="control" onclick={() => camera.fit()}>
							{m.cup_zoom_fit()}
						</button>
					</div>
					<p class="hint">{m.cup_hint()}</p>
				</div>
			{/if}
		</div>
	</div>
{:else}
	<CupBracketTree {bracket} {gameHref} onOpen={open} />
{/if}

{#if matchup.openId !== null}
	<MatchupPanel
		state={panelState}
		{layout}
		{gameHref}
		{playerHref}
		{card}
		onCard={(next) => (card = next)}
		onClose={closePanel}
	/>
{/if}

<style>
	.bracket {
		position: relative;
	}

	.viewport {
		position: relative;
		height: var(--bracket-viewport-height);
		overflow: hidden;
		border: var(--hairline) solid var(--color-divider);
		background: var(--color-bg);
		user-select: none;
	}

	.viewport.interactive {
		touch-action: none;
		cursor: grab;
	}

	.layer {
		position: absolute;
		top: 0;
		left: 0;
		width: var(--bracket-world-width);
		height: var(--bracket-world-height);
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
		stroke: var(--bracket-line-open-color);
		stroke-width: var(--bracket-line-open-width);
		vector-effect: non-scaling-stroke;
	}

	.connector.known {
		stroke: var(--bracket-line-known-color);
		stroke-width: var(--bracket-line-known-width);
	}

	.frame,
	.focus {
		fill: none;
		stroke: var(--color-divider);
		stroke-width: var(--hairline);
		vector-effect: non-scaling-stroke;
	}

	.frame.final {
		stroke: var(--color-accent);
	}

	.focus {
		stroke: var(--color-accent);
		stroke-width: var(--bracket-focus-width);
	}

	.tick {
		fill: none;
		stroke: var(--color-accent);
		stroke-width: var(--hairline);
		vector-effect: non-scaling-stroke;
	}

	.round-label,
	.champion {
		position: absolute;
		transform: translateX(-50%);
		font-family: var(--font-heading);
		white-space: nowrap;
		pointer-events: none;
	}

	.round-label {
		font-size: var(--bracket-round-label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	.champion {
		display: grid;
		justify-items: center;
		font-size: var(--bracket-champion-size);
		color: var(--color-ink);
	}

	.champion-label {
		font-size: var(--bracket-round-label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-accent-light);
	}

	.controls {
		position: absolute;
		inset: 0;
		display: grid;
		grid-template-columns: 1fr auto;
		grid-template-rows: auto 1fr;
		padding: var(--day-strip-gap);
		pointer-events: none;
	}

	.levels,
	.zoom {
		display: flex;
		gap: var(--hairline);
		pointer-events: auto;
	}

	.levels {
		grid-area: 1 / 1;
		justify-self: start;
	}

	.zoom {
		grid-area: 1 / 2;
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

	.hint {
		grid-area: 2 / 1 / 3 / 3;
		align-self: end;
		margin: 0;
		font-size: var(--caption-size);
		color: var(--color-muted);
	}
</style>
