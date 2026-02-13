<template>
  <div class="video-list-page">
    <div class="page-header">
      <div class="header-left">
        <div class="title">分析列表</div>
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

            <!-- Unread Dot -->
            <div v-if="!item.is_read" class="unread-dot"></div>

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
                {{ item.content_json?.summary || '暂无摘要' }}
              </div>
              
              <!-- Tags Section -->
              <div v-if="item.content_json?.tags && item.content_json.tags.length" class="tags-container">
                <span v-for="(tag, idx) in item.content_json.tags.slice(0, 3)" :key="idx" class="tag-badge">
                  #{{ tag }}
                </span>
              </div>

              <div class="info-meta">
                {{ formatTime(item.created_at) }}
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
import { useHistoryStore } from '../stores/history'

const router = useRouter()
const configStore = useConfigStore()
const historyStore = useHistoryStore()

const backendBaseUrl = computed(() => (configStore.backend_base_url || '').replace(/\/+$/, ''))

const items = ref([])
const loading = ref(false)
const keyword = ref('')

const norm = (s) => String(s || '').trim().toLowerCase()

const filteredItems = computed(() => {
  if (!keyword.value) return items.value
  const kw = keyword.value.toLowerCase()
  return items.value.filter(item => {
    const title = (item.content_json?.title || '').toLowerCase()
    const md5 = (item.md5 || '').toLowerCase()
    const dn = (item.display_name || '').toLowerCase()
    return title.includes(kw) || md5.includes(kw) || dn.includes(kw)
  })
})

const loadList = async () => {
  loading.value = true
  try {
    const res = await fetch(`${backendBaseUrl.value}/analysis/list?limit=100`)
    if (!res.ok) {
      const err = await res.text()
      throw new Error(err)
    }
    const data = await res.json()
    items.value = data.items || []
  } catch (e) {
    Message.error(e.message || '加载列表失败')
  } finally {
    loading.value = false
  }
}

const openItem = async (item) => {
  const md5 = norm(item?.md5)
  if (!md5) return

  // Add to history
  historyStore.addToHistory(item)

  // Mark as read locally first for instant feedback
  if (!item.is_read) {
    item.is_read = true
    // Call API to mark as read
    try {
      await fetch(`${backendBaseUrl.value}/analysis/${md5}/read`, { method: 'POST' })
    } catch (e) {
      console.error('Failed to mark as read', e)
    }
  }
  
  const at = String(item.asset_type || '').trim().toLowerCase()
  if (at === 'document' || at === 'file') {
    router.push({ name: 'AiFileSummary', query: { md5 } })
  } else {
    router.push({ name: 'AiVideoSummary', query: { md5 } })
  }
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

const formatTime = (ts) => {
  if (!ts) return ''
  // If timestamp is string, try to parse
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ts
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
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
  // Fix for plugin/extension items (Bilibili/YouTube) showing as TXT
  // If it comes from a URL source (plugin uses URL), and it's not explicitly audio/doc, treat as MP4
  const sk = String(item.source_kind || '').toLowerCase()
  const ref = String(item.source_ref || '').toLowerCase()
  
  if (sk === 'url' || ref.includes('bilibili.com') || ref.includes('youtube.com') || ref.includes('youtu.be')) {
      if (item.media_type === 'audio') return 'MP3'
      // If it's a video or unknown, default to MP4 for plugin items
      return 'MP4'
  }

  if (item.mime_type) {
    const mt = item.mime_type.toLowerCase()
    if (mt.includes('pdf')) return 'PDF'
    if (mt.includes('word') || mt.includes('document')) return 'DOCX'
    if (mt.includes('powerpoint') || mt.includes('presentation')) return 'PPTX'
    if (mt.includes('text') || mt.includes('plain')) return 'TXT'
    if (mt.includes('markdown')) return 'MD'
    
    // e.g. "video/mp4" -> "MP4"
    const parts = item.mime_type.split('/')
    if (parts.length > 1) {
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

/* Grid Layout */
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
  position: relative;
  display: flex;
  flex-direction: column;
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

.card-sm:hover .delete-btn {
  opacity: 1;
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

.unread-dot {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 10px;
  height: 10px;
  background-color: #f53f3f;
  border-radius: 50%;
  border: 2px solid #fff;
  z-index: 10;
  box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}

.card-cover-box {
  width: 100%;
  aspect-ratio: 16/9;
  overflow: hidden;
  background: #323232;
  border-bottom: 3px solid #323232;
  position: relative;
}

.card-cover-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.5s ease;
}

.card-sm:hover .card-cover-img {
  transform: scale(1.05);
}

.card-icon-placeholder {
  width: 100%;
  aspect-ratio: 16/9;
  background-color: #f0f0f0;
  border-bottom: 3px solid #323232;
  display: flex;
  align-items: center;
  justify-content: center;
}

.card-info-section {
  padding: 12px;
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.info-title {
  font-size: 16px;
  font-weight: 800;
  color: #323232;
  margin-bottom: 6px;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.info-desc {
  font-size: 12px;
  color: #666;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-bottom: 12px;
  flex: 1;
}

.tags-container {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.tag-badge {
  font-size: 10px;
  color: #323232;
  background: #e0e0e0;
  padding: 2px 6px;
  border-radius: 4px;
  white-space: nowrap;
  font-weight: 700;
  border: 1px solid #323232;
}

.info-meta {
  font-size: 11px;
  color: #888;
  margin-top: auto;
  border-top: 2px solid #f0f0f0;
  padding-top: 8px;
  font-weight: 600;
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

