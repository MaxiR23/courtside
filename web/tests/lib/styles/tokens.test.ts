// web/tests/lib/styles/tokens.test.ts
//
// Tests for the design tokens file.
//
// Tested:
// - Every token from docs/design.md is defined with its spec value
// - No token is defined twice
// - The file holds only the :root rule
// - No token is redeclared elsewhere in web/src
//
// What is covered:
// - Happy path (every token present with its spec value)
// - Edge cases (duplicates, extra declarations, tokens redeclared elsewhere)
//
// Run with: cd web && pnpm exec vitest run tests/lib/styles/tokens.test.ts
//
// SEE: web/src/lib/styles/tokens.css
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const srcDir = join(import.meta.dirname, '../../../src');
const tokensPath = join(srcDir, 'lib/styles/tokens.css');

const expected: Record<string, string> = {
	'--color-bg': '#0c0e10',
	'--color-surface': '#14171a',
	'--color-frame-fill': '#11161b',
	'--color-ink': '#ebe8e3',
	'--color-muted': '#a19d96',
	'--color-accent': '#749dc4',
	'--color-accent-light': '#94bce3',
	'--color-accent-hover': '#b5d9fd',
	'--color-bar-neutral': '#424244',
	'--color-divider': 'color-mix(in srgb, #ebe8e3 13%, transparent)',
	'--color-row-rule': 'rgba(235, 232, 227, 0.07)',
	'--color-grid-line': 'rgba(235, 232, 227, 0.035)',
	'--color-open-tint': 'rgba(116, 157, 196, 0.045)',
	'--color-selected-day': 'rgba(116, 157, 196, 0.12)',
	'--font-heading': "'Barlow Condensed', sans-serif",
	'--font-body': 'Barlow, sans-serif',
	'--font-weight-regular': '400',
	'--font-weight-medium': '500',
	'--font-weight-semibold': '600',
	'--label-size': '11px',
	'--label-letter-spacing': '0.16em',
	'--live-badge-size': '9.5px',
	'--tag-padding': '1px 5px',
	'--hero-h1-size': 'clamp(54px, 9.5vw, 148px)',
	'--hero-h1-line-height': '0.86',
	'--hero-h1-letter-spacing': '-0.02em',
	'--hero-h1-at-size': '0.42em',
	'--hero-watermark-size': 'clamp(180px, 26vw, 420px)',
	'--hero-watermark-stroke': '1px rgba(235, 232, 227, 0.13)',
	'--section-h2-size': 'clamp(40px, 5vw, 64px)',
	'--section-h2-line-height': '0.95',
	'--team-name-size': 'clamp(18px, 2.2vw, 26px)',
	'--team-name-size-mobile': '20px',
	'--score-size': 'clamp(32px, 4vw, 46px)',
	'--score-size-mobile': '30px',
	'--monogram-size': '46px',
	'--monogram-size-mobile': '38px',
	'--tip-time-size': 'clamp(28px, 3.4vw, 38px)',
	'--tip-time-suffix-size': '0.45em',
	'--player-name-size': '19px',
	'--body-size-hero': '17px',
	'--body-size': '14px',
	'--body-size-small': '13px',
	'--brand-size': '20px',
	'--brand-letter-spacing': '0.12em',
	'--caption-size': '12px',
	'--chip-code-size': '34px',
	'--chip-last-name-size': '22px',
	'--day-number-size': 'clamp(22px, 3vw, 32px)',
	'--radius': '0',
	'--hairline': '1px',
	'--frame-mark-size': '11px',
	'--frame-mark-offset': '-6px',
	'--frame-mark-color': 'color-mix(in srgb, #ebe8e3 55%, transparent)',
	'--shadow-hero-frame':
		'0 50px 100px -24px rgba(0, 0, 0, 0.9), 0 20px 40px -20px rgba(0, 0, 0, 0.7)',
	'--floor-shadow': 'radial-gradient(rgba(0, 0, 0, 0.9), transparent 70%)',
	'--floor-shadow-blur': '10px',
	'--floor-shadow-offset': '56px',
	'--accent-glow': 'radial-gradient(circle at 50% 45%, rgba(116, 157, 196, 0.24), transparent 62%)',
	'--accent-glow-extent': '18%',
	'--brand-mark-size': '22px',
	'--brand-mark-inner-size': '8px',
	'--hero-grid-size': '88px',
	'--hero-frame-grid-size': '44px',
	'--hero-frame-max-width': '500px',
	'--hero-frame-aspect': '4 / 5',
	'--hero-cutout-width': '172%',
	'--hero-cutout-clip': 'inset(-30% 0 0 0)',
	'--hero-cutout-filter':
		'drop-shadow(0 0 1px rgba(148, 188, 227, 0.35)) drop-shadow(0 30px 30px rgba(0, 0, 0, 0.7)) contrast(1.05)',
	'--hero-fade': 'linear-gradient(to top, rgba(12, 14, 16, 0.85), transparent)',
	'--hero-fade-height': '30%',
	'--chip-bg': 'rgba(12, 14, 16, 0.82)',
	'--chip-blur': '12px',
	'--progress-track-height': '2px',
	'--floor-shadow-width': '80%',
	'--floor-shadow-height': '40px',
	'--chevron-size': '24px',
	'--icon-stroke-width': '1.5',
	'--dimmed-opacity': '0.42',
	'--content-max-width': '1320px',
	'--side-padding': 'clamp(20px, 4vw, 48px)',
	'--game-list-gap': '14px',
	'--day-strip-gap': 'clamp(4px, 1vw, 8px)',
	'--panel-section-gap': '36px',
	'--hit-target-size': '44px',
	'--hero-column-min': '440px',
	'--hero-gap': 'clamp(40px, 6vw, 96px)',
	'--hero-min-height': 'min(820px, 88vh)',
	'--chip-left': 'clamp(-28px, -2vw, -10px)',
	'--chip-bottom': '36px',
	'--game-row-breakpoint': '680px',
	'--ease': 'cubic-bezier(0.2, 0.7, 0.1, 1)',
	'--hero-entrance-offset': '28px',
	'--hero-entrance-duration': '1s',
	'--hero-delay-tag': '0.1s',
	'--hero-delay-h1': '0.2s',
	'--hero-delay-blurb': '0.32s',
	'--hero-delay-buttons': '0.44s',
	'--hero-delay-indicator': '0.6s',
	'--hero-frame-entrance-offset': '60px',
	'--hero-frame-entrance-scale': '0.94',
	'--hero-frame-entrance-duration': '1.4s',
	'--hero-delay-frame': '0.25s',
	'--hero-slide-interval': '7s',
	'--hero-crossfade-duration': '1s',
	'--hero-slide-offset': '36px',
	'--hero-slide-scale': '0.95',
	'--hero-watermark-fade-duration': '1.1s',
	'--hero-float-distance': '-16px',
	'--hero-float-duration': '6s',
	'--hero-float-shadow-scale': '0.82',
	'--hero-float-shadow-opacity': '0.6',
	'--hero-perspective': '1200px',
	'--hero-tilt-y': '7deg',
	'--hero-tilt-x': '-6deg',
	'--hero-tilt-duration': '0.5s',
	'--hero-watermark-shift-x': '-30px',
	'--hero-watermark-shift-y': '-18px',
	'--hero-watermark-shift-duration': '0.6s',
	'--list-entrance-offset': '18px',
	'--list-entrance-duration': '600ms',
	'--list-entrance-stagger': '70ms',
	'--focus-ring-width': '2px',
	'--focus-ring-offset': '2px'
};

function stripComments(css: string): string {
	return css.replace(/\/\*[\s\S]*?\*\//g, '');
}

function parseDeclarations(css: string): [string, string][] {
	return [...stripComments(css).matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/g)].map((m) => [
		m[1],
		m[2].replace(/\s+/g, ' ').trim()
	]);
}

const tokensCss = readFileSync(tokensPath, 'utf8');

describe('design tokens', () => {
	it('defines every design token from docs/design.md with its spec value', () => {
		expect(Object.fromEntries(parseDeclarations(tokensCss))).toEqual(expected);
	});

	it('defines each token only once', () => {
		const names = parseDeclarations(tokensCss).map(([name]) => name);
		expect(new Set(names).size).toBe(names.length);
	});

	it('holds only the :root rule', () => {
		expect(stripComments(tokensCss)).toMatch(/^\s*:root\s*\{[^{}]*\}\s*$/);
	});

	it('does not redeclare a design token anywhere else in src', () => {
		const files = readdirSync(srcDir, { recursive: true, encoding: 'utf8' }).filter(
			(f) => /\.(css|svelte|html)$/.test(f) && f !== join('lib', 'styles', 'tokens.css')
		);
		for (const file of files) {
			const content = readFileSync(join(srcDir, file), 'utf8');
			for (const name of Object.keys(expected)) {
				expect(content.includes(`${name}:`), `${file} redeclares ${name}`).toBe(false);
			}
		}
	});
});
