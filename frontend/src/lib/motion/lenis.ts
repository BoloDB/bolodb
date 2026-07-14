import { browser } from "$app/environment";

let _lenis: any = null;

export function getLenis() {
  return _lenis;
}

export async function initLenis() {
  if (!browser || _lenis) return _lenis;

  const Lenis = (await import("lenis")).default;

  _lenis = new Lenis({
    duration: 1.2,
    easing: (t: number) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
    orientation: "vertical",
    gestureOrientation: "vertical",
    smoothWheel: true,
    wheelMultiplier: 1,
    touchMultiplier: 1.5,
  });

  return _lenis;
}

export function destroyLenis() {
  if (_lenis) {
    _lenis.destroy();
    _lenis = null;
  }
}

export function scrollTo(target: string | HTMLElement, options?: any) {
  if (!_lenis) {
    const id = typeof target === "string" ? target.replace(/^#/, "") : "";
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
    return;
  }
  const selector = typeof target === "string" && !target.startsWith("#") ? "#" + target : target;
  _lenis.scrollTo(selector, options);
}
