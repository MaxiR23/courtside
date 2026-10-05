import { getLocale } from '#lib/paraglide/runtime.js';

export function formatDate(date: Date, options: Intl.DateTimeFormatOptions): string {
	return new Intl.DateTimeFormat(getLocale(), options).format(date);
}

export function formatNumber(value: number, options?: Intl.NumberFormatOptions): string {
	return new Intl.NumberFormat(getLocale(), options).format(value);
}

export function formatDateParts(
	date: Date,
	options: Intl.DateTimeFormatOptions
): Intl.DateTimeFormatPart[] {
	return new Intl.DateTimeFormat(getLocale(), options).formatToParts(date);
}
