export function underline(node: HTMLElement) {
  node.style.position = "relative";
  node.style.display = "inline-block";

  const span = document.createElement("span");
  span.style.position = "absolute";
  span.style.bottom = "0";
  span.style.left = "0";
  span.style.width = "100%";
  span.style.height = "1.5px";
  span.style.background = "var(--brand)";
  span.style.transform = "scaleX(0)";
  span.style.transformOrigin = "left";
  span.style.transition = "transform 0.25s var(--ease)";
  span.style.pointerEvents = "none";
  node.appendChild(span);

  function onEnter() {
    span.style.transform = "scaleX(1)";
  }

  function onLeave() {
    span.style.transform = "scaleX(0)";
  }

  node.addEventListener("mouseenter", onEnter);
  node.addEventListener("mouseleave", onLeave);
  node.addEventListener("focus", onEnter);
  node.addEventListener("blur", onLeave);

  return {
    destroy() {
      node.removeEventListener("mouseenter", onEnter);
      node.removeEventListener("mouseleave", onLeave);
      node.removeEventListener("focus", onEnter);
      node.removeEventListener("blur", onLeave);
      span.remove();
    },
  };
}
