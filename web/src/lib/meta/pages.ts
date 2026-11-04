import { pageTitle } from '#lib/format/title.ts';
import { m } from '#lib/paraglide/messages.js';

export type PrerenderedPage = {
	title: () => string;
	description: () => string;
	/** Whether the page is listed in sitemap.xml and has a canonical address of its own. */
	inSitemap: boolean;
};

/**
 * The pages the build writes a file for. The title is the one the route shows while it loads.
 * /playoffs/series is a page of its own only with an id in its query, so it is not listed.
 * Removing a seasonal section also removes its entry here.
 */
export const prerenderedPages = {
	'/': { title: () => pageTitle(), description: () => m.meta_description_home(), inSitemap: true },
	'/standings': {
		title: () => pageTitle(m.standings_title()),
		description: () => m.meta_description_standings(),
		inSitemap: true
	},
	'/cup': {
		title: () => pageTitle(m.cup_title()),
		description: () => m.meta_description_cup(),
		inSitemap: true
	},
	'/playoffs': {
		title: () => pageTitle(m.playoffs_title()),
		description: () => m.meta_description_playoffs(),
		inSitemap: true
	},
	'/playoffs/series': {
		title: () => pageTitle(m.playoffs_title()),
		description: () => m.meta_description_series(),
		inSitemap: false
	},
	'/all-star': {
		title: () => pageTitle(m.allstar_title()),
		description: () => m.meta_description_all_star(),
		inSitemap: true
	},
	'/all-star/previous': {
		title: () => pageTitle(m.allstar_title()),
		description: () => m.meta_description_all_star(),
		inSitemap: true
	}
} as const satisfies Record<string, PrerenderedPage>;

export type PrerenderedPath = keyof typeof prerenderedPages;

/** The paths sitemap.xml lists, in the table's order. */
export function sitemapPaths(): PrerenderedPath[] {
	return (Object.keys(prerenderedPages) as PrerenderedPath[]).filter(
		(path) => prerenderedPages[path].inSitemap
	);
}
