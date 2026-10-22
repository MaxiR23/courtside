<script lang="ts">
	import type { ResolvedPathname } from '$app/types';

	type Props = {
		code: string;
		size:
			| 'large'
			| 'small'
			| 'header'
			| 'header-mobile'
			| 'injury'
			| 'team'
			| 'standings'
			| 'search'
			| 'cup-draw'
			| 'cup-champion'
			| 'playoffs-champion'
			| 'cup-node'
			| 'allstar-league'
			| 'names'
			| 'fill'; // the whole box of the parent
		href?: ResolvedPathname;
		logo?: string | null; // an image URL drawn in the box in place of the code; null or absent: the code
		onlogoerror?: () => void;
	};

	let { code, size, href, logo = null, onlogoerror }: Props = $props();
</script>

{#if href}
	<a class="team-monogram {size} linked" class:logo={logo !== null} {href}
		>{#if logo !== null}<img src={logo} alt={code} onerror={onlogoerror} />{:else}{code}{/if}</a
	>
{:else}
	<span class="team-monogram {size}" class:logo={logo !== null}
		>{#if logo !== null}<img src={logo} alt="" onerror={onlogoerror} />{:else}{code}{/if}</span
	>
{/if}

<style>
	.team-monogram {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		border: var(--hairline) solid var(--color-divider);
		border-radius: var(--radius);
		font-family: var(--font-heading);
		font-weight: var(--font-weight-semibold);
		font-size: var(--body-size);
	}

	.logo {
		border-color: transparent;
	}

	.logo img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: contain;
	}

	.linked {
		color: inherit;
		text-decoration: none;
	}

	.linked:hover {
		border-color: var(--color-accent);
	}

	.large {
		width: var(--monogram-size);
		height: var(--monogram-size);
	}

	.small {
		width: var(--monogram-size-mobile);
		height: var(--monogram-size-mobile);
	}

	.header {
		width: var(--detail-monogram-size);
		height: var(--detail-monogram-size);
	}

	.injury {
		width: var(--injury-monogram-size);
		height: var(--injury-monogram-size);
	}

	.team {
		width: var(--team-code-box-size);
		height: var(--team-code-box-size);
	}

	.standings {
		width: var(--standings-monogram-size);
		height: var(--standings-monogram-size);
	}

	.search {
		width: var(--search-tile-size);
		height: var(--search-tile-size);
		border-radius: var(--search-tile-radius);
	}

	.cup-draw {
		width: var(--cup-group-mark);
		height: var(--cup-group-mark);
	}

	.cup-champion {
		width: var(--cup-champion-mark);
		height: var(--cup-champion-mark);
		border-color: var(--color-accent);
	}

	.playoffs-champion {
		width: var(--playoffs-champion-mark);
		height: var(--playoffs-champion-mark);
		border-color: var(--color-accent);
	}

	.cup-node {
		width: var(--bracket-tile-size);
		height: var(--bracket-tile-size);
		font-size: var(--bracket-meta-size);
	}

	.names {
		width: var(--past-sigla-width);
		height: var(--past-sigla-height);
	}

	.allstar-league {
		width: var(--allstar-box-monogram-size);
		height: var(--allstar-box-monogram-size);
	}

	.fill {
		width: 100%;
		height: 100%;
	}

	.header-mobile {
		width: var(--detail-monogram-size-mobile);
		height: var(--detail-monogram-size-mobile);
	}
</style>
