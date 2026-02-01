<template>
  <a-layout class="layout-container" :class="{ 'solid-bg': isAiSummaryPage }">
    <AIBackground v-if="!isAiSummaryPage" />
    <a-layout-sider
      hide-trigger
      collapsible
      :width="90"
      class="sider-container"
    >
      <div class="sider-inner">
        <!-- Logo Section -->
        <div class="logo-section">
          <div class="logo-box">
            <icon-star-fill :style="{ fontSize: '20px', color: '#fff' }" />
          </div>
        </div>

        <!-- Navigation Section -->
        <div class="nav-section">
          <div 
            v-for="item in navItems" 
            :key="item.key"
            class="nav-item"
            :class="{ active: selectedKey === item.key }"
            @click="handleMenuClick(item.key)"
          >
            <component :is="item.icon" :style="{ fontSize: '22px' }" />
          </div>
        </div>

        <!-- Footer Section -->
        <div class="sider-footer">
          <div class="nav-item theme-toggle" @click="toggleTheme">
            <component :is="isDark ? IconSunFill : IconMoonFill" :style="{ fontSize: '22px' }" />
          </div>
          <div class="nav-item logout">
            <icon-export :style="{ fontSize: '22px' }" />
          </div>
        </div>
      </div>
    </a-layout-sider>
    
    <a-layout class="main-layout">
      <a-layout-content class="content-container">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup>
import { computed, watchEffect } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AIBackground from '../components/AIBackground.vue'
import { useConfigStore } from '../stores/config'
import { 
  IconHome, 
  IconPlayCircle, 
  IconBarChart, 
  IconHistory, 
  IconSettings,
  IconStarFill,
  IconExport,
  IconSearch,
  IconSunFill,
  IconMoonFill
} from '@arco-design/web-vue/es/icon'

const route = useRoute()
const router = useRouter()
const configStore = useConfigStore()

const navItems = [
  { key: 'Dashboard', icon: IconHome },
  { key: 'Video', icon: IconPlayCircle },
  { key: 'Analytics', icon: IconBarChart },
  { key: 'History', icon: IconHistory },
  { key: 'Settings', icon: IconSettings },
]

const selectedKey = computed(() => {
  if (route.name === 'Dashboard') return 'Dashboard'
  if (route.name === 'Settings') return 'Settings'
  return route.name
})

const pageTitle = computed(() => {
  if (route.name === 'Settings') return 'Settings'
  return 'Dashboard'
})

const isAiSummaryPage = computed(() => route.name === 'AiVideoSummary')
const isDark = computed(() => configStore.theme === 'dark')

const handleMenuClick = (key) => {
  if (key === 'Dashboard') {
    router.push('/')
  } else if (key === 'Settings') {
    router.push('/settings')
  }
}

const toggleTheme = () => {
  configStore.toggleTheme()
}

watchEffect(() => {
  if (configStore.theme === 'dark') {
    document.body.setAttribute('arco-theme', 'dark')
  } else {
    document.body.removeAttribute('arco-theme')
  }
  document.documentElement.setAttribute('data-theme', configStore.theme)
})
</script>

<style scoped>
.layout-container {
  height: 100vh;
  background-color: transparent; /* 改为透明 */
  padding: 0; /* 移除外边距实现全屏感 */
  overflow: hidden;
  display: flex;
}

.layout-container.solid-bg {
  background-color: var(--surface-1);
}

.sider-container {
  background-color: var(--sider-bg);
  margin: 0;
  border-radius: 0;
  box-shadow: none;
  z-index: 10;
  height: 100vh !important;
  max-height: none;
  overflow: hidden;
  flex-shrink: 0;
}

:deep(.arco-layout-sider-children) {
  overflow: hidden !important; /* 强制隐藏 Arco 默认滚动条 */
}

.sider-inner {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px 0;
  box-sizing: border-box;
}

.logo-section {
  margin-bottom: 32px;
  flex-shrink: 0;
}

.logo-box {
  width: 48px;
  height: 48px;
  background-color: rgba(255, 255, 255, 0.2);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.nav-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 22px;
  min-height: 0;
  position: relative;
}

.nav-section::before {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 50%;
  width: 2px;
  transform: translateX(-50%);
  background-color: var(--sider-line-bg);
  border-radius: 999px;
}

.nav-section::after {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 50%;
  width: 2px;
  transform: translateX(-50%);
  border-radius: 999px;
  background: linear-gradient(
    180deg,
    transparent 0%,
    rgba(168, 116, 255, 0.62) 22%,
    rgba(255, 116, 232, 0.52) 50%,
    rgba(206, 136, 255, 0.44) 78%,
    transparent 100%
  );
  background-size: 100% 220%;
  background-position: 0% 0%;
  filter: blur(0.2px);
  opacity: 0.9;
  animation: siderLineFlow 4.8s ease-in-out infinite;
  pointer-events: none;
}

.nav-item {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--sider-icon);
  transition: transform 0.18s ease, color 0.18s ease, background-color 0.18s ease, filter 0.18s ease;
  flex-shrink: 0;
  position: relative;
  z-index: 1;
  transform: translateZ(0);
}

.nav-item::before {
  content: '';
  position: absolute;
  inset: -10px;
  border-radius: 18px;
  background:
    radial-gradient(18px 18px at 28% 22%, rgba(255, 255, 255, 0.28), transparent 70%),
    radial-gradient(22px 22px at 72% 68%, rgba(255, 255, 255, 0.20), transparent 70%),
    radial-gradient(20px 20px at 54% 86%, rgba(255, 255, 255, 0.14), transparent 70%);
  opacity: 0;
  filter: blur(6px);
  transition: opacity 0.18s ease, transform 0.18s ease;
  pointer-events: none;
}

.nav-item::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 12px;
  opacity: 0;
  transition: opacity 0.18s ease;
  pointer-events: none;
  background: linear-gradient(
    120deg,
    rgba(255, 255, 255, 0.00) 0%,
    rgba(255, 255, 255, 0.16) 22%,
    rgba(255, 255, 255, 0.10) 52%,
    rgba(255, 255, 255, 0.08) 78%,
    rgba(255, 255, 255, 0.00) 100%
  );
}

.nav-item:hover {
  background-color: var(--sider-hover-bg);
  color: var(--sider-hover-color);
  transform: translateY(-1px) scale(1.03);
  filter: drop-shadow(0 10px 22px rgba(0, 0, 0, 0.25));
}

.nav-item:hover::before {
  opacity: 1;
  transform: scale(1.02);
}

.nav-item:hover::after {
  opacity: 1;
}

.nav-item.active {
  background-color: var(--sider-active-bg);
  color: var(--sider-active-color);
  box-shadow: none;
}

.nav-item.active::before {
  opacity: 1;
  filter: blur(7px);
  background:
    radial-gradient(18px 18px at 28% 22%, rgba(255, 255, 255, 0.28), transparent 70%),
    radial-gradient(22px 22px at 72% 68%, rgba(255, 255, 255, 0.20), transparent 70%),
    radial-gradient(20px 20px at 54% 86%, rgba(255, 255, 255, 0.14), transparent 70%);
}

.nav-item.active::after {
  opacity: 1;
  animation: navActiveSheen 2.8s ease-in-out infinite;
  background: linear-gradient(
    120deg,
    rgba(255, 255, 255, 0.00) 0%,
    rgba(255, 255, 255, 0.16) 22%,
    rgba(255, 255, 255, 0.10) 52%,
    rgba(255, 255, 255, 0.08) 78%,
    rgba(255, 255, 255, 0.00) 100%
  );
}

.nav-item.active > :deep(svg),
.nav-item.active > :deep(i) {
  filter: drop-shadow(0 0 10px rgba(255, 255, 255, 0.18));
}

.nav-item:active {
  transform: translateY(0px) scale(0.99);
}

.sider-footer {
  margin-top: 32px;
  flex-shrink: 0;
}

.nav-item.logout {
  color: var(--sider-muted);
}

.nav-item.logout:hover {
  color: var(--sider-hover-color);
}

.main-layout {
  background: transparent;
  height: 100vh;
  flex: 1;
}

.content-container {
  height: 100vh;
  overflow-y: auto;
  padding: 0; /* 内容区填满剩余空间 */
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@keyframes siderLineFlow {
  0% { background-position: 0% 0%; opacity: 0.70; }
  50% { background-position: 0% 100%; opacity: 0.95; }
  100% { background-position: 0% 0%; opacity: 0.70; }
}

@keyframes navActiveSheen {
  0% { opacity: 0.55; }
  50% { opacity: 1; }
  100% { opacity: 0.55; }
}

@media (prefers-reduced-motion: reduce) {
  .nav-section::after,
  .nav-item.active::after {
    animation: none;
  }

  .nav-item {
    transition: color 0.18s ease, background-color 0.18s ease;
  }

  .nav-item:hover,
  .nav-item:active {
    transform: none;
    filter: none;
  }
}
</style>
