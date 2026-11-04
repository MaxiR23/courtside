import { m } from '#lib/paraglide/messages.js';

/** The Open Graph image: a file in web/static, 1200 by 630. */
export const OG_IMAGE_PATH = '/og-image.png';
export const OG_IMAGE_WIDTH = 1200;
export const OG_IMAGE_HEIGHT = 630;

/** Marks the tags the server hook writes into a browser-rendered page's file. */
export const SHELL_MARK = 'data-shell-meta';

export type HeadTag = { tag: 'meta' | 'link'; attributes: Record<string, string> };

export type HeadInput = {
	title: string;
	description: string;
	/** The page's pathname and the query it reads, or null when the page has no canonical address. */
	path: string | null;
	/** The site's absolute origin, or undefined when the build has none. */
	siteUrl: string | undefined;
	locale: string;
};

const OG_LOCALES: Record<string, string> = { en: 'en_US', es: 'es_ES' };

/** The Open Graph locale of a language tag: `en` gives `en_US`, `es` gives `es_ES`. */
export function ogLocale(locale: string): string {
	return OG_LOCALES[locale] ?? locale;
}

/** The address a page answers at: its pathname, then only the listed query parameters it has. */
export function canonicalPath(
	url: { pathname: string; searchParams: Iterable<[string, string]> },
	keys: readonly string[]
): string {
	const kept = new URLSearchParams();
	for (const [key, value] of url.searchParams) {
		if (keys.includes(key)) kept.append(key, value);
	}
	const query = kept.toString();
	return query ? `${url.pathname}?${query}` : url.pathname;
}

/** The absolute address of a path that starts with a slash. */
export function absoluteUrl(siteUrl: string, path: string): string {
	return siteUrl + path;
}

/** Every head tag of a page, in a stable order. The title is the document title, drawn apart. */
export function headTags({ title, description, path, siteUrl, locale }: HeadInput): HeadTag[] {
	const address = siteUrl && path ? absoluteUrl(siteUrl, path) : null;
	const tags: (HeadTag | null)[] = [
		{ tag: 'meta', attributes: { name: 'description', content: description } },
		address ? { tag: 'link', attributes: { rel: 'canonical', href: address } } : null,
		{ tag: 'meta', attributes: { property: 'og:type', content: 'website' } },
		{ tag: 'meta', attributes: { property: 'og:site_name', content: m.site_name() } },
		{ tag: 'meta', attributes: { property: 'og:title', content: title } },
		{ tag: 'meta', attributes: { property: 'og:description', content: description } },
		address ? { tag: 'meta', attributes: { property: 'og:url', content: address } } : null,
		{
			tag: 'meta',
			attributes: {
				property: 'og:image',
				content: siteUrl ? absoluteUrl(siteUrl, OG_IMAGE_PATH) : OG_IMAGE_PATH
			}
		},
		{
			tag: 'meta',
			attributes: { property: 'og:image:width', content: String(OG_IMAGE_WIDTH) }
		},
		{
			tag: 'meta',
			attributes: { property: 'og:image:height', content: String(OG_IMAGE_HEIGHT) }
		},
		{ tag: 'meta', attributes: { property: 'og:image:alt', content: m.meta_image_alt() } },
		{ tag: 'meta', attributes: { property: 'og:locale', content: ogLocale(locale) } },
		{ tag: 'meta', attributes: { name: 'twitter:card', content: 'summary_large_image' } }
	];
	return tags.filter((tag): tag is HeadTag => tag !== null);
}

/** The attribute that identifies a tag, for a keyed list. */
export function tagKey(tag: HeadTag): string {
	const { name, property, rel } = tag.attributes;
	return `${tag.tag}:${name ?? property ?? rel}`;
}

function escapeAttribute(value: string): string {
	return value
		.replaceAll('&', '&amp;')
		.replaceAll('<', '&lt;')
		.replaceAll('>', '&gt;')
		.replaceAll('"', '&quot;');
}

function escapeText(value: string): string {
	return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
}

/** The title and the tags as HTML for a file the browser fills in; every tag but the title is marked. */
export function shellHead({ title, tags }: { title: string; tags: HeadTag[] }): string {
	const rendered = tags.map(({ tag, attributes }) => {
		const attrs = Object.entries(attributes)
			.map(([key, value]) => `${key}="${escapeAttribute(value)}"`)
			.join(' ');
		return `<${tag} ${attrs} ${SHELL_MARK}>`;
	});
	return [`<title>${escapeText(title)}</title>`, ...rendered].join('\n\t\t');
}
