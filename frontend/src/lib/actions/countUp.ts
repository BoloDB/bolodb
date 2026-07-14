import { browser } from "$app/environment";
import { loadGsap } from "$lib/motion/gsap";

export function countUp(
  node: HTMLElement,
  options: { from?: number; to: number; duration?: number; suffix?: string }
) {
  if (!browser) return;
  const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
  const { from = 0, to, duration = 1.5, suffix = "" } = options;

  if (mq.matches) {
    node.textContent = `${to}${suffix}`;
    return;
  }

  let observer: IntersectionObserver | null = null;
  let fired = false;

  const fmt = new Intl.NumberFormat();

  observer = new IntersectionObserver(
    async (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting && !fired) {
          fired = true;
          const { gsap } = await loadGsap();
          gsap.fromTo(
            { value: from },
            { value: from },
            {
              value: to,
              duration,
              ease: "power2.out",
              onUpdate: function (this: any) {
                node.textContent = `${fmt.format(Math.round(this.targets()[0].value))}${suffix}`;
              },
            }
          );
          observer?.disconnect();
        }
      }
    },
    { threshold: 0.3 }
  );

  observer.observe(node);

  return {
    destroy() {
      observer?.disconnect();
    },
  };
}
