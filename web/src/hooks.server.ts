import type { Handle } from '@sveltejs/kit/hooks';
import { siteUrl } from '#lib/feed/config.ts';
import { headTags, shellHead } from '#lib/meta/head.ts';
import { prerenderedPages, type PrerenderedPath } from '#lib/meta/pages.ts';
import { getTextDirection } from '#lib/paraglide/runtime.js';
import { paraglideMiddleware } from '#lib/paraglide/server.js';

/**
 * The head tags for a file the browser fills in: the build writes no component head into the
 * pages that turn off server rendering, nor into the fallback page, so a link preview that runs
 * no script would find no title. The fallback answers many addresses, so it gets the home's
 * wording and no canonical address. PageMeta removes these tags once it draws its own.
 */
function shellTags(pathname: string, locale: string): string {
	const known = pathname in prerenderedPages;
	const entry = prerenderedPages[known ? (pathname as PrerenderedPath) : '/'];
	const title = entry.title();
	const description = entry.description();
	const path = known && entry.inSitemap ? pathname : null;
	return shellHead({ title, tags: headTags({ title, description, path, siteUrl, locale }) });
}

const handleParaglide: Handle = ({ event, resolve }) =>
	paraglideMiddleware(event.request, ({ request, locale }) => {
		return resolve(
			{ ...event, request },
			{
				transformPageChunk: ({ html }) => {
					const page = html
						.replace('%paraglide.lang%', locale)
						.replace('%paraglide.dir%', getTextDirection(locale));
					return page.includes('</head>') && !page.includes('<title>')
						? page.replace('</head>', () => `${shellTags(event.url.pathname, locale)}\n</head>`)
						: page;
				}
			}
		);
	});

export const handle: Handle = handleParaglide;
