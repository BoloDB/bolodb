import { browser } from "$app/environment";

export function spotlight(node: HTMLElement) {
  if (!browser) return;
  const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (mq.matches) return;

  function onMove(e: PointerEvent) {
    const rect = node.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    node.style.setProperty("--mx", `${x}px`);
    node.style.setProperty("--my", `${y}px`);
  }

  function onLeave() {
    node.style.setProperty("--mx", "50%");
    node.style.setProperty("--my", "50%");
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
