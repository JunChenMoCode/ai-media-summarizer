<template>
  <div class="task-list-page">
    <div class="page-header">
      <div class="header-left">
        <div class="title">任务列表</div>
        <div class="subtitle">查看正在运行和已完成的任务</div>
      </div>
      <div class="header-right">
        <input
          ref="fileInputRef"
          type="file"
          style="display: none"
          multiple
          @change="handleFilesSelected"
        />
        <a-space>
          <a-button type="primary" @click="triggerUpload('video')">
            <template #icon><icon-play-circle /></template>
            音视频批量总结
          </a-button>
          <a-button type="primary" @click="triggerUpload('document')">
            <template #icon><icon-file /></template>
            文档批量总结
          </a-button>
          <a-button type="primary" status="success" @click="fetchTasks">
            <template #icon><icon-refresh /></template>
            刷新列表
          </a-button>
        </a-space>
      </div>
    </div>

    <div class="task-content">
      <a-table 
        :data="tasks" 
        :pagination="pagination" 
        :bordered="false" 
        row-key="id"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
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

    <a-modal v-model:visible="showTitleModal" title="开始批量总结" @ok="startBatchUpload" :ok-text="'开始'" :cancel-text="'取消'" @cancel="cancelBatchUpload">
      <div style="padding: 20px;">
        <p style="margin-bottom: 16px;">请选择分析结果的标题命名方式：</p>
        <a-radio-group v-model="titlePreference" direction="vertical">
          <a-radio value="ai">使用 AI 生成的标题 (推荐)</a-radio>
          <a-radio value="filename">使用原文件名</a-radio>
        </a-radio-group>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { IconRefresh, IconPlayCircle, IconFile } from '@arco-design/web-vue/es/icon'
import { useConfigStore } from '../stores/config'

const router = useRouter()
const configStore = useConfigStore()
const backendBaseUrl = computed(() => (configStore.backend_base_url || '').replace(/\/+$/, ''))

const tasks = ref([])
const fileInputRef = ref(null)
const uploadType = ref('video')
let pollTimer = null

const showTitleModal = ref(false)
const titlePreference = ref('ai')
const pendingFiles = ref([])
const pendingUploadType = ref('video')

const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: true,
  showJumper: true,
  showPageSize: true,
  pageSizeOptions: [10, 20, 50, 100]
})

const handlePageChange = (page) => {
  pagination.current = page
  fetchTasks()
}

const handlePageSizeChange = (pageSize) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  fetchTasks()
}

const triggerUpload = (type) => {
  uploadType.value = type
  if (fileInputRef.value) {
    fileInputRef.value.accept = type === 'video' 
      ? 'video/*,audio/*' 
      : '.pdf,.docx,.doc,.pptx,.ppt,.txt,.md'
    fileInputRef.value.click()
  }
}

const handleFilesSelected = async (e) => {
  const files = Array.from(e.target.files || [])
  if (!files.length) return
  
  // Clear input so same files can be selected again
  e.target.value = ''

  pendingFiles.value = files
  pendingUploadType.value = uploadType.value
  showTitleModal.value = true
}

const cancelBatchUpload = () => {
  showTitleModal.value = false
  pendingFiles.value = []
}

const startBatchUpload = async () => {
  showTitleModal.value = false
  const files = pendingFiles.value || []
  const type = pendingUploadType.value
  pendingFiles.value = []

  if (!files.length) return

  Message.info(`开始上传 ${files.length} 个文件...`)
  for (const file of files) {
    try {
      await uploadAndEnqueue(file, type)
    } catch (err) {
      console.error('Upload failed for', file.name, err)
      Message.error(`文件 ${file.name} 上传/添加任务失败: ${err.message}`)
    }
  }

  pagination.current = 1
  fetchTasks()
}

const uploadAndEnqueue = async (file, type) => {
  // Force refresh config from localStorage to ensure latest values
  const getCfg = (key, storeVal) => {
      const local = localStorage.getItem(key)
      return (local !== null && local !== undefined) ? local : storeVal
  }

  const taskConfig = {
      openai_api_key: getCfg('openai_api_key', configStore.openai_api_key),
      openai_base_url: getCfg('openai_base_url', configStore.openai_base_url),
      llm_model: getCfg('llm_model', configStore.llm_model),
      ocr_engine: getCfg('ocr_engine', configStore.ocr_engine),
      vl_model: getCfg('vl_model', configStore.vl_model),
      vl_base_url: getCfg('vl_base_url', configStore.vl_base_url),
      vl_api_key: getCfg('vl_api_key', configStore.vl_api_key),
      model_size: getCfg('model_size', configStore.model_size),
      device: getCfg('device', configStore.device),
      compute_type: getCfg('compute_type', configStore.compute_type),
      capture_offset: parseFloat(getCfg('capture_offset', configStore.capture_offset)) || 5.0,
      title_preference: titlePreference.value
  }

  console.log('>>> Submitting task config:', taskConfig)

  if (!taskConfig.openai_api_key) {
    Message.warning('未检测到前端 API Key，将使用后端环境变量配置')
    // 强制阻止提交，如果用户确实想用后端的 Key，可以注释掉这行。但既然用户在问为什么没生效，那说明他不想用后端的。
    // 为了不完全阻断，我们还是允许提交，但日志已经足够明显。
  } else {
    Message.success('前端 API Key 检测成功，准备提交任务')
    console.log('>>> API Key detected:', taskConfig.openai_api_key.substring(0, 8) + '...')
  }

  // 1. Get Presign URL
  const presignRes = await fetch(`${backendBaseUrl.value}/minio/presign_upload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename: file.name })
  })
  
  if (!presignRes.ok) throw new Error('Failed to get upload URL')
  const { upload_url, video_url } = await presignRes.json()

  // 2. Upload to MinIO
  const uploadRes = await fetch(upload_url, {
    method: 'PUT',
    body: file
  })
  
  if (!uploadRes.ok) throw new Error('Failed to upload file to storage')

  // 3. Enqueue Task
  // Use video_url (presigned GET url) so backend can download it generically
  const enqueueRes = await fetch(`${backendBaseUrl.value}/tasks/enqueue`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      url: video_url, 
      type: type === 'video' ? 'video' : 'file',
      config: taskConfig
    })
  })

  if (!enqueueRes.ok) throw new Error('Failed to create task')
  Message.success(`任务已添加: ${file.name}`)
}

const fetchTasks = async () => {
  try {
    const params = new URLSearchParams({
      page: pagination.current,
      size: pagination.pageSize
    })
    const res = await fetch(`${backendBaseUrl.value}/tasks?${params}`)
    if (res.ok) {
      const data = await res.json()
      if (Array.isArray(data)) {
        // Fallback for old API response
        tasks.value = data
        pagination.total = data.length
      } else if (data && data.items) {
        // New paginated response
        tasks.value = data.items
        pagination.total = data.total
        pagination.current = data.page
        pagination.pageSize = data.size
      }
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
    const t = String(record.type || '').trim().toLowerCase()
    if (t === 'file' || t === 'document') {
      router.push({ name: 'AiFileSummary', query: { md5: record.result.md5 } })
    } else {
      router.push({ name: 'AiVideoSummary', query: { md5: record.result.md5 } })
    }
  } else {
    Message.warning('无法找到结果链接')
  }
}
</script>

<style scoped>
.task-list-page {
  padding: 24px 24px 0;
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
}

.empty-placeholder {
  padding: 40px 0;
  display: flex;
  justify-content: center;
}
</style>
