import { browser } from "$app/environment";

export function magnetic(node: HTMLElement) {
  if (!browser) return;
  const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (mq.matches || "ontouchstart" in window) return;

  let raf: number | null = null;
  let tx = 0,
    ty = 0,
    cx = 0,
    cy = 0;

  function loop() {
    cx += (tx - cx) * 0.18;
    cy += (ty - cy) * 0.18;
    node.style.transform = `translate(${cx.toFixed(2)}px,${cy.toFixed(2)}px)`;
    if (Math.abs(tx - cx) > 0.1 || Math.abs(ty - cy) > 0.1) {
      raf = requestAnimationFrame(loop);
    } else {
      raf = null;
    }
  }

  function kick() {
    if (!raf) raf = requestAnimationFrame(loop);
  }

  function onMove(e: PointerEvent) {
    if (e.pointerType === "touch") return;
    const r = node.getBoundingClientRect();
    tx = (e.clientX - (r.left + r.width / 2)) * 0.28;
    ty = (e.clientY - (r.top + r.height / 2)) * 0.4;
    tx = Math.max(-12, Math.min(12, tx));
    ty = Math.max(-12, Math.min(12, ty));
    kick();
  }

  function onLeave() {
    tx = 0;
    ty = 0;
    kick();
  }

  node.addEventListener("pointermove", onMove);
  node.addEventListener("pointerleave", onLeave);

  return {
    destroy() {
      node.removeEventListener("pointermove", onMove);
      node.removeEventListener("pointerleave", onLeave);
      if (raf) cancelAnimationFrame(raf);
    },
  };
}
