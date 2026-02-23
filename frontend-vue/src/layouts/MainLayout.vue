<template>
  <a-layout class="layout-container" :class="{ 'solid-bg': isAiSummaryPage }">
    <AIBackground v-if="!isAiSummaryPage" />
    <a-layout-sider
      hide-trigger
      collapsible
      :width="74"
      class="sider-container"
    >
      <div class="sider-inner">
        <!-- Logo Section -->
        <div class="logo-section">
          <a-avatar 
            :size="48" 
            shape="square" 
            class="logo-avatar"
          >
            <img :src="headerImg" alt="Logo" />
          </a-avatar>
        </div>

        <!-- Navigation Section -->
        <div class="nav-section">
          <a-tooltip 
            v-for="item in navItems" 
            :key="item.key"
            :content="item.label"
            position="right"
            mini
          >
            <div 
              class="nav-item"
              :class="{ active: selectedKey === item.key }"
              @click="handleMenuClick(item.key)"
            >
              <component :is="item.icon" :style="{ fontSize: '20px' }" />
            </div>
          </a-tooltip>
        </div>

        <!-- Footer Section -->
        <div class="sider-footer">
          <div class="nav-item theme-toggle" @click="toggleTheme">
            <component :is="isDark ? IconSunFill : IconMoonFill" :style="{ fontSize: '20px' }" />
          </div>
          <div class="nav-item logout">
            <icon-export :style="{ fontSize: '20px' }" />
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
import { Message } from '@arco-design/web-vue'
import AIBackground from '../components/AIBackground.vue'
import { useConfigStore } from '../stores/config'
import headerImg from '../assert/headr.png'
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
  IconMoonFill,
  IconList,
  IconFolder
} from '@arco-design/web-vue/es/icon'

const route = useRoute()
const router = useRouter()
const configStore = useConfigStore()

const navItems = [
  { key: 'Dashboard', icon: IconHome, label: '仪表盘' },
  { key: 'Category', icon: IconFolder, label: '分类管理' },
  { key: 'Video', icon: IconPlayCircle, label: '分析列表' },
  { key: 'TaskList', icon: IconList, label: '任务列表' },
  { key: 'Analytics', icon: IconBarChart, label: '数据统计' },
  { key: 'History', icon: IconHistory, label: '历史记录' },
  { key: 'Settings', icon: IconSettings, label: '系统设置' },
]

const selectedKey = computed(() => {
  if (route.name === 'Dashboard') return 'Dashboard'
  if (route.name === 'Settings') return 'Settings'
  if (route.name === 'Category') return 'Category'
  if (route.name === 'Video' || route.name === 'AiVideoSummary' || route.name === 'AiFileSummary') return 'Video'
  if (route.name === 'TaskList') return 'TaskList'
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
  } else if (key === 'Video') {
    router.push('/video')
  } else if (key === 'TaskList') {
    router.push('/tasks')
  } else if (key === 'Settings') {
    router.push('/settings')
  } else if (key === 'Category') {
    router.push('/category')
  } else if (key === 'Analytics') {
    router.push('/analytics')
  } else if (key === 'History') {
    router.push('/history')
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
  background-color: var(--color-bg-1);
}

.sider-container {
  background-color: var(--color-bg-2);
  margin: 0;
  border-radius: 0;
  box-shadow: none;
  z-index: 10;
  height: 100vh !important;
  max-height: none;
  overflow: hidden;
  flex-shrink: 0;
  border-right: 1px solid var(--color-border-2);
  backdrop-filter: blur(20px);
}

:deep(.arco-layout-sider-children) {
  overflow: hidden !important; /* 强制隐藏 Arco 默认滚动条 */
}

.sider-inner {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 0;
  box-sizing: border-box;
}

.logo-section {
  margin-bottom: 24px;
  flex-shrink: 0;
  display: flex;
  justify-content: center;
}

.logo-avatar {
  background-color: transparent !important;
  border-radius: 12px !important;
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  border: 2px solid transparent;
  cursor: pointer;
  overflow: hidden;
}

.logo-avatar:hover {
  transform: scale(1.05) rotate(2deg);
  box-shadow: 0 8px 20px rgba(var(--primary-6), 0.25);
  border-color: rgba(var(--primary-6), 0.3);
}

.logo-avatar :deep(img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease;
}

.logo-avatar:hover :deep(img) {
  transform: scale(1.1);
}

.nav-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  min-height: 0;
  padding-top: 10px;
}

.nav-item {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--color-text-2);
  transition: all 0.2s cubic-bezier(0.34, 0.69, 0.1, 1);
  position: relative;
}

.nav-item:hover {
  background-color: var(--color-fill-2);
  color: var(--color-text-1);
  transform: translateY(-1px);
}

.nav-item.active {
  background-color: var(--primary-6);
  color: #fff;
  box-shadow: 0 4px 12px color-mix(in srgb, var(--primary-6), transparent 70%);
}

/* Light Theme Optimization */
[data-theme='light'] .nav-item.active {
  background-color: var(--color-fill-2) !important;
  color: #722ed1 !important; /* Purple icon */
  box-shadow: none !important;
}

[data-theme='light'] .nav-item.active > :deep(svg) {
  stroke-width: 2.5px; /* Thicker stroke for better visibility */
  filter: drop-shadow(0 1px 2px rgba(114, 46, 209, 0.2)); /* Purple shadow */
}

/* Dark Theme specific adjustments if needed */
[data-theme='dark'] .nav-item.active {
  color: #fff;
}

.nav-item.active > :deep(svg),
.nav-item.active > :deep(i) {
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.1));
}

.nav-item:active {
  transform: translateY(0) scale(0.95);
}

.sider-footer {
  margin-top: 32px;
  flex-shrink: 0;
}

.nav-item.logout {
  color: var(--color-text-3);
}

.nav-item.logout:hover {
  color: var(--color-text-1);
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

/* Custom Scrollbar for Content Container */
.content-container::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
.content-container::-webkit-scrollbar-thumb {
  background: var(--text-muted);
  border-radius: 3px;
  opacity: 0.5;
}
.content-container::-webkit-scrollbar-track {
  background: transparent;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .nav-item {
    transition: none;
  }

  .nav-item:hover,
  .nav-item:active {
    transform: none;
  }
}
</style>
