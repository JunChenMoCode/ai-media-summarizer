import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '../layouts/MainLayout.vue'
import Dashboard from '../views/Dashboard.vue'
import AiVideoSummary from '../views/AiVideoSummary.vue'
import Video from '../views/Video.vue'
import Settings from '../views/Settings.vue'

const routes = [
  {
    path: '/',
    component: MainLayout,
    children: [
      {
        path: '',
        name: 'Dashboard',
        component: Dashboard
      },
      {
        path: 'settings',
        name: 'Settings',
        component: Settings
      },
      {
        path: 'video',
        name: 'Video',
        component: Video
      },
      {
        path: 'ai-video-summary',
        name: 'AiVideoSummary',
        component: AiVideoSummary
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
