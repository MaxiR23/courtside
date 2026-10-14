// World geometry of the playoffs bracket: where the 15 series cards sit, the connectors between
// them, the games list under a card and the champion anchor, for the desktop world, and the
// stacked order of the mobile rounds. Pure, in world units. The sizes mirror the --playoffs-*
// tokens; tests/lib/playoffs/bracket-layout.test.ts pins them.

import type { Rect, Size } from '#lib/bracket/camera.ts';
import { elbowPath, type Point } from '#lib/bracket/geometry.ts';
import type { SeriesId } from '#lib/contract/playoffs.ts';

export const WORLD: Size = { width: 1400, height: 650 };
export const COLUMN_WIDTH = 176;
export const COLUMN_STEP = 204;
export const ROW_HEIGHT = 33;
export const CARD: Size = { width: COLUMN_WIDTH, height: 2 * ROW_HEIGHT };
export const GAME_ROW = 8;
export const GAMES_GAP = 4;
export const SERIES_ZOOM_MAX = 4.4;

// Plan choices, not in the design.
export const FIT_MARGIN = 20;
export const SERIES_MARGIN = 12;
export const CHAMPION_GAP = 8;

export const SERIES_IDS: SeriesId[] = [
	'east-r1-1',
	'east-r1-2',
	'east-r1-3',
	'east-r1-4',
	'east-r2-1',
	'east-r2-2',
	'east-r3',
	'finals',
	'west-r3',
	'west-r2-1',
	'west-r2-2',
	'west-r1-1',
	'west-r1-2',
	'west-r1-3',
	'west-r1-4'
];

// Column (0 to 6) and row center of each series.
const PLACE: Record<SeriesId, { column: number; center: number }> = {
	'east-r1-1': { column: 0, center: 105 },
	'east-r1-2': { column: 0, center: 235 },
	'east-r1-3': { column: 0, center: 365 },
	'east-r1-4': { column: 0, center: 495 },
	'east-r2-1': { column: 1, center: 170 },
	'east-r2-2': { column: 1, center: 430 },
	'east-r3': { column: 2, center: 300 },
	finals: { column: 3, center: 300 },
	'west-r3': { column: 4, center: 300 },
	'west-r2-1': { column: 5, center: 170 },
	'west-r2-2': { column: 5, center: 430 },
	'west-r1-1': { column: 6, center: 105 },
	'west-r1-2': { column: 6, center: 235 },
	'west-r1-3': { column: 6, center: 365 },
	'west-r1-4': { column: 6, center: 495 }
};

/** The top-left of each series card. */
export const SERIES_AT = Object.fromEntries(
	SERIES_IDS.map((id) => [
		id,
		{ x: PLACE[id].column * COLUMN_STEP, y: PLACE[id].center - CARD.height / 2 }
	])
) as Record<SeriesId, Point>;

export type Connector = { from: SeriesId; to: SeriesId; d: string };

// The feed's placement rule: round 1 series 1 and 2 feed round 2 series 1, 3 and 4 feed series 2,
// the two round 2 series feed the conference finals, and both conference finals feed the Finals.
const FEEDERS: { from: SeriesId; to: SeriesId }[] = [
	{ from: 'east-r1-1', to: 'east-r2-1' },
	{ from: 'east-r1-2', to: 'east-r2-1' },
	{ from: 'east-r1-3', to: 'east-r2-2' },
	{ from: 'east-r1-4', to: 'east-r2-2' },
	{ from: 'east-r2-1', to: 'east-r3' },
	{ from: 'east-r2-2', to: 'east-r3' },
	{ from: 'east-r3', to: 'finals' },
	{ from: 'west-r1-1', to: 'west-r2-1' },
	{ from: 'west-r1-2', to: 'west-r2-1' },
	{ from: 'west-r1-3', to: 'west-r2-2' },
	{ from: 'west-r1-4', to: 'west-r2-2' },
	{ from: 'west-r2-1', to: 'west-r3' },
	{ from: 'west-r2-2', to: 'west-r3' },
	{ from: 'west-r3', to: 'finals' }
];

const isWest = (id: SeriesId): boolean => id.startsWith('west');

/** The 14 orthogonal connectors, each from the facing edge of its feeder to the card it feeds. */
export function connectors(): Connector[] {
	return FEEDERS.map(({ from, to }) => ({
		from,
		to,
		d: elbowPath(SERIES_AT[from], SERIES_AT[to], CARD, isWest(from))
	}));
}

/** The card plus, when the series has games, the list under it. */
export function seriesRect(id: SeriesId, games: number): Rect {
	const at = SERIES_AT[id];
	const list = games > 0 ? GAMES_GAP + games * GAME_ROW : 0;
	return { x: at.x, y: at.y, width: CARD.width, height: CARD.height + list };
}

/** The top-left of the games list under a card. */
export function gamesAt(id: SeriesId): Point {
	const at = SERIES_AT[id];
	return { x: at.x, y: at.y + CARD.height + GAMES_GAP };
}

/** The bottom center of the Champion label: centered above the Finals card. */
export function championAt(): Point {
	const at = SERIES_AT.finals;
	return { x: at.x + CARD.width / 2, y: at.y - CHAMPION_GAP };
}

/** The next or previous series in bracket order, wrapping. With none selected: the first, or the last. */
export function step(current: SeriesId | null, dir: 1 | -1): SeriesId {
	const last = SERIES_IDS.length - 1;
	if (current === null) return SERIES_IDS[dir === 1 ? 0 : last];
	const index = SERIES_IDS.indexOf(current) + dir;
	return SERIES_IDS[(index + SERIES_IDS.length) % SERIES_IDS.length];
}

/** The mobile rounds, stacked: East round 1, round 2, conference finals, Finals, then West. */
export const MOBILE_GROUPS: SeriesId[][] = [
	['east-r1-1', 'east-r1-2', 'east-r1-3', 'east-r1-4'],
	['east-r2-1', 'east-r2-2'],
	['east-r3'],
	['finals'],
	['west-r3'],
	['west-r2-1', 'west-r2-2'],
	['west-r1-1', 'west-r1-2', 'west-r1-3', 'west-r1-4']
];
