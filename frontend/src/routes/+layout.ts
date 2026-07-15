import { loadLocale } from "$lib/i18n/i18n-util.sync";
import { setLocale } from "$lib/i18n/i18n-svelte";
import type { LayoutLoad } from "./$types";

export const load: LayoutLoad = async ({ data }) => {
  const locale = data.locale;
  loadLocale(locale);
  setLocale(locale);
  return data;
};
