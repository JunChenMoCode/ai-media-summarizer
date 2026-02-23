<template>
  <div class="history-page">
    <div class="page-header">
      <div class="header-left">
        <div class="title">历史记录</div>
        <div class="subtitle">最近查看的分析内容</div>
      </div>
      <div class="header-right">
        <a-button @click="clearHistory">清空历史</a-button>
      </div>
    </div>

    <div v-if="!history.length" class="empty-state">
      <div class="empty-title">暂无历史记录</div>
      <div class="empty-subtitle">您查看过的分析将显示在这里</div>
    </div>

    <div v-else class="video-grid">
      <div
        v-for="item in history"
        :key="item.md5"
        class="card-sm"
        @click="openItem(item)"
      >
        <div class="card-content-wrapper">
          <!-- Format Label -->
          <div class="format-label" v-if="getFormatLabel(item)">
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
              :class="['card-cover-img', { 'default-cover-img': isDefaultCover(getCoverUrl(item)) }]"
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
            <div class="info-title" :title="getItemTitle(item)">
              {{ getItemTitle(item) }}
            </div>
            <div class="info-desc" :title="item.summary">
              {{ item.summary || '暂无摘要' }}
            </div>
            
            <!-- Tags Section -->
            <div v-if="item.tags && item.tags.length" class="tags-container">
              <span v-for="(tag, idx) in item.tags.slice(0, 3)" :key="idx" class="tag-badge">
                #{{ tag }}
              </span>
            </div>

            <div class="info-meta">
              上次查看: {{ formatTime(item.timestamp) }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useHistoryStore } from '../stores/history'
import { useConfigStore } from '../stores/config'
import { Message } from '@arco-design/web-vue'
import coverMD from '../assert/author_bg_card/MD.jpg'
import coverMP4 from '../assert/author_bg_card/MP4.jpg'
import coverPDF from '../assert/author_bg_card/PDF.jpg'
import coverTXT from '../assert/author_bg_card/TXT.jpg'

const router = useRouter()
const historyStore = useHistoryStore()
const configStore = useConfigStore()
const history = computed(() => historyStore.history)
const backendBaseUrl = computed(() => (configStore.backend_base_url || '').replace(/\/+$/, ''))

const norm = (s) => String(s || '').trim().toLowerCase()
const decodeTitle = (s) => {
  const v = String(s || '').trim()
  if (!v) return v
  if (!/%[0-9A-Fa-f]{2}/.test(v)) return v
  try {
    return decodeURIComponent(v)
  } catch {
    return v
  }
}

const getItemTitle = (item) => decodeTitle(item?.title || item?.display_name || item?.md5)

onMounted(async () => {
  const base = backendBaseUrl.value
  if (!base) return
  // Always try to hydrate/refresh to get latest metadata (cover, title, type)
  try {
    const res = await fetch(`${base}/analysis/list?limit=200`)
    if (!res.ok) return
    const data = await res.json()
    const items = Array.isArray(data.items) ? data.items : []
    const map = new Map(items.map(it => [norm(it?.md5), it]))
    historyStore.history.forEach(h => {
      const it = map.get(norm(h?.md5))
      if (!it) return
      // Update fields if available in remote
      if (it.display_name) h.display_name = it.display_name
      if (it.mime_type) h.mime_type = it.mime_type
      if (it.asset_type) h.asset_type = it.asset_type
      if (it.source_ref) h.source_ref = it.source_ref
      
      const nextTitle = it.content_json?.title || it.display_name || h.display_name
      if (nextTitle) {
        const cur = String(h.title || '').trim()
        const md5 = String(h.md5 || '').trim()
        if (!cur || cur === md5) h.title = nextTitle
      }
      if (it.content_json?.summary) h.summary = it.content_json.summary
      // Also update cover related info if needed
      if (it.content_json) {
        h.content_json = it.content_json
        if (it.content_json.tags) h.tags = it.content_json.tags
      }
    })
  } catch (e) {
    return
  }
})

const clearHistory = () => {
  historyStore.clearHistory()
  Message.success('历史记录已清空')
}

const openItem = (item) => {
  const md5 = item.md5
  if (!md5) return
  
  // Re-add to move to top
  historyStore.addToHistory(item)

  const at = String(item.asset_type || '').trim().toLowerCase()
  if (at === 'document' || at === 'file') {
    router.push({ name: 'AiFileSummary', query: { md5 } })
  } else {
    router.push({ name: 'AiVideoSummary', query: { md5 } })
  }
}

const getCoverUrl = (item) => {
  // Use cover_url if available
  if (item.cover_url) return item.cover_url
  // Or check content_json structure
  if (item.content_json?.cover_url) return item.content_json.cover_url
  // Or try to find first segment image
  if (item.content_json?.segments && item.content_json.segments.length > 0) {
    const seg = item.content_json.segments[0]
    if (seg.image_url) return seg.image_url
  }
  const fmt = getFormatLabel(item)
  if (fmt === 'MD') return coverMD
  if (fmt === 'PDF') return coverPDF
  if (fmt === 'TXT') return coverTXT
  if (fmt === 'MP4') return coverMP4
  return ''
}

const isDefaultCover = (url) => {
  return url === coverMD || url === coverPDF || url === coverTXT || url === coverMP4
}

const getFormatLabel = (item) => {
  // 1. 优先使用 display_name 或 title 的后缀名
  const name = String(item.display_name || item.title || '').trim()
  if (name) {
    const parts = name.split('.')
    if (parts.length > 1) {
      const ext = parts.pop().toUpperCase()
      // 常见文档/音视频格式直接返回
      if (['PDF', 'DOC', 'DOCX', 'PPT', 'PPTX', 'TXT', 'MD', 'MP4', 'MP3', 'MOV', 'AVI', 'MKV', 'WAV', 'M4A'].includes(ext)) {
        return ext
      }
    }
  }

  // 2. 其次检查 mime_type
  if (item.mime_type) {
    const mt = item.mime_type.toLowerCase()
    if (mt.includes('pdf')) return 'PDF'
    if (mt.includes('word') || mt.includes('document')) return 'DOCX'
    if (mt.includes('powerpoint') || mt.includes('presentation')) return 'PPTX'
    if (mt.includes('markdown')) return 'MD'
    if (mt.includes('text') || mt.includes('plain')) return 'TXT'
    if (mt.includes('octet-stream')) {
        // 如果是 octet-stream，尝试再次从 display_name 提取，或者返回 'FILE'
        if (item.display_name) {
             const ext = item.display_name.split('.').pop()
             if (ext && ext !== item.display_name) return ext.toUpperCase()
        }
        return 'FILE'
    }
    
    const parts = item.mime_type.split('/')
    if (parts.length > 1) {
       return parts[1].toUpperCase()
    }
    return item.mime_type.toUpperCase()
  }

  // 3. 其次检查 asset_type
  const at = (item.asset_type || '').toUpperCase()
  if (at === 'VIDEO' || at === 'AUDIO' || at === 'UNKNOWN') return 'VIDEO'
  if (at === 'DOCUMENT' || at === 'FILE') return 'DOC'

  // 4. 内容特征检查
  // 如果有 segments，通常是音视频
  if (item.content_json?.segments?.length > 0) return 'VIDEO'

  // 5. 来源 URL 特征
  const sr = String(item.source_ref || '').toLowerCase()
  if (sr.includes('bilibili')) return 'BILI'
  if (sr.includes('youtube') || sr.includes('youtu.be')) return 'YT'

  return at || 'FILE'
}

const formatTime = (ts) => {
  if (!ts) return ''
  return new Date(ts).toLocaleString()
}
</script>

<style scoped>
/* Reuse styles from Video.vue or similar */
.history-page {
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

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
  color: var(--text-muted);
}

.empty-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 8px;
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

.default-cover-img {
  object-position: 50% 35%;
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

/* CSS Variables */
:root {
  --bg-card: #ffffff;
  --bg-card-hover: #f7f8fa;
  --text-main: #1d2129;
  --text-muted: #86909c;
  --border-color: #f2f3f5;
  --primary-color: #165dff;
  --primary-color-hover: #4080ff;
  --primary-color-bg: #e8f3ff;
}

[data-theme='dark'] {
  --bg-card: #232324;
  --bg-card-hover: #2a2a2b;
  --text-main: #f2f3f5;
  --text-muted: #86909c;
  --border-color: #3e3e3e;
  --primary-color: #165dff;
  --primary-color-hover: #4080ff;
  --primary-color-bg: rgba(22, 93, 255, 0.1);
}
</style>
