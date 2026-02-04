<template>
  <div class="video-list-page">
    <div class="page-header">
      <div class="header-left">
        <div class="title">已分析资源</div>
        <div class="subtitle">点击卡片打开分析结果</div>
      </div>
      <div class="header-right">
        <a-input
          v-model="keyword"
          allow-clear
          placeholder="搜索 md5 / 文件名"
          class="search-input"
        />
        <a-button type="primary" :loading="loading" @click="loadList">刷新</a-button>
      </div>
    </div>

    <a-spin :loading="loading" style="width: 100%">
      <div v-if="!loading && !filteredItems.length" class="empty-state">
        <div class="empty-title">暂无已分析数据</div>
        <div class="empty-subtitle">完成一次分析后，这里会自动出现卡片列表</div>
      </div>

      <div v-else class="video-grid">
        <div
          v-for="item in filteredItems"
          :key="item.md5"
          class="card-sm"
          @click="openItem(item)"
        >
          <div class="card-content-wrapper">
            <!-- Delete Button -->
            <a-button 
              type="text" 
              status="danger" 
              class="delete-btn" 
              @click.stop="handleDelete(item)"
            >
              <template #icon><icon-delete /></template>
            </a-button>

            <!-- Format Label -->
            <div class="format-label">
              {{ getFormatLabel(item) }}
            </div>

            <!-- Cover Image or Placeholder -->
            <div 
              v-if="getCoverUrl(item)" 
              class="card-cover-box"
            >
              <img 
                :src="getCoverUrl(item)" 
                alt="Cover" 
                class="card-cover-img"
              />
            </div>
            <div v-else class="card-icon-placeholder">
              <svg width="64" height="64" fill="none" viewBox="0 0 256 256">
                <rect width="256" height="256" fill="#E14E1D" rx="60"></rect>
                <path fill="#fff" d="M48 38L56.6098 134.593H167.32L163.605 176.023L127.959 185.661L92.38 176.037L90.0012 149.435H57.9389L62.5236 200.716L127.951 218.888L193.461 200.716L202.244 102.655H85.8241L82.901 69.9448H205.041H205.139L208 38H48Z"></path>
              </svg>
            </div>

            <!-- Info Section -->
            <div class="card-info-section">
              <div class="info-title" :title="item.content_json?.title || item.display_name || item.md5">
                {{ item.content_json?.title || item.display_name || item.md5 }}
              </div>
              <div class="info-desc" :title="item.content_json?.summary">
                {{ item.content_json?.summary || '暂无视频摘要' }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </a-spin>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { IconDelete } from '@arco-design/web-vue/es/icon'
import { useConfigStore } from '../stores/config'

const router = useRouter()
const configStore = useConfigStore()

const backendBaseUrl = computed(() => (configStore.backend_base_url || '').replace(/\/+$/, ''))

const items = ref([])
const loading = ref(false)
const keyword = ref('')

const loadList = async () => {
  loading.value = true
  try {
    const res = await fetch(`${backendBaseUrl.value}/analysis/list?limit=200&offset=0`)
    if (!res.ok) {
      const txt = await res.text()
      throw new Error(txt || 'Load failed')
    }
    const data = await res.json()
    const rawItems = Array.isArray(data.items) ? data.items : []
    // Ensure content_json is an object
    items.value = rawItems.map(it => {
      if (it.content_json && typeof it.content_json === 'string') {
        try {
          it.content_json = JSON.parse(it.content_json)
        } catch (e) {
          console.warn('Failed to parse content_json for', it.md5, e)
        }
      }
      return it
    })
  } catch (e) {
    Message.error(e.message || '加载失败')
    items.value = []
  } finally {
    loading.value = false
  }
}

const norm = (s) => String(s || '').trim().toLowerCase()

const filteredItems = computed(() => {
  const q = norm(keyword.value)
  if (!q) return items.value
  return (items.value || []).filter((x) => {
    const d = norm(x.display_name)
    const m = norm(x.md5)
    const r = norm(x.source_ref)
    return d.includes(q) || m.includes(q) || r.includes(q)
  })
})

const openItem = (item) => {
  const md5 = norm(item?.md5)
  if (!md5) return
  router.push({ name: 'AiVideoSummary', query: { md5 } })
}

const shortMd5 = (md5) => {
  const s = String(md5 || '')
  if (s.length <= 12) return s
  return `${s.slice(0, 8)}...${s.slice(-4)}`
}

const copyMd5 = async (md5) => {
  const s = norm(md5)
  if (!s) return
  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(s)
      Message.success('已复制')
      return
    }
  } catch (e) {
  }

  try {
    const textArea = document.createElement('textarea')
    textArea.value = s
    textArea.style.position = 'fixed'
    textArea.style.opacity = '0'
    document.body.appendChild(textArea)
    textArea.select()
    document.execCommand('copy')
    document.body.removeChild(textArea)
    Message.success('已复制')
  } catch (e) {
    Message.error('复制失败')
  }
}

const getCoverUrl = (item) => {
  let segments = item.content_json?.segments
  if (!segments) return ''
  
  // Convert dict to list if needed
  if (!Array.isArray(segments) && typeof segments === 'object') {
    segments = Object.values(segments)
  }
  
  if (!Array.isArray(segments) || !segments.length) return ''
  
  // Sort by timestamp to ensure we get the first one chronologically
  const sortedSegments = [...segments].sort((a, b) => {
    return (a.timestamp || 0) - (b.timestamp || 0)
  })
  
  // Try to find image_url first (presigned url), then image_path
    const firstSeg = sortedSegments[0]
    const path = firstSeg.image_url || firstSeg.image_path
    
    if (!path) return ''
  
  // If it's already a full URL (http...), return it
  if (path.startsWith('http') || path.startsWith('blob:')) return path
  
  // Otherwise assume it's relative to static folder
  // backendBaseUrl is computed, so use .value
  // Note: path usually is "images/keyframe..." so we join with /static/
  const baseUrl = backendBaseUrl.value.replace(/\/+$/, '')
  const cleanPath = path.replace(/^\/+/, '')
  return `${baseUrl}/static/${cleanPath}`
}

const getFormatLabel = (item) => {
  if (item.mime_type) {
    // e.g. "video/mp4" -> "MP4"
    const parts = item.mime_type.split('/')
    if (parts.length > 1) {
       // Special case handling if needed
       return parts[1].toUpperCase()
    }
    return item.mime_type.toUpperCase()
  }
  // Fallback to asset_type or extension from display_name
  if (item.display_name) {
      const ext = item.display_name.split('.').pop()
      if (ext && ext !== item.display_name) return ext.toUpperCase()
  }
  return (item.asset_type || 'UNKNOWN').toUpperCase()
}

const handleDelete = async (item) => {
  Modal.warning({
    title: '确认删除',
    content: `确定要删除视频 "${item.display_name || item.md5}" 及其所有分析数据吗？此操作不可恢复。`,
    hideCancel: false,
    onOk: async () => {
      try {
        const res = await fetch(`${backendBaseUrl.value}/analysis/${item.md5}`, {
          method: 'DELETE'
        })
        if (!res.ok) {
           const txt = await res.text()
           throw new Error(txt || 'Delete failed')
        }
        Message.success('删除成功')
        loadList()
      } catch (e) {
        Message.error('删除失败: ' + e.message)
      }
    }
  })
}

onMounted(() => {
  loadList()
})
</script>

<style scoped>
.video-list-page {
  padding: 24px;
  min-height: 100vh;
  background: transparent;
}

.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
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

.header-right {
  display: flex;
  gap: 10px;
  align-items: center;
}

.search-input {
  width: 260px;
}

.video-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 24px;
}

/* Neo Brutalism data card */
.card-sm {
  background-color: #fff;
  width: 100%;
  border-radius: 5px;
  box-shadow: 5px 5px #323232;
  border: 3px solid #323232;
  box-sizing: border-box;
  cursor: pointer;
  transition: transform 0.1s ease, box-shadow 0.1s ease;
}

.card-sm:hover {
  transform: translate(2px, 2px);
  box-shadow: 3px 3px #323232;
}

.card-sm:active {
  transform: translate(5px, 5px);
  box-shadow: 0 0 #323232;
}

.card-content-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
  position: relative;
}

.delete-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 10;
  opacity: 0;
  transition: opacity 0.2s;
  background-color: rgba(255, 255, 255, 0.8) !important;
  border-radius: 4px;
}

.format-label {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 10;
  background-color: #323232;
  color: #fff;
  padding: 2px 8px;
  font-size: 12px;
  font-weight: 800;
  border-radius: 4px;
  box-shadow: 2px 2px 0 rgba(0,0,0,0.2);
  pointer-events: none;
}

.card-sm:hover .delete-btn {
  opacity: 1;
}

.card-cover-box {
  width: 100%;
  height: 160px;
  background: #f5f5f5;
  border-bottom: 3px solid #323232;
  overflow: hidden;
  position: relative;
}

.card-cover-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.5s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

.card-sm:hover .card-cover-img {
  transform: scale(1.1);
}

.card-icon-placeholder {
  width: 100%;
  height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f4dbda;
  border-bottom: 3px solid #323232;
}

.card-info-section {
  padding: 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: #fff;
}

.info-title {
  font-size: 16px;
  font-weight: 800;
  color: #323232;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.info-desc {
  font-size: 13px;
  color: #666;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.empty-state {
  border: 1px dashed var(--card-border);
  border-radius: 12px;
  padding: 40px 16px;
  text-align: center;
  background: var(--surface-1);
  color: var(--text-muted);
}

.empty-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-main);
  margin-bottom: 6px;
}

.empty-subtitle {
  font-size: 13px;
  color: var(--text-muted);
}
</style>

