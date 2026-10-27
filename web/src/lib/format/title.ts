import { m } from '#lib/paraglide/messages.js';

const SEPARATOR = ' · ';

/** The document title: the given parts, then the site name. With no part, the site name alone. */
export function pageTitle(...parts: (string | null | undefined)[]): string {
	return [...parts.filter((part): part is string => !!part?.trim()), m.site_name()].join(SEPARATOR);
}
