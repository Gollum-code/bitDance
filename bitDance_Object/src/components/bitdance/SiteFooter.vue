<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { Hexagon } from 'lucide-vue-next'
</script>

<template>
  <footer class="footer">
    <div class="inner">
      <div class="brand-row">
        <div class="mark" aria-hidden="true">
          <Hexagon class="hex" stroke-width="1.25" />
        </div>
        <span class="name">bitDance</span>
        <span class="tag">数据即艺术</span>
      </div>
      <nav class="links" aria-label="页脚">
        <RouterLink to="/community">社区</RouterLink>
        <a href="mailto:hello@bitdance.io">联系</a>
      </nav>
      <p class="legal">© {{ new Date().getFullYear() }} bitDance. 界面为演示资产，不构成投资建议。</p>
    </div>
  </footer>
</template>

<style scoped>
.footer {
  margin-top: 5rem;
  padding: 2.5rem 0 3rem;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
  box-shadow: 0 -1px 0 rgba(191, 147, 83, 0.04);
}

.inner {
  max-width: 1120px;
  margin: 0 auto;
  padding: 0 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  align-items: flex-start;
}

@media (min-width: 640px) {
  .inner {
    flex-direction: row;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
  }
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.mark {
  width: 1.5rem;
  height: 1.5rem;
  color: rgba(191, 147, 83, 0.75);
}

.hex {
  width: 100%;
  height: 100%;
}

.name {
  font-weight: 600;
  font-size: 0.95rem;
  color: rgba(191, 147, 83, 0.9);
}

.tag {
  font-size: 0.75rem;
  color: rgba(168, 162, 158, 0.55);
  letter-spacing: 0.06em;
}

.links {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem 1.25rem;
}

.links a {
  font-size: 0.8125rem;
  color: rgba(168, 162, 158, 0.82);
  text-decoration: none;
  transition: color 0.25s ease;
}

.links a:hover {
  color: rgba(191, 147, 83, 0.85);
}

.legal {
  margin: 0;
  width: 100%;
  font-size: 0.6875rem;
  line-height: 1.5;
  color: rgba(120, 113, 108, 0.65);
}

@media (min-width: 640px) {
  .legal {
    flex-basis: 100%;
    text-align: left;
  }
}
</style>

