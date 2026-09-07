/**
 * LIGHTWEIGHT i18n REDYNESS LAYER
 * ------------------------------
 * Structures every user-facing string in one place so translations can be
 * added later WITHOUT an architectural rewrite. Each key maps to English
 * today; a future `setLocale` can swap in a dictionary per language.
 *
 * Usage:  t('nav.home')  /  t('catalog.subtitle', { count: '12,400' })
 *
 * Never render raw keys: `t()` always returns a string and falls back to
 * the key itself if a string is missing, so a typo can't crash the UI.
 */

export const LOCALES = ['en'];

const LOCALE_EN = {
  'brand.name': 'BingeFinder',

  'nav.home': 'Home',
  'nav.discover': 'Discover',
  'nav.surprise': 'Surprise Me',
  'nav.forYou': 'For You',
  'nav.watchlist': 'Watchlist',
  'nav.liked': 'Liked',
  'nav.recentlyViewed': 'Recently Viewed',
  'nav.settings': 'Settings',

  'auth.login': 'Log In',
  'auth.logout': 'Logout',
  'auth.signup': 'Sign Up',

  'hero.title': "What's your next binge?",
  'hero.subtitle': 'Search {count} series or let us find something for you.',
  'hero.subtitleNoCount': 'Search our full catalog or let us find something for you.',
  'hero.searchLabel': 'Search for a series',
  'hero.searchPlaceholder': 'Search for a series...',
  'hero.searchButton': 'Search',
  'hero.surpriseLink': 'Not sure? Try Surprise Me',

  'mood.title': 'Pick a mood',

  'section.viewAll': 'View all',
  'section.discoverMore': 'Discover more',

  'cta.startBrowsing': 'Start Browsing',
  'cta.discoverSeries': 'Discover Series',

  'discover.title': 'Discover',
  'discover.exploreCount': 'Explore {count} titles',
  'discover.searchCatalog': 'Search the catalog',
  'discover.searchLabel': 'Search titles',
  'discover.searchPlaceholder': 'Search by title...',
  'discover.filterTypeLabel': 'Content type',
  'discover.allTypes': 'All Types',
  'discover.typeSeries': 'Series',
  'discover.typeMovies': 'Movies',
  'discover.typeAnime': 'Anime',
  'discover.filterGenreLabel': 'Genre',
  'discover.allGenres': 'All Genres',
  'discover.filterYearLabel': 'Year',
  'discover.allYears': 'All Years',
  'discover.filterRatingLabel': 'Minimum rating',
  'discover.anyRating': 'Any Rating',
  'discover.filterStatusLabel': 'Status',
  'discover.allStatus': 'All Status',
  'discover.clearAll': 'Clear all',
  'discover.noResultsTitle': 'No results',
  'discover.noResultsForQuery': 'No series found for "{q}". Try a different search.',
  'discover.noResultsFilters': 'Try adjusting your filters.',

  'home.tonightsBinge': "Tonight's Binge",
  'home.tonightsBingeSub': 'Fresh picks for your next binge',
  'home.trending': 'Trending',
  'home.trendingSub': 'What everyone is watching',
  'home.newNoteworthy': 'New & Noteworthy',
  'home.newNoteworthySub': 'Fresh premieres worth your time',
  'home.recommendedForYou': 'Recommended For You',
  'home.recommendedForYouSub': 'Based on your history',
  'home.hiddenGems': 'Hidden Gems',
  'home.hiddenGemsSub': 'Less obvious, highly rated',
  'home.freeTonight': 'Free Tonight',
  'home.freeTonightSub': 'Stream free in your region right now',
  'home.personalizedComing': 'Personalized picks are coming',
  'home.personalizedComingMsg': 'Keep exploring and we\'ll learn what you like.',

  'card.viewDetails': 'View Details',
  'card.noPoster': 'No poster available',
  'card.untitled': 'Untitled',
  'card.match': '{score}% match',
  'card.free': 'FREE',
  'card.freeWithAds': 'FREE WITH ADS',
  'card.freeOn': 'Free: {names}',
  'card.onServices': 'On {names}',

  'detail.watchProviderTitle': 'Where to Watch',
  'detail.watchProviderLoading': 'Loading watch availability...',
  'detail.watchProviderNotConfigured': 'Watch availability is not configured.',
  'detail.watchProviderError': 'Watch availability is temporarily unavailable.',
  'detail.noOptionsInRegion': 'No streaming options found in {region}.',
  'detail.noFreeInRegion': 'No verified free streaming option currently available in {region}.',
  'detail.watchNow': 'WATCH NOW →',
  'detail.viewAvailability': 'VIEW AVAILABILITY →',
  'detail.justwatchAvailability': 'See all options on JustWatch ({region})',
  'detail.justwatchHint': 'Availability is verified on JustWatch for your region.',
  'detail.free': 'Free',
  'detail.freeWithAds': 'Free With Ads',
  'detail.subscription': 'Subscription',
  'detail.rentBuy': 'Rent / Buy',
  'detail.otherWays': 'Other ways to watch (subscription, rent or buy)',
  'detail.whyRecommendedTitle': 'Why you might like it',
  'detail.alsoLike': 'You might also like',
  'detail.inWatchlist': 'In Watchlist',
  'detail.addWatchlist': '+ Watchlist',
  'detail.liked': 'Liked',
  'detail.like': 'Like',
  'detail.love': 'Love',
  'detail.loved': 'Loved',
  'detail.notForMe': 'Not For Me',
  'detail.notForMeActive': 'Not For Me',
  'detail.notForMeHintTitle': 'You said not for me',
  'detail.notForMeHint': 'We won\'t recommend this title (or similar ones) again.',
  'detail.loveSaved': 'Loved! We\'ll recommend more like this.',
  'detail.likeSaved': 'Saved to Likes.',
  'detail.notForMeSaved': 'Got it — we\'ll show less like this.',
  'detail.reactionCleared': 'Reaction removed.',

  'action.addedToWatchlist': 'Added to your watchlist.',
  'action.removedFromWatchlist': 'Removed from your watchlist.',
  'action.liked': 'Saved to Likes.',
  'action.unliked': 'Removed from Likes.',
  'action.genericError': 'That could not be completed. Please try again.',
  'action.remove': 'Remove',
  'action.cancel': 'Cancel',
  'action.loginRequired': 'Log in to keep your lists and get personalized picks.',
  'confirm.removeTitle': 'Remove from your list?',
  'confirm.removeWatchlistMsg': 'This will remove it from your watchlist. You can add it back anytime.',
  'toast.dismiss': 'Dismiss',
  'detail.seriesNotFound': 'Series not found.',

  'region.label': 'Your region',
  'region.selectorAria': 'Choose your region',

  'settings.title': 'Settings',
  'settings.subtitle': 'Tune discovery and availability for you.',
  'settings.region': 'Your region',
  'settings.regionHint': 'Shown on every watch-availability and "Free Tonight" result.',
  'settings.languages': 'Preferred languages',
  'settings.languagesHint': 'Used to surface more international shows for you. Max {max}.',
  'settings.genres': 'Favorite genres',
  'settings.genresHint': 'We\'ll point new recommendations toward these. Max {max}.',
  'settings.services': 'My Services',
  'settings.servicesHint': 'Optional: pick the services you already have. Choices come from the availability source for your region.',
  'settings.servicesUnavailable': 'Service list is unavailable right now.',
  'settings.save': 'Save settings',
  'settings.saved': 'Settings saved.',
  'settings.savedError': 'Could not save settings. Please try again.',
  'settings.loading': 'Loading settings...',
  'settings.guestNote': 'You are browsing as a guest — your choices are saved on this device only.',

  'error.generic': 'Something went wrong. Please try again.',
  'error.retry': 'Try again',

  'forYou.title': 'For You',
  'forYou.subtitle': 'Personalized recommendations based on your taste',
  'forYou.emptyTitle': 'Build up your profile first',
  'forYou.emptyMsg': 'Like and watch a few shows, then come back for picks.',
  'forYou.emptyRecsTitle': 'No recommendations yet',
  'forYou.offlineEmpty': 'Recommendations are unavailable right now.',

  'onboarding.stepCount': 'Step {current} of {total}',
  'onboarding.genresTitle': 'What genres do you love?',
  'onboarding.genresHint': 'Pick up to {max} genres to shape your recommendations.',
  'onboarding.languagesTitle': 'Which languages do you prefer?',
  'onboarding.languagesHint': 'Pick up to {max} languages.',
  'onboarding.favoritesTitle': 'Pick a few favorites',
  'onboarding.favoritesHint': 'Tap shows you love to fine-tune your taste.',
  'onboarding.favoritesCount': '({count} selected)',
  'onboarding.favoritesEmpty': 'No shows found. Try another search.',
  'onboarding.searchPlaceholder': 'Search for a show...',
  'onboarding.favoriteAdd': 'Favorite',
  'onboarding.favoriteAdded': 'Favorite \u2713',
  'onboarding.back': 'Back',
  'onboarding.next': 'Next',
  'onboarding.finish': 'Finish',
  'onboarding.saving': 'Saving...',
  'onboarding.savedError': 'Could not save your preferences. Please try again.',
  'onboarding.skip': 'Skip for now',

  'watchlist.title': 'Watchlist',
  'watchlist.emptyTitle': 'Your watchlist is empty',
  'watchlist.emptyMsg': 'Save shows here so they are easy to find later.',
  'liked.title': 'Liked',
  'liked.emptyTitle': 'Nothing liked yet',
  'liked.emptyMsg': 'Tap Like on any show to see it here.',
  'recent.title': 'Recently Viewed',
  'recent.emptyTitle': 'Nothing viewed yet',
  'recent.emptyMsg': 'Shows you open will appear here.',
  'vibes.backHome': 'Back to Home',
  'vibes.noResultsTitle': 'No results',
  'vibes.noResultsMsg': 'No series match this mood right now.',
  'surprise.title': 'Surprise Me',
  'surprise.subtitle': "We'll pick something worth watching",
  'surprise.pick': 'Pick for me',
  'surprise.tryAnother': 'Try Another',
  'surprise.whyTitle': 'Why this pick?',
  'surprise.whereToWatch': 'Where to watch',
  'surprise.watchUnavailable': 'Watch availability is temporarily unavailable.',

  'notFound.title': 'Page not found',
  'notFound.message': 'The page you\'re looking for doesn\'t exist.',
  'notFound.home': 'Go home',
};

let messages = LOCALE_EN;

export function setLocale(locale) {
  const table = { en: LOCALE_EN }[locale] || LOCALE_EN;
  messages = table;
}

function interpolate(template, vars) {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (_, k) => (vars[k] != null ? String(vars[k]) : `{${k}}`));
}

export function t(key, vars) {
  const template = messages[key] ?? key;
  return interpolate(template, vars);
}

export const STRINGS = LOCALE_EN;