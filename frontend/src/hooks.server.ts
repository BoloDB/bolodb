import { detectLocale } from "$lib/i18n/i18n-util";
import { loadLocale } from "$lib/i18n/i18n-util.sync";
import { setLocale } from "$lib/i18n/i18n-svelte";
import { initAcceptLanguageHeaderDetector } from "typesafe-i18n/detectors";
import type { Locales } from "$lib/i18n/i18n-types";

export async function handle({ event, resolve }) {
  let lang = event.cookies.get("locale");
  if (!lang) {
    const acceptLanguageDetector = initAcceptLanguageHeaderDetector(
      event.request,
    );
    lang = detectLocale(acceptLanguageDetector);
  } else {
    lang = detectLocale(() => [lang as string]);
  }

  const locale = lang as Locales;
  event.locals.locale = locale;

  loadLocale(locale);
  setLocale(locale);

  return resolve(event, {
    transformPageChunk: ({ html }) =>
      html.replace('lang="en"', `lang="${locale}"`),
  });
}
