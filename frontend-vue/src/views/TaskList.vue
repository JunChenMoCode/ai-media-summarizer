<template>
  <div class="task-list-page">
    <div class="page-header">
      <div class="header-left">
        <div class="title">任务列表</div>
        <div class="subtitle">查看正在运行和已完成的任务</div>
      </div>
      <div class="header-right">
        <a-button type="primary" status="success" @click="fetchTasks">
          <template #icon><icon-refresh /></template>
          刷新列表
        </a-button>
      </div>
    </div>

    <div class="task-content">
      <a-table :data="tasks" :pagination="false" :bordered="false" row-key="id">
        <template #columns>
          <a-table-column title="任务名称" data-index="url" ellipsis tooltip>
            <template #cell="{ record }">
              <div style="max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                {{ record.url }}
              </div>
            </template>
          </a-table-column>
          <a-table-column title="类型" data-index="type">
            <template #cell="{ record }">
              <a-tag :color="record.type === 'video' ? 'arcoblue' : 'orange'">
                {{ record.type === 'video' ? '视频分析' : '文档分析' }}
              </a-tag>
            </template>
          </a-table-column>
          <a-table-column title="状态" data-index="status">
            <template #cell="{ record }">
              <a-badge
                :status="getStatusColor(record.status)"
                :text="getStatusText(record.status)"
              />
            </template>
          </a-table-column>
          <a-table-column title="进度" data-index="progress">
            <template #cell="{ record }">
              <div style="display: flex; align-items: center; gap: 8px;">
                <a-progress 
                  :percent="record.progress / 100" 
                  size="small" 
                  :status="record.status === 'failed' ? 'danger' : record.status === 'completed' ? 'success' : 'normal'" 
                  style="width: 100px"
                />
                <span style="font-size: 12px; color: var(--text-muted)">{{ getLastLog(record) }}</span>
              </div>
            </template>
          </a-table-column>
          <a-table-column title="创建时间" data-index="created_at">
            <template #cell="{ record }">
              {{ formatTime(record.created_at) }}
            </template>
          </a-table-column>
          <a-table-column title="操作">
            <template #cell="{ record }">
              <a-space>
                <a-button 
                  v-if="record.status === 'completed'" 
                  type="text" 
                  size="small" 
                  @click="viewResult(record)"
                >
                  查看
                </a-button>
                <a-button 
                  type="text" 
                  size="small" 
                  status="danger" 
                  @click="deleteTask(record)"
                >
                  {{ record.status === 'running' || record.status === 'pending' ? '取消' : '删除' }}
                </a-button>
              </a-space>
            </template>
          </a-table-column>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { IconRefresh } from '@arco-design/web-vue/es/icon'
import { useConfigStore } from '../stores/config'

const router = useRouter()
const configStore = useConfigStore()
const backendBaseUrl = computed(() => (configStore.backend_base_url || '').replace(/\/+$/, ''))

const tasks = ref([])
let pollTimer = null

const fetchTasks = async () => {
  try {
    const res = await fetch(`${backendBaseUrl.value}/tasks`)
    if (res.ok) {
      tasks.value = await res.json()
    }
  } catch (e) {
    console.error('Failed to fetch tasks', e)
  }
}

const startPolling = () => {
  fetchTasks()
  pollTimer = setInterval(fetchTasks, 2000)
}

const stopPolling = () => {
  if (pollTimer) clearInterval(pollTimer)
}

onMounted(() => {
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})

const getStatusColor = (status) => {
  switch (status) {
    case 'running': return 'processing'
    case 'completed': return 'success'
    case 'failed': return 'danger'
    case 'cancelled': return 'warning'
    default: return 'normal'
  }
}

const getStatusText = (status) => {
  switch (status) {
    case 'running': return '进行中'
    case 'completed': return '已完成'
    case 'failed': return '失败'
    case 'cancelled': return '已取消'
    case 'pending': return '等待中'
    default: return status
  }
}

const getLastLog = (record) => {
  if (record.logs && record.logs.length) {
    return record.logs[record.logs.length - 1]
  }
  return ''
}

const formatTime = (ts) => {
  if (!ts) return ''
  return new Date(ts * 1000).toLocaleString()
}

const deleteTask = async (record) => {
  const isRunning = record.status === 'running' || record.status === 'pending'
  const actionText = isRunning ? '取消' : '删除'
  
  Modal.warning({
    title: `确认${actionText}`,
    content: `确定要${actionText}任务吗？`,
    onOk: async () => {
      try {
        const res = await fetch(`${backendBaseUrl.value}/tasks/${record.id}`, {
          method: 'DELETE'
        })
        if (res.ok) {
          Message.success(`${actionText}成功`)
          fetchTasks()
        } else {
          Message.error(`${actionText}失败`)
        }
      } catch (e) {
        Message.error('操作出错')
      }
    }
  })
}

const viewResult = (record) => {
  if (record.result && record.result.md5) {
    router.push({ name: 'AiVideoSummary', query: { md5: record.result.md5 } })
  } else {
    Message.warning('无法找到结果链接')
  }
}
</script>

<style scoped>
.task-list-page {
  padding: 24px;
  min-height: 100vh;
}

.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
}

.header-left .title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-main);
  line-height: 1.2;
}

.header-left .subtitle {
  margin-top: 6px;
  font-size: 13px;
  color: var(--text-muted);
}

.task-content {
  background: var(--color-bg-2);
  border-radius: 8px;
  padding: 24px;
  min-height: 400px;
}

.empty-placeholder {
  padding: 40px 0;
  display: flex;
  justify-content: center;
}
</style>
