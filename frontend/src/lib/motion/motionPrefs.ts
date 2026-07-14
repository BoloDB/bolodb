import { browser } from "$app/environment";

let _reduced = false;

if (browser) {
  const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
  _reduced = mq.matches;

  mq.addEventListener("change", (e) => {
    _reduced = e.matches;
  });
}

export function prefersReducedMotion() {
  return _reduced;
}

export const motionPrefs = {
  get reduced() {
    return _reduced;
  },
};
