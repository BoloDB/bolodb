<script lang="ts">
  import { browser } from "$app/environment";
  import { motionPrefs } from "$lib/motion/motionPrefs";

  let canvas: HTMLCanvasElement;
  let ctx: CanvasRenderingContext2D | null = null;
  let animId: number;

  $effect(() => {
    if (!browser || !canvas) return;

    ctx = canvas.getContext("2d");
    if (!ctx) return;

    let w = 0, h = 0;
    const dpr = Math.min(1.5, devicePixelRatio || 1);
    let blobs: any[] = [];
    let isVisible = true;
    let running = false;

    function currentDark() {
      const attr = document.documentElement.getAttribute("data-theme");
      if (attr) return attr === "dark";
      return window.matchMedia("(prefers-color-scheme: dark)").matches;
    }

    function palette() {
      return currentDark()
        ? [
            [77, 166, 255],
            [98, 224, 176],
            [139, 123, 255],
          ]
        : [
            [27, 158, 107],
            [43, 179, 214],
            [95, 140, 220],
          ];
    }

    function build() {
      const c = palette();
      blobs = [
        { x: 0.22, y: 0.16, r: 0.55, c: c[0], ax: 0.05, ay: 0.06, sp: 0.00013, ph: 0 },
        { x: 0.82, y: 0.1, r: 0.5, c: c[1], ax: 0.06, ay: 0.05, sp: 0.00017, ph: 2 },
        { x: 0.6, y: 0.78, r: 0.62, c: c[2], ax: 0.07, ay: 0.05, sp: 0.00011, ph: 4 },
        { x: 0.1, y: 0.88, r: 0.42, c: c[0], ax: 0.05, ay: 0.06, sp: 0.00015, ph: 1.5 },
      ];
    }

    function resize() {
      w = canvas.width = Math.floor(window.innerWidth * dpr);
      h = canvas.height = Math.floor(window.innerHeight * dpr);
    }

    function draw(t: number) {
      ctx!.clearRect(0, 0, w, h);
      ctx!.globalCompositeOperation = "lighter";
      const base = currentDark() ? 0.12 : 0.08;
      for (let i = 0; i < blobs.length; i++) {
        const b = blobs[i];
        const cx = (b.x + Math.sin(t * b.sp + b.ph) * b.ax) * w;
        const cy = (b.y + Math.cos(t * b.sp * 1.3 + b.ph) * b.ay) * h;
        const rad = b.r * Math.max(w, h);
        const g = ctx!.createRadialGradient(cx, cy, 0, cx, cy, rad);
        g.addColorStop(0, `rgba(${b.c[0]},${b.c[1]},${b.c[2]},${base})`);
        g.addColorStop(1, `rgba(${b.c[0]},${b.c[1]},${b.c[2]},0)`);
        ctx!.fillStyle = g;
        ctx!.fillRect(0, 0, w, h);
      }
      ctx!.globalCompositeOperation = "source-over";
    }

    function loop(now: number) {
      if (isVisible) draw(now);
      animId = requestAnimationFrame(loop);
    }

    function start() {
      if (running) return;
      running = true;
      animId = requestAnimationFrame(loop);
    }

    function stop() {
      running = false;
      if (animId) cancelAnimationFrame(animId);
      animId = 0;
    }

    resize();
    build();

    if (motionPrefs.reduced) {
      draw(6000);
      return;
    }

    const obs = new IntersectionObserver(
      (entries) => { isVisible = entries[0]?.isIntersecting ?? true; },
      { threshold: 0 }
    );
    obs.observe(canvas);

    function onVisibilityChange() {
      if (document.hidden) stop();
      else if (!motionPrefs.reduced) start();
    }

    window.addEventListener("resize", resize);
    document.addEventListener("visibilitychange", onVisibilityChange);

    const themeObs = new MutationObserver(() => {
      build();
      if (motionPrefs.reduced) draw(6000);
    });
    themeObs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

    start();

    return () => {
      stop();
      window.removeEventListener("resize", resize);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      obs.disconnect();
      themeObs.disconnect();
    };
  });
</script>

<canvas bind:this={canvas} class="backdrop-canvas" aria-hidden="true"></canvas>
<div class="backdrop-noise" aria-hidden="true"></div>
<div class="backdrop-static" aria-hidden="true"></div>

<style>
  .backdrop-canvas {
    position: fixed;
    inset: 0;
    z-index: 0;
    width: 100vw;
    height: 100vh;
    pointer-events: none;
  }

  .backdrop-noise {
    position: fixed;
    inset: 0;
    z-index: 0;
    pointer-events: none;
    opacity: 0.035;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
    background-size: 200px 200px;
  }

  .backdrop-static {
    position: fixed;
    inset: 0;
    z-index: 0;
    pointer-events: none;
  }

  :global([data-theme="dark"]) .backdrop-static {
    background:
      radial-gradient(1000px 800px at 82% -6%, rgba(77,166,255,0.05) 0%, transparent 50%),
      radial-gradient(800px 600px at 8% 8%, rgba(139,123,255,0.05) 0%, transparent 50%);
  }

  :global([data-theme="crisp"]) .backdrop-static,
  :global([data-theme="soft"]) .backdrop-static {
    background:
      radial-gradient(1200px 700px at 82% -6%, rgba(27,158,107,0.05) 0%, transparent 55%),
      radial-gradient(800px 500px at 8% 8%, rgba(43,179,214,0.05) 0%, transparent 50%);
  }
</style>
