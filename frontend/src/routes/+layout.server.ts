import type { LayoutServerLoad } from "./$types";
import type { Locales } from "$lib/i18n/i18n-types";

export const load: LayoutServerLoad = async ({ locals }) => {
  return {
    locale: locals.locale as Locales,
  };
};
