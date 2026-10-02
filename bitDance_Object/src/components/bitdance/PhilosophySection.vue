<template>
  <section id="philosophy" class="philosophy" aria-labelledby="philosophy-title">
    <h2 id="philosophy-title" class="sr-only">理念</h2>
    <div class="strip">
      <article class="pillar">
        <h3 class="pillar-title">秩序</h3>
        <p class="pillar-copy">策略与风控以层级呈现，不靠线框分割空间。</p>
      </article>
      <article class="pillar">
        <h3 class="pillar-title">光影</h3>
        <p class="pillar-copy">明暗即层级；磨砂金只作低语，不作喧哗。</p>
      </article>
      <article class="pillar">
        <h3 class="pillar-title">深度</h3>
        <p class="pillar-copy">卡片沉入背景 1%，单侧高光勾勒存在。</p>
      </article>
    </div>
  </section>
</template>

<style scoped>
.philosophy {
  margin-top: 4rem;
  scroll-margin-top: 6rem;
}

.strip {
  display: grid;
  gap: 1.25rem;
}

@media (min-width: 768px) {
  .strip {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 1.5rem;
  }
}

.pillar {
  padding: 1.5rem 1.35rem;
  border-radius: 1rem;
  background: #040404;
  box-shadow:
    0 0 0 1px rgba(255, 255, 255, 0.028) inset,
    0 -1px 0 0 rgba(191, 147, 83, 0.08) inset,
    0 20px 48px rgba(0, 0, 0, 0.45),
    -1px -1px 0 0 rgba(191, 147, 83, 0.1);
}

.pillar-title {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: rgba(191, 147, 83, 0.75);
}

.pillar-copy {
  margin: 0.65rem 0 0;
  font-size: 0.875rem;
  line-height: 1.65;
  color: rgba(168, 162, 158, 0.78);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>

