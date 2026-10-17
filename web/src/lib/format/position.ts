// The name of a player position in the page language. The feeds send English position names
// ("Guard", "Forward-Center") or abbreviations ("G", "F-C"); a name the page knows is translated,
// anything else is shown as sent (ADR 0054).
// SEE: docs/adr/0054-historical-sides-and-past-pages.md
import { m } from '#lib/paraglide/messages.js';

const POSITIONS: Record<string, () => string> = {
	guard: m.position_guard,
	forward: m.position_forward,
	center: m.position_center,
	'point guard': m.position_point_guard,
	'shooting guard': m.position_shooting_guard,
	'small forward': m.position_small_forward,
	'power forward': m.position_power_forward
};

const known = (name: string): string | null => POSITIONS[name.trim().toLowerCase()]?.() ?? null;

/** A position in the page language: a known name, a hyphenated name of known parts, else as sent. */
export function positionName(text: string): string {
	const whole = known(text);
	if (whole !== null) return whole;
	const parts = text.split('-');
	if (parts.length < 2) return text;
	const translated = parts.map(known);
	return translated.every((part) => part !== null) ? translated.join('-') : text;
}
