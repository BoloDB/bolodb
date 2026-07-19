export const routing = {
  locales: ["en", "de", "es", "fr", "ja"],
  defaultLocale: "en",
  localeDetection: true,
  localePrefix: "never",
} as const;

export type Locale = (typeof routing.locales)[number];
