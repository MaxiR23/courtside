<script lang="ts">
	import AllStarLiveDot from '#lib/components/AllStarLiveDot.svelte';
	import AllStarSigla from '#lib/components/AllStarSigla.svelte';
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import PlayerAvatar from '#lib/components/PlayerAvatar.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { LiveTick } from '#lib/all-star/live-tick.svelte.ts';
	import type { PlateView } from '#lib/all-star/types.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { RowLayout } from '#lib/schedule/types.ts';
	import Kicker from '#lib/components/Kicker.svelte';
	import Tag from '#lib/components/Tag.svelte';

	type Props = {
		plate: PlateView;
		layout: RowLayout;
		tick: LiveTick;
		onLive: (gameId: string) => void; // the live scoreboard of the mobile hero was tapped
	};

	type LivePlate = Extract<PlateView, { kind: 'live' }>;

	let { plate, layout, tick, onLive }: Props = $props();

	// The live clock is re-read from the latest feed value every second; nothing counts down.
	const clock = $derived.by(() => {
		void tick.tick;
		return plate.kind === 'live' ? plate.clock : '';
	});
	const mobile = $derived(layout === 'mobile');
</script>

{#snippet liveBoard(view: LivePlate)}
	<Kicker contents
		><span class="live-head">
			<AllStarLiveDot />
			<span class="live-title">{view.header}</span>
			{#if view.formatLine}<span class="format">{view.formatLine}</span>{/if}
		</span></Kicker
	>
	<span class="live-rows">
		{#each view.rows as row, i (i)}
			<span class="live-row" class:loser={row.loser}>
				<AllStarSigla team={row.team} size="large" winner={row.winner} />
				<span class="live-name">
					{#if row.team}<TeamMark team={row.team} part="name" />{:else}{row.name}{/if}
				</span>
				<span class="live-score">{row.score}</span>
			</span>
		{/each}
	</span>
	<span class="live-foot">
		<span class="clock">{clock}</span>
		{#if view.status}<Kicker tone="muted" contents><span class="status">{view.status}</span></Kicker
			>{/if}
		{#if view.next}<Kicker tone="muted" contents><span class="next">{view.next}</span></Kicker>{/if}
	</span>
{/snippet}

<div class="plate-wrap" class:mobile>
	{#if plate.kind === 'mvp'}
		{#if mobile}
			<a class="mvp-thumb" href="#mvp">
				<BlueprintFrame marks="allstar">
					<span class="thumb-body">
						<PlayerAvatar name={plate.name} photo={plate.photo} size="allstar-plate" />
						<span class="mvp-tag"
							><Tag text={m.allstar_mvp_tag()} variant="solid" borderless /></span
						>
					</span>
				</BlueprintFrame>
			</a>
		{:else}
			<BlueprintFrame marks="allstar">
				<div class="plate mvp">
					{#if plate.jersey}<span class="watermark" aria-hidden="true">{plate.jersey}</span>{/if}
					<span class="photo"
						><PlayerAvatar name={plate.name} photo={plate.photo} size="allstar-plate" /></span
					>
					<Kicker contents><span class="label top-left">{m.allstar_mvp_label()}</span></Kicker>
					<Kicker contents><span class="label top-right">{plate.labels}</span></Kicker>
					<span class="bottom">
						<span class="plate-name">{plate.name}</span>
						<Tag text={m.allstar_mvp_tag()} variant="solid" borderless />
					</span>
				</div>
			</BlueprintFrame>
		{/if}
	{:else if plate.kind === 'score'}
		<BlueprintFrame marks="allstar">
			<div class="plate score">
				<span class="score-rows">
					{#each plate.rows as row, i (i)}
						<span class="score-row" class:loser={row.loser}>
							<span class="score-name">
								{#if row.team}<TeamMark team={row.team} part="name" />{:else}{row.name}{/if}
							</span>
							<span class="score-value" class:winner={row.winner}>{row.score}</span>
						</span>
					{/each}
				</span>
			</div>
		</BlueprintFrame>
	{:else if plate.kind === 'live'}
		{#if mobile}
			<BlueprintFrame marks="allstar">
				<button type="button" class="live-block" onclick={() => onLive(plate.gameId)}>
					{@render liveBoard(plate)}
				</button>
			</BlueprintFrame>
		{:else}
			<BlueprintFrame marks="allstar">
				<div class="plate live">
					{@render liveBoard(plate)}
				</div>
			</BlueprintFrame>
		{/if}
	{:else if plate.kind === 'tipoff'}
		<BlueprintFrame marks="allstar">
			<div class="plate tipoff">
				<span class="tipoff-text">{plate.text}</span>
			</div>
		</BlueprintFrame>
	{:else}
		<div class="plate year">
			<span class="circle outer" aria-hidden="true"></span>
			<span class="circle inner" aria-hidden="true"></span>
			<span class="numeral">{plate.year ?? '—'}</span>
		</div>
	{/if}
</div>

<style>
	.plate-wrap {
		width: 100%;
		max-width: var(--allstar-plate-max-width);
		min-width: 0;
	}

	.plate-wrap.mobile {
		max-width: none;
	}

	.plate {
		position: relative;
		overflow: hidden;
		aspect-ratio: var(--playoffs-plate-ratio);
		background: var(--color-frame-fill);
	}

	.plate.mvp {
		background:
			radial-gradient(ellipse at 50% 100%, var(--allstar-plate-glow), transparent 70%),
			var(--color-frame-fill);
	}

	.watermark {
		position: absolute;
		inset: 0;
		display: grid;
		place-items: center;
		font-family: var(--font-heading);
		font-size: var(--hero-watermark-size);
		color: var(--allstar-watermark-ink);
		line-height: 1;
		pointer-events: none;
	}

	.photo {
		position: absolute;
		right: 0;
		bottom: 0;
		left: 0;
		display: block;
		height: 100%;
	}

	.photo :global(.avatar) {
		position: absolute;
		bottom: 0;
	}

	.label {
		position: absolute;
		top: var(--game-list-gap);
	}

	.top-left {
		left: var(--game-list-gap);
	}

	.top-right {
		right: var(--game-list-gap);
	}

	.bottom {
		position: absolute;
		right: var(--game-list-gap);
		bottom: var(--game-list-gap);
		left: var(--game-list-gap);
		display: flex;
		align-items: flex-end;
		justify-content: space-between;
		gap: var(--game-list-gap);
	}

	.plate-name {
		font-family: var(--font-heading);
		font-size: var(--allstar-mvp-name-size);
		line-height: var(--allstar-hero-title-leading);
		text-transform: uppercase;
	}

	.mvp-thumb {
		display: block;
		width: var(--allstar-mvp-thumb-width);
		color: inherit;
		text-decoration: none;
	}

	.thumb-body {
		position: relative;
		display: block;
		height: var(--allstar-mvp-thumb-height);
		overflow: hidden;
		background: var(--color-frame-fill);
	}

	.thumb-body .mvp-tag {
		position: absolute;
		bottom: var(--day-strip-gap);
		left: var(--day-strip-gap);
		display: flex;
	}

	.thumb-body :global(.avatar) {
		position: absolute;
		bottom: 0;
		height: 100%;
	}

	.thumb-body :global(.avatar img) {
		object-fit: cover;
		object-position: top center;
	}

	.plate.score {
		display: grid;
		align-content: center;
		padding: var(--panel-section-gap);
	}

	.score-rows {
		display: grid;
		gap: var(--game-list-gap);
	}

	.score-row {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: var(--game-list-gap);
	}

	.score-row.loser {
		color: var(--color-muted);
	}

	.score-name {
		font-family: var(--font-heading);
		font-size: var(--allstar-team-name-size);
	}

	.score-value {
		font-family: var(--font-heading);
		font-size: var(--allstar-score-size);
		font-variant-numeric: tabular-nums;
	}

	.score-value.winner {
		color: var(--color-accent-light);
	}

	.plate.live,
	.live-block {
		display: grid;
		align-content: space-between;
		gap: var(--game-list-gap);
		padding: var(--panel-section-gap);
		background-image:
			linear-gradient(var(--color-grid-line) var(--hairline), transparent var(--hairline)),
			linear-gradient(90deg, var(--color-grid-line) var(--hairline), transparent var(--hairline));
		background-color: var(--color-frame-fill);
		background-size: var(--allstar-plate-grid-size) var(--allstar-plate-grid-size);
	}

	.live-block {
		width: 100%;
		border: 0;
		font: inherit;
		color: inherit;
		text-align: left;
		cursor: pointer;
	}

	.live-head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--day-strip-gap);
	}

	.format {
		margin-inline-start: auto;
		color: var(--color-muted);
	}

	.live-rows {
		display: grid;
		gap: var(--game-list-gap);
	}

	.live-row {
		display: flex;
		align-items: center;
		gap: var(--game-list-gap);
	}

	.live-row.loser {
		color: var(--color-muted);
	}

	.live-name {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		font-family: var(--font-heading);
		font-size: var(--allstar-team-name-size);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.live-score {
		font-family: var(--font-heading);
		font-size: var(--allstar-live-score-size);
		font-variant-numeric: tabular-nums;
		line-height: 1;
	}

	.mobile .live-score {
		font-size: var(--allstar-live-score-size-mobile);
	}

	.live-foot {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--game-list-gap);
	}

	.clock {
		font-family: var(--font-heading);
		font-size: var(--allstar-live-clock-size);
		font-variant-numeric: tabular-nums;
		color: var(--color-accent-light);
	}

	.mobile .clock {
		font-size: var(--allstar-live-clock-size-mobile);
	}

	.next {
		margin-inline-start: auto;
	}

	.plate.tipoff {
		display: grid;
		place-items: center;
	}

	.tipoff-text {
		font-family: var(--font-heading);
		font-size: var(--allstar-team-name-size);
		text-transform: uppercase;
		color: var(--color-accent-light);
	}

	.plate.year {
		display: grid;
		place-items: center;
		background: none;
	}

	.circle {
		position: absolute;
		top: 50%;
		left: 50%;
		translate: -50% -50%;
		aspect-ratio: 1;
		border: var(--hairline) dashed var(--color-divider);
		border-radius: 50%;
	}

	.circle.outer {
		width: 90%;
	}

	.circle.inner {
		width: 62%;
	}

	.numeral {
		position: relative;
		font-family: var(--font-heading);
		font-size: var(--allstar-year-size);
		line-height: 1;
		color: transparent;
		-webkit-text-stroke: var(--allstar-year-stroke) var(--color-accent-light);
	}

	.mobile .numeral {
		font-size: var(--allstar-year-size-mobile);
	}
</style>
