// Views of the recorded All-Star feeds for the component tests, and the link builders the routes pass.
import type { ResolvedPathname } from '$app/types';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import type { AllStarView } from '../../../src/lib/all-star/types';
import type { AllStarFeed } from '../../../src/lib/contract/all-star';
import { toAllStarView } from '../../../src/lib/feed/all-star-props';

export const feedOf = (name: 'before' | 'live' | 'after'): AllStarFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', `all-star-${name}.json`), 'utf8')
	);

export const viewOf = (
	name: 'before' | 'live' | 'after',
	which: 'current' | 'previous' = 'current'
): AllStarView => toAllStarView(feedOf(name), which)!;

export const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;
export const playerHref = (id: string) => `/player/${id}` as ResolvedPathname;
