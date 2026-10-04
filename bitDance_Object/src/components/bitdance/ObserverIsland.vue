<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ChevronDown, FileStack, Hexagon, LogOut, Menu, User, X } from 'lucide-vue-next'
import { useAuth } from '../../state/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuth()
const isAuthed = auth.isAuthed
const currentUser = auth.user

const menuOpen = ref(false)
const userMenuOpen = ref(false)
const userMenuRoot = ref<HTMLElement | null>(null)

const displayName = computed(() => currentUser.value?.username || '…')

const nav = [
  { label: '首页', to: '/' },
  { label: '市场看板', to: '/dashboard' },
  { label: '行情', to: '/market' },
  { label: '我的策略', to: '/strategies' },
  { label: '文档中心', to: '/docs' },
  { label: '会员中心', to: '/member' },
  { label: '社区', to: '/community' },
] as const

const toolNav = [
  { label: '策略对比', to: '/analytics/compare' },
  { label: '因子选股', to: '/analytics/screen' },
  { label: '参数优化', to: '/analytics/grid' },
  { label: '组合回测', to: '/analytics/portfolio' },
  { label: '实时行情', to: '/analytics/realtime' },
] as const

function isActive(path: string) {
  if (path === '/') return route.path === '/'
  if (path === '/market') return route.path.startsWith('/market')
  if (path === '/analytics/compare') return route.path.startsWith('/analytics/compare')
  if (path === '/analytics/screen') return route.path.startsWith('/analytics/screen')
  if (path === '/analytics/grid') return route.path.startsWith('/analytics/grid')
  if (path === '/analytics/realtime') return route.path.startsWith('/analytics/realtime')
  if (path === '/analytics/portfolio') return route.path.startsWith('/analytics/portfolio')
  return route.path === path
}
function closeMenu() {
  menuOpen.value = false
}

function toggleUserMenu() {
  userMenuOpen.value = !userMenuOpen.value
}

function closeUserMenu() {
  userMenuOpen.value = false
}

function handleLogout() {
  auth.signOut()
  closeUserMenu()
  closeMenu()
  router.replace('/')
}

function onDocClick(e: MouseEvent) {
  const root = userMenuRoot.value
  if (root && !root.contains(e.target as Node)) {
    userMenuOpen.value = false
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    menuOpen.value = false
    userMenuOpen.value = false
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  document.addEventListener('click', onDocClick)
  void auth.init()
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  document.removeEventListener('click', onDocClick)
})

watch(
  () => route.fullPath,
  () => {
    menuOpen.value = false
    userMenuOpen.value = false
  },
)

watch(menuOpen, (open) => {
  if (open) userMenuOpen.value = false
})
</script>

<template>
  <header class="observer">
    <div class="island">
      <RouterLink to="/" class="brand" @click="closeMenu">
        <div class="brand-mark" aria-hidden="true">
          <Hexagon class="hex" stroke-width="1.25" />
          <span class="brand-core" />
        </div>
        <span class="brand-name">bitDance</span>
      </RouterLink>

      <nav class="nav" aria-label="主导航">
        <RouterLink
          v-for="item in nav"
          :key="item.to"
          :to="item.to"
          class="nav-link"
          :class="{ 'nav-link--on': isActive(item.to) }"
        >
          {{ item.label }}
        </RouterLink>
        <span class="nav-sep" aria-hidden="true" />
        <RouterLink
          v-for="item in toolNav"
          :key="item.to"
          :to="item.to"
          class="nav-link nav-link--tool"
          :class="{ 'nav-link--on': isActive(item.to) }"
        >
          {{ item.label }}
        </RouterLink>
      </nav>

      <div class="actions">
        <template v-if="!isAuthed">
          <RouterLink to="/login" class="link-quiet">登录</RouterLink>
          <RouterLink to="/register" class="btn-secondary">注册</RouterLink>
        </template>

        <div v-else ref="userMenuRoot" class="user-menu">
          <button
            type="button"
            class="user-trigger"
            :aria-expanded="userMenuOpen"
            aria-haspopup="true"
            @click.stop="toggleUserMenu"
          >
            <User class="user-ic" aria-hidden="true" />
            <span class="user-name">{{ displayName }}</span>
            <ChevronDown class="chevron" :class="{ 'chevron--open': userMenuOpen }" aria-hidden="true" />
          </button>
          <Transition name="dropdown">
            <div v-show="userMenuOpen" class="dropdown" role="menu">
              <RouterLink to="/report-history" class="dropdown-item" role="menuitem" @click="closeUserMenu">
                <FileStack class="dropdown-ic" aria-hidden="true" />
                回测报告历史记录
              </RouterLink>
              <button type="button" class="dropdown-item dropdown-item--danger" role="menuitem" @click="handleLogout">
                <LogOut class="dropdown-ic" aria-hidden="true" />
                退出登录
              </button>
            </div>
          </Transition>
        </div>

        <button
          type="button"
          class="burger"
          :aria-expanded="menuOpen"
          aria-label="打开菜单"
          @click="menuOpen = !menuOpen"
        >
          <Menu v-if="!menuOpen" class="burger-ic" />
          <X v-else class="burger-ic" />
        </button>
      </div>
    </div>

    <Transition name="sheet">
      <div v-if="menuOpen" class="sheet" role="dialog" aria-modal="true" aria-label="导航">
        <div v-if="isAuthed" class="sheet-user">
          <p class="sheet-user-label">已登录</p>
          <p class="sheet-user-name">{{ displayName }}</p>
          <div class="sheet-user-actions">
            <RouterLink to="/member" class="sheet-btn sheet-btn--ghost" @click="closeMenu">会员中心</RouterLink>
            <button type="button" class="sheet-btn sheet-btn--danger" @click="handleLogout">退出登录</button>
          </div>
        </div>
        <div v-else class="sheet-auth">
          <RouterLink to="/login" class="sheet-btn sheet-btn--ghost" @click="closeMenu">登录</RouterLink>
          <RouterLink to="/register" class="sheet-btn sheet-btn--primary" @click="closeMenu">注册</RouterLink>
        </div>
        <nav class="sheet-nav">
          <RouterLink
            v-for="item in nav"
            :key="`m-${item.to}`"
            :to="item.to"
            class="sheet-link"
            :class="{ 'sheet-link--on': isActive(item.to) }"
            @click="closeMenu"
          >
            {{ item.label }}
          </RouterLink>
          <p class="sheet-group">分析工具</p>
          <RouterLink
            v-for="item in toolNav"
            :key="`t-${item.to}`"
            :to="item.to"
            class="sheet-link"
            :class="{ 'sheet-link--on': isActive(item.to) }"
            @click="closeMenu"
          >
            {{ item.label }}
          </RouterLink>
        </nav>
      </div>
    </Transition>
  </header>
</template>

<style scoped>
.observer {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 40;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 1.25rem 1rem 0;
  pointer-events: none;
}

.island {
  pointer-events: auto;
  display: flex;
  max-width: 1120px;
  width: min(1120px, 100%);
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.7rem 1.15rem 0.7rem 1rem;
  border-radius: 999px;
  background: rgba(18, 28, 45, 0.62);
  backdrop-filter: blur(22px) saturate(1.15);
  -webkit-backdrop-filter: blur(22px) saturate(1.15);
  box-shadow:
    0 0 0 1px var(--bq-edge),
    0 1px 0 0 rgba(255, 255, 255, 0.04) inset,
    0 -18px 48px rgba(0, 0, 0, 0.45),
    0 12px 40px rgba(166, 127, 74, 0.08);
  animation: breathe 5.5s ease-in-out infinite;
}

@keyframes breathe {
  0%,
  100% {
    box-shadow:
      0 0 0 1px rgba(166, 127, 74, 0.14),
      0 1px 0 0 rgba(255, 255, 255, 0.04) inset,
      0 -18px 48px rgba(0, 0, 0, 0.45),
      0 8px 28px rgba(166, 127, 74, 0.06);
  }
  50% {
    box-shadow:
      0 0 0 1px rgba(166, 127, 74, 0.2),
      0 1px 0 0 rgba(255, 255, 255, 0.05) inset,
      0 -18px 52px rgba(0, 0, 0, 0.5),
      0 14px 44px rgba(166, 127, 74, 0.11);
  }
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
  text-decoration: none;
}

.brand-mark {
  position: relative;
  width: 2rem;
  height: 2rem;
  color: rgba(198, 153, 96, 0.92);
}

.hex {
  width: 100%;
  height: 100%;
}

.brand-core {
  position: absolute;
  inset: 30%;
  border-radius: 2px;
  background: linear-gradient(135deg, rgba(198, 153, 96, 0.94), rgba(107, 74, 41, 0.6));
  opacity: 0.9;
  transform: rotate(12deg);
}

.brand-name {
  font-size: 0.95rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: var(--bq-accent);
}

.nav {
  display: none;
  flex: 1;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.35rem 1.05rem;
  margin: 0 0.75rem;
}

@media (min-width: 1024px) {
  .nav {
    display: flex;
  }
}

.nav-link {
  font-size: 0.8125rem;
  font-weight: 500;
  color: rgba(231, 229, 228, 0.72);
  text-decoration: none;
  padding: 0.38rem 0.25rem;
  transform-origin: center center;
  transition:
    color 0.35s ease,
    transform 0.45s cubic-bezier(0.22, 1, 0.36, 1);
}

.nav-link:hover {
  color: rgba(250, 250, 249, 0.95);
  transform: scale(0.94);
}

.nav-link--on {
  color: var(--bq-accent-soft);
}

.nav-sep {
  align-self: center;
  width: 1px;
  height: 1.05rem;
  background: rgba(255, 255, 255, 0.14);
  margin: 0 0.15rem;
}

.nav-link--tool {
  color: rgba(191, 147, 83, 0.6);
}

.actions {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  flex-shrink: 0;
}

.link-quiet {
  display: none;
  font-size: 0.8125rem;
  color: rgba(245, 245, 244, 0.88);
  text-decoration: none;
  padding: 0.32rem 0.45rem;
  border-radius: 8px;
  transition:
    color 0.25s ease,
    background 0.25s ease;
}

.link-quiet:hover {
  color: #f7f5ef;
  background: rgba(255, 255, 255, 0.06);
}

@media (min-width: 480px) {
  .link-quiet {
    display: inline;
  }
}

.btn-secondary {
  display: none;
  padding: 0.42rem 0.85rem;
  border-radius: 999px;
  font-size: 0.8125rem;
  font-weight: 600;
  color: #0c0c0c;
  text-decoration: none;
  background: linear-gradient(180deg, #b3874f 0%, #7f5731 100%);
  box-shadow: 0 8px 22px rgba(0, 0, 0, 0.35);
}

@media (min-width: 480px) {
  .btn-secondary {
    display: inline-block;
  }
}

.user-menu {
  position: relative;
  display: none;
}

@media (min-width: 480px) {
  .user-menu {
    display: block;
  }
}

.user-trigger {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  max-width: 11rem;
  padding: 0.38rem 0.55rem 0.38rem 0.5rem;
  border: none;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(245, 245, 244, 0.92);
  font-size: 0.8125rem;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.08) inset;
  transition: background 0.2s ease;
}

.user-trigger:hover {
  background: rgba(255, 255, 255, 0.1);
}

.user-ic {
  width: 1rem;
  height: 1rem;
  flex-shrink: 0;
  opacity: 0.85;
}

.user-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chevron {
  width: 0.9rem;
  height: 0.9rem;
  flex-shrink: 0;
  opacity: 0.7;
  transition: transform 0.2s ease;
}

.chevron--open {
  transform: rotate(180deg);
}

.dropdown {
  position: absolute;
  right: 0;
  top: calc(100% + 0.45rem);
  min-width: 11rem;
  padding: 0.35rem;
  border-radius: 12px;
  background: rgba(16, 25, 41, 0.96);
  backdrop-filter: blur(16px);
  box-shadow:
    0 0 0 1px rgba(166, 127, 74, 0.2),
    0 16px 40px rgba(0, 0, 0, 0.45);
  z-index: 50;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.55rem 0.65rem;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: rgba(231, 229, 228, 0.92);
  font-size: 0.84rem;
  text-decoration: none;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s ease;
}

.dropdown-item:hover {
  background: rgba(255, 255, 255, 0.06);
}

.dropdown-item--danger {
  color: #f0a8a8;
}

.dropdown-item--danger:hover {
  background: rgba(240, 88, 88, 0.12);
}

.dropdown-ic {
  width: 1rem;
  height: 1rem;
  flex-shrink: 0;
  opacity: 0.85;
}

.dropdown-enter-active,
.dropdown-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.burger {
  display: flex;
  margin-left: 0.15rem;
  align-items: center;
  justify-content: center;
  width: 2.5rem;
  height: 2.5rem;
  border: none;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  color: rgba(245, 245, 244, 0.9);
  cursor: pointer;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.06) inset;
  pointer-events: auto;
}

@media (min-width: 1024px) {
  .burger {
    display: none;
  }
}

.burger-ic {
  width: 1.25rem;
  height: 1.25rem;
}

.sheet {
  pointer-events: auto;
  margin-top: 0.65rem;
  width: min(1120px, 100%);
  padding: 0.75rem 1rem 1rem;
  border-radius: 1.25rem;
  background: rgba(16, 25, 41, 0.78);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  box-shadow:
    0 0 0 1px rgba(166, 127, 74, 0.18),
    0 24px 48px rgba(0, 0, 0, 0.5);
}

@media (min-width: 1024px) {
  .sheet {
    display: none;
  }
}

.sheet-user {
  padding-bottom: 0.75rem;
  margin-bottom: 0.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.sheet-user-label {
  margin: 0;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--bq-accent-soft);
}

.sheet-user-name {
  margin: 0.35rem 0 0.65rem;
  font-size: 1rem;
  font-weight: 600;
  color: var(--bq-text);
}

.sheet-user-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.sheet-auth {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding-bottom: 0.75rem;
  margin-bottom: 0.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.sheet-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 0.85rem;
  border-radius: 10px;
  font-size: 0.84rem;
  font-weight: 600;
  text-decoration: none;
  border: none;
  cursor: pointer;
  transition:
    background 0.2s ease,
    color 0.2s ease;
}

.sheet-btn--ghost {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(245, 245, 244, 0.92);
}

.sheet-btn--primary {
  background: linear-gradient(180deg, #b3874f 0%, #7f5731 100%);
  color: #0c0c0c;
}

.sheet-btn--danger {
  background: rgba(240, 88, 88, 0.15);
  color: #f0a8a8;
}

.sheet-nav {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.sheet-link {
  padding: 0.65rem 0.5rem;
  font-size: 0.9375rem;
  color: rgba(231, 229, 228, 0.88);
  text-decoration: none;
  border-radius: 0.65rem;
  transition:
    background 0.2s ease,
    color 0.2s ease;
}

.sheet-link:hover {
  background: rgba(255, 255, 255, 0.04);
}

.sheet-link--on {
  color: rgba(198, 153, 96, 0.92);
}

.sheet-group {
  margin: 0.85rem 0.5rem 0.15rem;
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: rgba(191, 147, 83, 0.55);
}

.sheet-enter-active,
.sheet-leave-active {
  transition:
    opacity 0.3s ease,
    transform 0.35s cubic-bezier(0.22, 1, 0.36, 1);
}

.sheet-enter-from,
.sheet-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
