<script lang="ts">
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import Kicker from '#lib/components/Kicker.svelte';
	import PlayerAvatar from '#lib/components/PlayerAvatar.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import type { FinalsMvpView } from '#lib/playoffs/types.ts';
	import type { RowLayout } from '#lib/schedule/types.ts';

	type Props = { mvp: NonNullable<FinalsMvpView>; layout?: RowLayout };

	let { mvp, layout = 'desktop' }: Props = $props();
</script>

<BlueprintFrame>
	<div class="finals-mvp" class:mobile={layout === 'mobile'}>
		<div class="photo" style:--side-accent={mvp.accent ?? 'var(--identity-neutral-accent)'}>
			<span class="glow" aria-hidden="true"></span>
			<PlayerAvatar name={mvp.name} photo={mvp.photo} size="playoffs-mvp" clip="bottom" />
		</div>
		<div class="info">
			<Kicker text={m.playoffs_finals_mvp()} />
			<span class="name">{mvp.name}</span>
			<span class="team">
				<TeamMark team={mvp.mark} part="tile" size="playoffs-mvp-team" logo={mvp.mark.logo} />
				{mvp.teamName}
			</span>
			<dl class="stats">
				{#each mvp.stats as stat (stat.key)}
					<div class="stat" class:accent={stat.accent}>
						<dt>{stat.label}</dt>
						<dd>{stat.value}</dd>
					</div>
				{/each}
			</dl>
		</div>
	</div>
</BlueprintFrame>

<style>
	.finals-mvp {
		display: grid;
		grid-template-columns: var(--playoffs-mvp-photo-columns);
		height: 100%;
	}

	.finals-mvp.mobile {
		grid-template-columns: var(--playoffs-mvp-photo-columns-mobile);
	}

	.photo {
		position: relative;
		min-height: var(--playoffs-mvp-photo-min-height);
		overflow: hidden;
	}

	.glow {
		position: absolute;
		inset: 0;
		background: radial-gradient(
			circle at var(--playoffs-mvp-glow-position),
			var(--side-accent),
			transparent var(--playoffs-mvp-glow-falloff)
		);
		opacity: var(--playoffs-hero-glow-alpha);
		pointer-events: none;
	}

	.info {
		display: flex;
		flex-direction: column;
		justify-content: space-between;
		min-width: 0;
		padding: var(--playoffs-mvp-info-padding);
		border-left: var(--hairline) solid var(--color-divider);
	}

	.mobile .info {
		border-left: 0;
		border-top: var(--hairline) solid var(--color-divider);
	}

	.name {
		font-family: var(--font-heading);
		font-weight: var(--font-weight-bold);
		font-size: var(--playoffs-mvp-name-size);
		text-transform: uppercase;
	}

	.team {
		display: flex;
		align-items: center;
		gap: var(--identity-inline-mark-gap);
		font-size: var(--playoffs-mvp-team-size);
		color: var(--color-muted);
	}

	.stats {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: var(--playoffs-mvp-stats-gap);
		margin: 0;
	}

	.stat {
		display: flex;
		flex-direction: column-reverse;
	}

	dt {
		font-size: var(--playoffs-mvp-stat-label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-muted);
	}

	dd {
		margin: 0;
		font-family: var(--font-heading);
		font-size: var(--playoffs-mvp-stat-value-size);
		font-variant-numeric: tabular-nums;
	}

	.stat.accent dd {
		color: var(--color-accent-light);
	}
</style>
