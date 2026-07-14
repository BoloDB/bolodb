import { browser } from "$app/environment";
import { loadGsap } from "$lib/motion/gsap";

export function reveal(node: HTMLElement, options: { threshold?: number } = {}) {
  if (!browser) return;
  const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
  const threshold = options.threshold ?? 0.2;

  let observer: IntersectionObserver | null = null;
  let cleanup = () => {};

  if (mq.matches) {
    node.style.opacity = "1";
    node.style.transform = "none";
    return;
  }

  node.style.opacity = "0";
  node.style.transform = "translateY(24px)";

  observer = new IntersectionObserver(
    async (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          const { gsap } = await loadGsap();
          gsap.to(node, {
            y: 0,
            opacity: 1,
            duration: 0.6,
            ease: "power3.out",
          });
          observer?.disconnect();
        }
      }
    },
    { threshold }
  );

  observer.observe(node);

  return {
    destroy() {
      observer?.disconnect();
      cleanup();
    },
  };
}
