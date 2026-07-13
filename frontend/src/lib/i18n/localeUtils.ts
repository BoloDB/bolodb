export function setLocaleCookie(locale: string): void {
  if (typeof document === "undefined") return;
  document.cookie = `locale=${encodeURIComponent(locale)};path=/;max-age=${60 * 60 * 24 * 365};SameSite=Lax`;
}
