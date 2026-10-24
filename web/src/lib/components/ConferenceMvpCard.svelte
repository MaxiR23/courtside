<script lang="ts">
	import BlueprintFrame from '#lib/components/BlueprintFrame.svelte';
	import PlayerAvatar from '#lib/components/PlayerAvatar.svelte';
	import TeamMark from '#lib/components/TeamMark.svelte';
	import type { ConferenceMvpView } from '#lib/playoffs/types.ts';

	type Props = { mvp: ConferenceMvpView };

	let { mvp }: Props = $props();
</script>

<BlueprintFrame>
	<div class="conference-mvp">
		<div class="photo" style:--side-accent={mvp.accent ?? 'var(--identity-neutral-accent)'}>
			<span class="glow" aria-hidden="true"></span>
			<PlayerAvatar name={mvp.name} photo={mvp.photo} size="playoffs-conference-mvp" />
		</div>
		<div class="who">
			<span class="label">{mvp.label}</span>
			<span class="name">{mvp.name}</span>
			<span class="team">{mvp.teamName}</span>
		</div>
		<span class="logo">
			<TeamMark team={mvp.mark} part="tile" size="playoffs-mvp-logo" logo={mvp.mark.logo} />
		</span>
	</div>
</BlueprintFrame>

<style>
	.conference-mvp {
		display: grid;
		grid-template-columns: var(--playoffs-conf-columns);
		align-items: center;
		height: 100%;
	}

	.photo {
		position: relative;
		align-self: stretch;
		min-height: var(--playoffs-conf-photo-min-height);
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
		opacity: var(--playoffs-conf-glow-alpha);
		pointer-events: none;
	}

	.who {
		display: grid;
		min-width: 0;
	}

	.label {
		font-size: var(--playoffs-conf-label-size);
		letter-spacing: var(--label-letter-spacing);
		text-transform: uppercase;
		color: var(--color-accent-light);
	}

	.name {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-family: var(--font-heading);
		font-weight: var(--font-weight-bold);
		font-size: var(--playoffs-conf-name-size);
		text-transform: uppercase;
	}

	.team {
		font-size: var(--playoffs-conf-team-size);
		color: var(--color-muted);
	}

	.logo {
		margin-right: var(--playoffs-conf-logo-margin);
	}
</style>
