<script lang="ts">
	// An original line drawing in the blueprint style: a cup on a stepped base, two handles,
	// thin construction lines and small tick marks. Lines only: no fill, no text, no name,
	// no dimensions and no materials. It is not a copy of any real trophy.
	type Props = { title: string };

	let { title }: Props = $props();
</script>

<svg class="trophy" viewBox="0 0 100 140" role="img" preserveAspectRatio="xMidYMid meet">
	<title>{title}</title>
	<!-- construction lines -->
	<line class="thin" x1="50" y1="4" x2="50" y2="136" vector-effect="non-scaling-stroke" />
	<line class="thin" x1="8" y1="70" x2="92" y2="70" vector-effect="non-scaling-stroke" />
	<!-- bowl -->
	<path d="M 26 18 L 74 18 L 68 62 Q 50 82 32 62 Z" vector-effect="non-scaling-stroke" />
	<path d="M 26 26 L 74 26" vector-effect="non-scaling-stroke" />
	<!-- handles -->
	<path d="M 27 24 C 6 24 6 56 33 58" vector-effect="non-scaling-stroke" />
	<path d="M 73 24 C 94 24 94 56 67 58" vector-effect="non-scaling-stroke" />
	<!-- stem -->
	<polyline points="46 76 46 106 54 106 54 76" vector-effect="non-scaling-stroke" />
	<line x1="44" y1="92" x2="56" y2="92" vector-effect="non-scaling-stroke" />
	<!-- stepped base -->
	<polyline points="34 106 66 106 66 114 34 114 34 106" vector-effect="non-scaling-stroke" />
	<polyline points="28 114 72 114 72 122 28 122 28 114" vector-effect="non-scaling-stroke" />
	<polyline points="22 122 78 122 78 130 22 130 22 122" vector-effect="non-scaling-stroke" />
	<!-- tick marks -->
	<line class="thin" x1="4" y1="18" x2="10" y2="18" vector-effect="non-scaling-stroke" />
	<line class="thin" x1="90" y1="18" x2="96" y2="18" vector-effect="non-scaling-stroke" />
	<line class="thin" x1="4" y1="130" x2="10" y2="130" vector-effect="non-scaling-stroke" />
	<line class="thin" x1="90" y1="130" x2="96" y2="130" vector-effect="non-scaling-stroke" />
</svg>

<style>
	.trophy {
		display: block;
		width: 100%;
		height: 100%;
	}

	path,
	line,
	polyline {
		fill: none;
		stroke: var(--color-accent-light);
		stroke-width: var(--playoffs-trophy-stroke);
		vector-effect: non-scaling-stroke;
	}

	.thin {
		stroke: var(--color-divider);
	}
</style>
