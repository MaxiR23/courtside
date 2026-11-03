// Props of the news components. Components get pre-formatted strings and never a contract type.

export type NewsCardView = {
	id: string;
	kind: 'news' | 'recap';
	kindLabel: string; // "Recap", "Crónica"
	teamTag: string | null; // the first team code, uppercase; null: the note names no team
	english: boolean; // an English note shown in Spanish: drawn with an EN tag
	date: string; // "16 h ago", "2 nov"
	headline: string;
	description: string | null;
	photo: { url: string; width: number; height: number } | null; // null: the card is text only
};

// null: the block is drawn nowhere (no URL, 404, failed or no notes).
export type NewsBlock = null | { kind: 'loading' } | { kind: 'ready'; notes: NewsCardView[] };

export type NewsArticleView = {
	card: NewsCardView;
	fullDate: string; // "2 de noviembre de 2026, 20:30"
	credit: string | null; // the photo credit; null: none
	related: {
		players: { id: string; name: string }[];
		teams: { code: string; label: string }[]; // code lowercase for the link, label uppercase
		game: { id: string; label: string } | null; // null: the site does not hold the game
	};
};

export type NewsArticleState =
	| { kind: 'loading' }
	| { kind: 'unavailable' }
	| { kind: 'not-found' }
	| { kind: 'ready'; view: NewsArticleView };

export type NewsKindFilter = 'all' | 'recap' | 'news';

export type NewsTeamOption = { code: string; label: string }; // code lowercase

// The list of the News page.
export type NewsListState =
	| { kind: 'loading' }
	| { kind: 'unavailable' }
	| { kind: 'ready'; cards: NewsCardView[]; hasMore: boolean; loadingMore: boolean };
