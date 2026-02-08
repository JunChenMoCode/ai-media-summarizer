import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '../layouts/MainLayout.vue'
import Dashboard from '../views/Dashboard.vue'
import AiVideoSummary from '../views/AiVideoSummary.vue'
import AiFileSummary from '../views/AiFileSummary.vue'
import Video from '../views/Video.vue'
import TaskList from '../views/TaskList.vue'
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
        path: 'tasks',
        name: 'TaskList',
        component: TaskList
      },
      {
        path: 'ai-video-summary',
        name: 'AiVideoSummary',
        component: AiVideoSummary
      },
      {
        path: 'ai-file-summary',
        name: 'AiFileSummary',
        component: AiFileSummary
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
