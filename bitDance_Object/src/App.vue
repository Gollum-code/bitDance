<script setup lang="ts">
import BitdanceAssistant from './components/bitdance/BitdanceAssistant.vue'
import ObserverIsland from './components/bitdance/ObserverIsland.vue'
</script>

<template>
  <div class="app-atmosphere">
    <div class="blob blob-a" aria-hidden="true" />
    <div class="blob blob-b" aria-hidden="true" />
    <div class="blob blob-c" aria-hidden="true" />
    <div class="blob blob-d" aria-hidden="true" />

    <div class="grain" aria-hidden="true" />
    <div class="vignette" aria-hidden="true" />

    <ObserverIsland />

    <div class="page-shell">
      <router-view />
    </div>

    <BitdanceAssistant />
  </div>
</template>

<style scoped>
.app-atmosphere {
  position: relative;
  isolation: isolate;
  min-height: 100%;
  background-color: var(--bq-bg);
  color: var(--bq-text);
  overflow-x: hidden;
}

.page-shell {
  position: relative;
  z-index: 3;
  min-height: 100vh;
}

.blob {
  position: fixed;
  pointer-events: none;
  z-index: 0;
  border-radius: 50%;
  mix-blend-mode: screen;
  opacity: 0.5;
  filter: blur(120px);
  will-change: transform;
  animation: drift 28s ease-in-out infinite alternate;
}

.blob-a {
  width: min(95vw, 820px);
  height: min(95vw, 820px);
  top: -18%;
  right: -12%;
  background: radial-gradient(
    circle at 35% 35%,
    rgba(123, 168, 207, 0.4) 0%,
    rgba(60, 84, 114, 0.12) 42%,
    transparent 68%
  );
  animation-duration: 32s;
}

.blob-b {
  width: min(80vw, 640px);
  height: min(80vw, 640px);
  bottom: -22%;
  left: -8%;
  background: radial-gradient(
    circle at 60% 55%,
    rgba(200, 168, 115, 0.28) 0%,
    rgba(102, 79, 45, 0.1) 45%,
    transparent 70%
  );
  opacity: 0.35;
  animation-duration: 26s;
  animation-delay: -4s;
}

.blob-c {
  width: min(70vw, 520px);
  height: min(70vw, 520px);
  top: 38%;
  left: 55%;
  transform: translate(-50%, -50%);
  background: radial-gradient(
    circle at 50% 50%,
    rgba(123, 168, 207, 0.18) 0%,
    transparent 62%
  );
  opacity: 0.5;
  filter: blur(140px);
  animation: drift-center 36s ease-in-out infinite alternate;
  animation-delay: -8s;
}

.blob-d {
  width: min(60vw, 480px);
  height: min(60vw, 480px);
  top: 8%;
  left: 5%;
  background: radial-gradient(
    ellipse 80% 60% at 50% 50%,
    rgba(200, 168, 115, 0.12) 0%,
    transparent 65%
  );
  opacity: 0.4;
  filter: blur(160px);
  animation-duration: 30s;
  animation-delay: -12s;
}

@keyframes drift {
  0% {
    transform: translate(0, 0) scale(1);
  }
  100% {
    transform: translate(-2.5%, 1.8%) scale(1.04);
  }
}

@keyframes drift-center {
  0% {
    transform: translate(-50%, -50%) scale(1);
  }
  100% {
    transform: translate(calc(-50% + 2%), calc(-50% + 1.5%)) scale(1.05);
  }
}

.grain {
  position: fixed;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  opacity: 0.034;
  mix-blend-mode: overlay;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 512 512' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  background-size: 180px 180px;
}

.vignette {
  position: fixed;
  inset: 0;
  z-index: 2;
  pointer-events: none;
  background: radial-gradient(
    ellipse 85% 75% at 50% 42%,
    rgba(0, 0, 0, 0) 0%,
    rgba(0, 0, 0, 0.2) 62%,
    rgba(0, 0, 0, 0.52) 100%
  );
}

@media (prefers-reduced-motion: reduce) {
  .blob {
    animation: none;
  }
}
</style>
