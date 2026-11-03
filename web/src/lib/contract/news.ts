/**
 * Generated from api/schemas/news.schema.json by scripts/contract.sh.
 * Do not edit by hand: run scripts/contract.sh instead.
 */

export type NewsLanguage = 'en' | 'es';
export type NewsKind = 'news' | 'recap';

export interface NewsFeed {
	page: number;
	hasMore: boolean;
	/**
	 * @maxItems 12
	 */
	notes:
		| []
		| [NewsNote]
		| [NewsNote, NewsNote]
		| [NewsNote, NewsNote, NewsNote]
		| [NewsNote, NewsNote, NewsNote, NewsNote]
		| [NewsNote, NewsNote, NewsNote, NewsNote, NewsNote]
		| [NewsNote, NewsNote, NewsNote, NewsNote, NewsNote, NewsNote]
		| [NewsNote, NewsNote, NewsNote, NewsNote, NewsNote, NewsNote, NewsNote]
		| [NewsNote, NewsNote, NewsNote, NewsNote, NewsNote, NewsNote, NewsNote, NewsNote]
		| [NewsNote, NewsNote, NewsNote, NewsNote, NewsNote, NewsNote, NewsNote, NewsNote, NewsNote]
		| [
				NewsNote,
				NewsNote,
				NewsNote,
				NewsNote,
				NewsNote,
				NewsNote,
				NewsNote,
				NewsNote,
				NewsNote,
				NewsNote
		  ]
		| [
				NewsNote,
				NewsNote,
				NewsNote,
				NewsNote,
				NewsNote,
				NewsNote,
				NewsNote,
				NewsNote,
				NewsNote,
				NewsNote,
				NewsNote
		  ]
		| [
				NewsNote,
				NewsNote,
				NewsNote,
				NewsNote,
				NewsNote,
				NewsNote,
				NewsNote,
				NewsNote,
				NewsNote,
				NewsNote,
				NewsNote,
				NewsNote
		  ];
}
export interface NewsNote {
	id: string;
	language: NewsLanguage;
	kind: NewsKind;
	headline: string;
	description: string | null;
	published: string;
	photo: NewsPhoto | null;
	teams: string[];
	players: NewsPlayer[];
	gameId: string | null;
}
export interface NewsPhoto {
	url: string;
	width: number;
	height: number;
	credit: string | null;
}
export interface NewsPlayer {
	playerId: string;
	name: string;
}
