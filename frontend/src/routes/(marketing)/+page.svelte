<script lang="ts">
  import { browser } from "$app/environment";
  import { trackSectionView } from "$lib/marketing/analytics";
  import Backdrop from "$lib/marketing/Backdrop.svelte";
  import Hero from "$lib/marketing/Hero.svelte";
  import LiveDemo from "$lib/marketing/LiveDemo.svelte";
  import Pipeline from "$lib/marketing/Pipeline.svelte";
  import TrustEngine from "$lib/marketing/TrustEngine.svelte";
  import Flywheel from "$lib/marketing/Flywheel.svelte";
  import Integrations from "$lib/marketing/Integrations.svelte";
  import FinalCta from "$lib/marketing/FinalCta.svelte";

  const sections = ["hero", "demo", "pipeline", "trust", "flywheel", "integrations", "cta"] as const;

  $effect(() => {
    if (!browser) return;
    const obs = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            const id = e.target.getAttribute("data-section");
            if (id) trackSectionView(id as any);
          }
        }
      },
      { threshold: 0.3 }
    );

    for (const id of sections) {
      const el = document.getElementById(id);
      if (el) obs.observe(el);
    }

    return () => obs.disconnect();
  });
</script>



<Backdrop />
<div id="hero" data-section="hero"><Hero /></div>
<div id="demo" data-section="demo"><LiveDemo /></div>
<div id="pipeline" data-section="pipeline"><Pipeline /></div>
<div id="trust" data-section="trust"><TrustEngine /></div>
<div id="flywheel" data-section="flywheel"><Flywheel /></div>
<div id="integrations" data-section="integrations"><Integrations /></div>
<div id="cta" data-section="cta"><FinalCta /></div>
