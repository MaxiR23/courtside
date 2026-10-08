export type HeroPlayer = {
	firstName: string;
	lastName: string;
	shortName: string; // watermark and slide indicator
	teamCode: string; // three letters
	teamName: string; // full team name, chip
	photo: string; // image URL
};

export type HeroStatus = 'tonight' | 'live' | 'final' | 'delayed' | 'postponed' | 'canceled';

export type HeroGame = {
	id: string; // the game id, passed back by Match details
	status: HeroStatus;
	tipTime: string; // already formatted, e.g. "10:30 PM ET"
	arena: string;
	away: { code: string; name: string; star: HeroPlayer };
	home: { code: string; name: string; star: HeroPlayer };
};
