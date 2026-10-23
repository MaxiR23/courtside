// Hrefs into the playoffs routes, shared by the pages that link to a series.
import { resolve } from '$app/paths';
import type { ResolvedPathname } from '$app/types';
import type { SeriesId } from '#lib/contract/playoffs.ts';

/** The full series page. A past season keeps `season`; the current season (null) has none. */
export function seriesHref(id: SeriesId, season: number | null): ResolvedPathname {
	return season === null
		? resolve(`/playoffs/series?id=${id}`)
		: resolve(`/playoffs/series?id=${id}&season=${season}`);
}

/** The bracket section of /playoffs, same season. */
export function bracketHref(season: number | null): ResolvedPathname {
	return season === null
		? resolve('/playoffs#bracket')
		: resolve(`/playoffs?season=${season}#bracket`);
}
