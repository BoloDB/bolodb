import { loadLocale } from "$lib/i18n/i18n-util.sync";
import { setLocale } from "$lib/i18n/i18n-svelte";

loadLocale("en");
setLocale("en");

export async function handle({ event, resolve }) {
  return resolve(event);
}
