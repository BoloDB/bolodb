let _gsap: any = null;
let _ScrollTrigger: any = null;

export async function loadGsap() {
  if (_gsap) return { gsap: _gsap, ScrollTrigger: _ScrollTrigger };

  const [{ gsap }, { ScrollTrigger }] = await Promise.all([
    import("gsap"),
    import("gsap/ScrollTrigger"),
  ]);

  gsap.registerPlugin(ScrollTrigger);
  _gsap = gsap;
  _ScrollTrigger = ScrollTrigger;

  return { gsap, ScrollTrigger };
}
