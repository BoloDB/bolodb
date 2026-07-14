import { browser } from "$app/environment";

export function tilt(node: HTMLElement, options: { max?: number } = {}) {
  if (!browser) return;
  const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (mq.matches) return;

  const max = options.max ?? 6;

  function onMove(e: PointerEvent) {
    if (e.pointerType === "touch") return;
    const rect = node.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    const rotX = (y - 0.5) * max;
    const rotY = (x - 0.5) * -max;
    node.style.transform = `perspective(800px) rotateX(${rotX}deg) rotateY(${rotY}deg)`;
  }

  function onLeave() {
    node.style.transform = "";
  }

  node.addEventListener("pointermove", onMove);
  node.addEventListener("pointerleave", onLeave);

  return {
    destroy() {
      node.removeEventListener("pointermove", onMove);
      node.removeEventListener("pointerleave", onLeave);
    },
  };
}
