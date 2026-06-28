<div style="position:absolute;inset:0;pointer-events:none;z-index:3;overflow:hidden">
  <div class="flywheel-glow"></div>
  {#each Array(7) as _, i}
    <span class="flywheel-spark" style="right:{30 + i * 8}%;animation-delay:{i * 40}ms"></span>
  {/each}
</div>

<style>
  .flywheel-glow {
    position: absolute; inset: 0;
    background: radial-gradient(420px 180px at 80% 0%, var(--brand-tint) 0%, transparent 70%);
    animation: fadein .3s ease both, flywheel-fadeout .5s ease 1s both;
  }
  .flywheel-spark {
    position: absolute; top: 22px; width: 6px; height: 6px; border-radius: 99px;
    background: var(--brand);
    animation: flywheel-spark .9s var(--spring) both;
  }
  @keyframes flywheel-fadeout { to { opacity: 0; } }
  @keyframes flywheel-spark {
    0% { opacity: 0; transform: translateY(8px) scale(.4); }
    40% { opacity: 1; }
    100% { opacity: 0; transform: translateY(-26px) scale(1); }
  }
</style>
