<template>
  <div class="dashboard-page" :class="{ 'welcome-theme': showWelcome }">
    <!-- Welcome Page Layout -->
    <div v-if="showWelcome" class="welcome-container">
      <div class="welcome-header">
        <h1 class="welcome-title">👋 Hi~ Let me help you get started!</h1>
      </div>

      <div class="category-tabs">
        <div 
          v-for="cat in categories" 
          :key="cat.id"
          class="category-tab"
          :class="{ active: activeCategory === cat.id }"
          @click="activeCategory = cat.id"
        >
          <div class="category-icon">
            <component :is="cat.icon" :size="20" />
          </div>
          <span class="category-name">{{ cat.name }}</span>
          <div v-if="cat.isNew" class="new-badge">New</div>
        </div>
      </div>

      <div class="tools-grid">
        <div 
          v-for="tool in filteredTools" 
          :key="tool.id"
          class="tool-card"
          @click="handleToolClick(tool)"
        >
          <div class="tool-icon-box" :style="{ backgroundColor: tool.iconBg }">
            <component :is="tool.icon" :size="24" color="var(--on-dark)" />
          </div>
          <div class="tool-info">
            <div class="tool-name">{{ tool.name }}</div>
            <div v-if="tool.rating" class="tool-rating">
              <icon-star-fill v-for="i in 5" :key="i" :style="{ color: i <= tool.rating ? 'var(--accent-warn)' : 'var(--text-muted)' }" />
              <span class="featured-badge" v-if="tool.featured">Featured</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Original Analysis Layout (YouTube Summarizer) -->
    <div v-else-if="currentToolView === 'yt-summarizer'" class="analysis-container">
      <div class="analysis-header">
        <a-button type="text" @click="goHome" class="back-btn">
          <template #icon><icon-arrow-left /></template>
          Back to Home
        </a-button>
      </div>
      <a-grid :cols="24" :col-gap="24" :row-gap="24">
      <!-- Top Row: Main Overview (Video/Report) and Quick Stats -->
      <a-grid-item :span="16">
        <a-card :bordered="false" class="main-card overview-card">
          <div class="card-header-row">
            <span class="card-title">Overview</span>
            <span class="card-subtitle">Monthly</span>
          </div>
          
          <div class="video-section">
            <div v-if="!videoUrl && !loading" class="upload-area">
              <a-upload
                draggable
                :auto-upload="false"
                :show-file-list="false"
                @change="handleFileChange"
                accept="video/*"
              >
                <template #drag>
                  <div class="upload-drag-content">
                    <div class="icon-circle">
                      <icon-plus :style="{ fontSize: '32px', color: 'var(--accent-1)' }" />
                    </div>
                    <div class="upload-main-text">Drop your video here</div>
                    <div class="upload-sub-text">or click to browse files</div>
                  </div>
                </template>
              </a-upload>
            </div>

            <div v-else class="player-wrapper">
              <video 
                v-if="videoUrl"
                ref="videoRef"
                :src="videoUrl" 
                controls 
                class="main-video-player"
              />
              <div v-else class="loading-overlay">
                <a-spin :loading="loading" tip="Analyzing content...">
                  <template #icon>
                    <icon-loading :style="{ fontSize: '40px', color: 'var(--on-dark)' }" />
                  </template>
                  <div class="loading-msg">{{ progressMsg }}</div>
                </a-spin>
              </div>
            </div>
          </div>

          <div class="card-footer-stats">
            <div class="stat-item">
              <div class="stat-label">Total Time</div>
              <div class="stat-value">748 Hr</div>
              <div class="stat-month">April</div>
            </div>
            <div class="stat-item active">
              <div class="stat-label">Total Steps</div>
              <div class="stat-value">9.178 St</div>
              <div class="stat-month">April</div>
            </div>
            <div class="stat-item">
              <div class="stat-label">Target</div>
              <div class="stat-value">9200 St</div>
              <div class="stat-month">April</div>
            </div>
          </div>
        </a-card>
      </a-grid-item>

      <a-grid-item :span="8">
        <div class="right-column">
          <a-card :bordered="false" class="main-card daily-card purple-card">
            <div class="card-icon-box">
              <icon-thunderbolt :style="{ fontSize: '24px', color: 'var(--on-dark)' }" />
            </div>
            <div class="card-content-box">
              <div class="card-title-white">Daily Summary</div>
              <div class="card-desc-white">Quickly grasp the core points</div>
            </div>
          </a-card>

          <a-card :bordered="false" class="main-card daily-card pink-card">
            <div class="card-icon-box">
              <icon-fire :style="{ fontSize: '24px', color: 'var(--on-dark)' }" />
            </div>
            <div class="card-content-box">
              <div class="card-title-white">Key Insights</div>
              <div class="card-desc-white">AI-driven extraction of highlights</div>
            </div>
            <div class="card-action-circle">
              <icon-right :style="{ fontSize: '18px', color: 'var(--accent-2)' }" />
            </div>
          </a-card>
          
          <div class="bottom-stats-row">
            <div class="small-stat-card">
              <div class="small-stat-label">Processing Speed</div>
              <div class="small-stat-value">2.4x</div>
              <div class="small-stat-desc">Faster than real-time</div>
            </div>
          </div>
        </div>
      </a-grid-item>

      <!-- Bottom Row: Report and Keyframes -->
      <a-grid-item :span="16">
        <a-card v-if="report" :bordered="false" class="main-card report-card">
          <div class="card-header-row">
            <span class="card-title">📝 Analysis Report</span>
          </div>
          <div class="markdown-body" v-html="renderedReport"></div>
        </a-card>
        <div v-else class="empty-report-placeholder">
          <icon-file :style="{ fontSize: '48px', color: 'var(--text-muted)' }" />
          <p>Analysis report will appear here</p>
        </div>
      </a-grid-item>

      <a-grid-item :span="8">
        <a-card :bordered="false" class="main-card index-card">
          <div class="card-header-row">
            <span class="card-title">🎬 Keyframes Index</span>
            <span class="card-link">View All</span>
          </div>
          
          <div v-if="analysisData && analysisData.segments.length" class="segments-list">
            <div 
              v-for="(seg, idx) in analysisData.segments" 
              :key="idx" 
              class="segment-item"
              @click="jumpToTime(seg.timestamp)"
            >
              <div class="segment-thumb">
                <img :src="seg.image_url" :alt="seg.title" />
                <div class="segment-time-badge">{{ formatTime(seg.timestamp) }}</div>
              </div>
              <div class="segment-info">
                <div class="segment-title">{{ seg.title }}</div>
                <div class="segment-meta">{{ idx + 1 }} min ago</div>
              </div>
              <div class="segment-action">
                <icon-message :style="{ color: 'var(--text-muted)' }" />
              </div>
            </div>
          </div>
          <div v-else class="empty-index-state">
            <icon-empty :style="{ fontSize: '40px', color: 'var(--surface-1)' }" />
            <div class="empty-text">No index data available</div>
          </div>
        </a-card>
      </a-grid-item>
      </a-grid>
    </div>

    <!-- Floating Action Button -->
    <a-button 
      v-if="!showWelcome && videoFile && !loading && !videoUrl"
      type="primary" 
      size="large" 
      class="analyze-fab"
      @click="handleSubmit"
    >
      <template #icon><icon-play-arrow-fill /></template>
      Start Deep Analysis
    </a-button>
  </div>
</template>

<script setup>
import { ref, computed, markRaw } from 'vue'
import { useRouter } from 'vue-router'
import { useConfigStore } from '../stores/config'
import { Message } from '@arco-design/web-vue'
import { marked } from 'marked'
import { 
  Youtube, 
  Captions, 
  FileText, 
  Mic2, 
  Image as ImageIcon, 
  PenTool, 
  MessageSquare, 
  MoreHorizontal,
  ListVideo,
  Bell,
  Chrome
} from 'lucide-vue-next'

const configStore = useConfigStore()
const router = useRouter()
const videoRef = ref(null)
const progressPercent = ref(0)
  const loading = ref(false)
  const progressMsg = ref('')
  const report = ref('')
  const analysisData = ref(null)
const videoUrl = ref('')
const videoFile = ref(null)
const backendBaseUrl = computed(() => (configStore.backend_base_url || '').replace(/\/+$/, ''))

// Welcome Page States
const showWelcome = ref(true)
const activeCategory = ref('youtube')
const currentToolView = ref('') // 'yt-summarizer' or 'ai-video-summary'


const categories = [
  { id: 'youtube', name: 'AI YouTube', icon: markRaw(Youtube) },
  { id: 'transcriber', name: 'AI Transcriber', icon: markRaw(Captions) },
  { id: 'summarizer', name: 'AI Summarizer', icon: markRaw(FileText) },
  { id: 'voices', name: 'AI Voices', icon: markRaw(Mic2) },
  { id: 'images', name: 'AI Images', icon: markRaw(ImageIcon) },
  { id: 'writer', name: 'AI Writer', icon: markRaw(PenTool) },
  { id: 'chat', name: 'AI Chat', icon: markRaw(MessageSquare) },
  { id: 'more', name: 'More Tools', icon: markRaw(MoreHorizontal), isNew: true },
]

const tools = [
  { 
    id: 'yt-summarizer', 
    cat: 'youtube', 
    name: 'YouTube Video Summarizer', 
    icon: markRaw(ListVideo), 
    iconBg: 'var(--accent-1)' 
  },
  { 
    id: 'ai-video-summary', 
    cat: 'summarizer', 
    name: 'AI Video Summary', 
    icon: markRaw(FileText), 
    iconBg: 'var(--primary-color)' 
  },
  { 
    id: 'yt-transcript', 
    cat: 'youtube', 
    name: 'YouTube Transcript Generator', 
    icon: markRaw(Captions), 
    iconBg: 'var(--accent-1)' 
  },
  { 
    id: 'yt-subs', 
    cat: 'youtube', 
    name: 'YouTube Subscriptions', 
    icon: markRaw(Bell), 
    iconBg: 'var(--accent-1)' 
  },
  { 
    id: 'yt-ext', 
    cat: 'youtube', 
    name: 'YouTube Extension', 
    icon: markRaw(Chrome), 
    iconBg: 'var(--surface-0)', 
    rating: 5, 
    featured: true 
  },
]

const filteredTools = computed(() => {
  return tools.filter(t => t.cat === activeCategory.value)
})

const goHome = () => {
  showWelcome.value = true
  currentToolView.value = ''
  videoUrl.value = ''
  videoFile.value = null
}

const handleToolClick = (tool) => {
  if (tool.id === 'ai-video-summary') {
    router.push({ name: 'AiVideoSummary' })
    return
  }
  if (tool.id === 'yt-summarizer') {
    currentToolView.value = tool.id
    showWelcome.value = false
    // Reset data when switching tools
    videoUrl.value = ''
    videoFile.value = null
    report.value = ''
    analysisData.value = null
  } else {
    Message.info(`Tool "${tool.name}" is coming soon!`)
  }
}

const renderedReport = computed(() => {
  if (!report.value) return ''
  // Auto-link timestamps (HH:MM:SS) to enable click-to-jump
  // Regex looks for HH:MM:SS pattern and wraps it in a custom link format
  const linkedReport = report.value.replace(/(\d{2}:\d{2}:\d{2})/g, '[$1](timestamp:$1)')
  return marked(linkedReport)
})

const handleFileChange = (_, fileItem) => {
  videoFile.value = fileItem.file
  Message.success(`Selected: ${fileItem.file.name}`)
}

const readSseResponse = async (response) => {
  if (!response.body) throw new Error('ReadableStream not supported')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()

  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (!line.trim()) continue
      try {
        const data = JSON.parse(line)
        if (data.status === 'progress') {
          progressMsg.value = data.message

          if (data.message.includes('视频加载成功')) progressPercent.value = 5
          else if (data.message.includes('快速抽取音频流')) progressPercent.value = 10
          else if (data.message.includes('音频提取')) progressPercent.value = 15
          else if (data.message.includes('加载 Whisper 模型')) progressPercent.value = 20
          else if (data.message.includes('正在进行 ASR 加速转录')) progressPercent.value = 30
          else if (data.message.includes('转录完成')) progressPercent.value = 50
          else if (data.message.includes('ASR 转录')) progressPercent.value = 55
          else if (data.message.includes('发送给 LLM')) progressPercent.value = 60
          else if (data.message.includes('LLM 分析')) progressPercent.value = 75
          else if (data.message.includes('并行截取')) progressPercent.value = 80
          else if (data.message.includes('并行截图')) progressPercent.value = 85
          else if (data.message.includes('生成最终 Markdown')) progressPercent.value = 90
        } else if (data.status === 'success') {
          report.value = data.report
          analysisData.value = data.data
          videoUrl.value = data.video_url

          progressMsg.value = 'Analysis completed!'
          progressPercent.value = 100
          Message.success('Analysis completed!')
        } else if (data.status === 'error') {
          throw new Error(data.message)
        }
      } catch (e) {
        console.error('Error parsing line:', line, e)
      }
    }
  }
}

const handleSubmit = async () => {
  if (!videoFile.value) return
  
  if (!configStore.openai_api_key) {
    Message.warning('Please set API Key in Settings first')
    return
  }

  loading.value = true
  progressPercent.value = 0
  progressMsg.value = '请求上传地址...'
  report.value = ''
  analysisData.value = null
  
  const config = {
    openai_api_key: configStore.openai_api_key,
    openai_base_url: configStore.openai_base_url,
    llm_model: configStore.llm_model,
    model_size: configStore.model_size,
    device: configStore.device,
    compute_type: configStore.compute_type,
    capture_offset: configStore.capture_offset,
  }

  try {
    const presignRes = await fetch(`${backendBaseUrl.value}/minio/presign_upload`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filename: videoFile.value.name,
        content_type: videoFile.value.type || 'application/octet-stream',
      }),
    })

    if (!presignRes.ok) {
      const err = await presignRes.json().catch(() => null)
      throw new Error(err?.detail || '获取 MinIO 上传地址失败')
    }
    const presign = await presignRes.json()

    if (presign.video_url) videoUrl.value = presign.video_url

    await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open('PUT', presign.upload_url, true)
      try {
        xhr.setRequestHeader('Content-Type', videoFile.value.type || 'application/octet-stream')
      } catch (e) {}

      xhr.upload.onprogress = (evt) => {
        if (!evt.lengthComputable) return
        const pct = Math.round((evt.loaded / evt.total) * 95)
        progressPercent.value = Math.max(progressPercent.value, Math.min(95, pct))
        progressMsg.value = `Uploading: ${progressPercent.value}%`
      }

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) resolve()
        else reject(new Error(`上传失败: ${xhr.status}`))
      }
      xhr.onerror = () => reject(new Error('上传失败: 网络错误'))

      xhr.send(videoFile.value)
    })

    progressMsg.value = 'Preparing analysis...'
    progressPercent.value = Math.max(progressPercent.value, 95)

    const response = await fetch(`${backendBaseUrl.value}/analyze_path`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ video_path: presign.object_key, config }),
    })
    await readSseResponse(response)
  } catch (error) {
    Message.error(error.message || 'Unknown error during analysis')
    progressMsg.value = 'Error: ' + (error.message || 'Unknown error')
  } finally {
    loading.value = false
  }
}

const jumpToTime = (seconds) => {
  // Try ref first
  let videoEl = videoRef.value
  
  // Fallback to DOM query if ref is missing (can happen with v-if/v-else switching)
  if (!videoEl) {
    videoEl = document.querySelector('.summary-video-player') || document.querySelector('.main-video-player')
  }

  if (videoEl) {
    videoEl.currentTime = seconds
    videoEl.play().catch(e => console.log('Auto-play prevented:', e))
  } else {
    Message.warning('Video player not ready')
  }
}

const formatTime = (seconds) => {
  return new Date(seconds * 1000).toISOString().substr(11, 8)
}
</script>

<style scoped>
/* Welcome Page Styles */
.dashboard-page {
  min-height: 100vh;
  padding-bottom: 48px;
  position: relative;
  overflow-x: hidden;
}

.dashboard-page::before {
  content: '';
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  background:
    radial-gradient(900px 520px at 22% 12%, rgba(94, 106, 210, 0.22), transparent 55%),
    radial-gradient(720px 420px at 78% 18%, rgba(255, 143, 161, 0.14), transparent 55%),
    radial-gradient(900px 520px at 58% 86%, rgba(255, 200, 87, 0.10), transparent 60%),
    repeating-linear-gradient(
      90deg,
      rgba(255, 255, 255, 0.018) 0,
      rgba(255, 255, 255, 0.018) 1px,
      transparent 1px,
      transparent 7px
    );
}

.welcome-container,
.analysis-container {
  position: relative;
  z-index: 1;
}

.welcome-theme {
  background-color: transparent; /* 改为透明 */
  min-height: 100vh;
  width: 100%;
  margin: 0;
  padding: 56px 40px 72px 40px;
  color: var(--text-main);
  box-sizing: border-box;
}

.welcome-container {
  max-width: 1400px; /* 增加全屏下的内容宽度 */
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  align-items: stretch;
}

.welcome-header {
  text-align: left;
  margin-bottom: 22px;
  width: 100%;
}

.welcome-title {
  font-size: 28px;
  font-weight: 800;
  margin-bottom: 0;
  letter-spacing: -0.3px;
  color: var(--text-strong);
}

.category-tabs {
  display: flex;
  gap: 10px;
  margin-bottom: 28px;
  width: 100%;
  justify-content: flex-start;
  flex-wrap: wrap;
}

.category-tab {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 14px 18px;
  border-radius: 14px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  min-width: 110px;
  position: relative;
  color: var(--text-sub);
  background-color: var(--surface-2);
  border: 1px solid var(--card-border);
}

.category-tab:hover {
  background-color: var(--surface-3);
  border-color: var(--card-border-strong);
  color: var(--text-strong);
}

.category-tab.active {
  background-color: var(--surface-0);
  color: var(--text-strong);
  border-color: var(--hover-border);
}

.category-tab.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 18px;
  right: 18px;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(94, 106, 210, 0.9), transparent);
  border-radius: 999px;
}

.category-icon {
  margin-bottom: 12px;
}

.category-name {
  font-size: 14px;
  font-weight: 600;
}

.new-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  background-color: var(--danger);
  color: var(--on-dark);
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 10px;
  font-weight: 800;
}

.tools-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
  width: 100%;
}

.tool-card {
  background-color: var(--surface-2);
  backdrop-filter: blur(10px);
  border: 1px solid var(--card-border);
  border-radius: 16px;
  padding: 18px;
  display: flex;
  align-items: center;
  gap: 16px;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: none;
  position: relative;
  overflow: hidden;
}

.tool-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: -50%;
  width: 50%;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(94, 106, 210, 0.9), transparent);
  opacity: 0;
}

.tool-card:hover {
  transform: translateY(-2px);
  border-color: var(--card-border-strong);
  background-color: var(--surface-3);
}

.tool-card:hover::before {
  opacity: 1;
  animation: toolCardSheen 1.8s ease-in-out infinite;
}

@keyframes toolCardSheen {
  from { transform: translateX(0); }
  to { transform: translateX(320%); }
}

.tool-icon-box {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.tool-info {
  flex: 1;
}

.tool-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-strong);
  line-height: 1.4;
}

.tool-rating {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.featured-badge {
  margin-left: 8px;
  background-color: var(--hover-bg);
  color: var(--text-strong);
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 6px;
  font-weight: 700;
  border: 1px solid var(--card-border-strong);
}

/* Dashboard Analysis Page Styles (Original) */
.analysis-container {
  padding: 32px 40px 72px 40px;
  background-color: transparent;
  backdrop-filter: blur(14px);
  min-height: 100vh;
  box-sizing: border-box;
}

.analysis-header {
  margin-bottom: 20px;
}

.back-btn {
  color: var(--card-text);
  font-weight: 600;
}

.back-btn:hover {
  background-color: var(--hover-bg);
}

.main-card {
  background-color: var(--surface-2);
  backdrop-filter: blur(14px);
  border-radius: 16px;
  box-shadow: none;
  overflow: hidden;
  border: 1px solid var(--card-border);
}

.overview-card {
  padding: 30px;
  background-color: var(--overview-bg);
  color: var(--on-dark);
  border: 1px solid var(--overview-border);
}

.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.card-title {
  font-size: 18px;
  font-weight: 800;
  color: var(--card-text);
}

.overview-card .card-title {
  color: var(--on-dark);
}

.card-subtitle {
  font-size: 14px;
  font-weight: 600;
  color: var(--on-dark-muted);
}

.video-section {
  background-color: var(--overview-overlay);
  border-radius: 16px;
  height: 400px;
  overflow: hidden;
  margin-bottom: 30px;
  position: relative;
  border: 1px solid rgba(255, 255, 255, 0.10);
}

.upload-area {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

:deep(.arco-upload-wrapper), :deep(.arco-upload-list) {
  width: 100%;
  height: 100%;
}

:deep(.arco-upload-drag) {
  background: transparent;
  border: 2px dashed var(--overview-border);
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
}

.upload-drag-content {
  color: var(--on-dark);
  text-align: center;
}

.icon-circle {
  width: 64px;
  height: 64px;
  background-color: var(--primary-color);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
}

.upload-main-text {
  font-size: 18px;
  font-weight: 800;
  margin-bottom: 8px;
}

.upload-sub-text {
  font-size: 14px;
  opacity: 0.7;
}

.player-wrapper {
  width: 100%;
  height: 100%;
  background-color: var(--media-bg);
  display: flex;
  align-items: center;
  justify-content: center;
}

.main-video-player {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.loading-overlay {
  text-align: center;
  color: var(--on-dark);
}

.loading-msg {
  margin-top: 15px;
  font-weight: 600;
}

.card-footer-stats {
  display: flex;
  gap: 20px;
}

.stat-item {
  flex: 1;
  background-color: var(--overview-overlay);
  padding: 20px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.10);
}

.stat-item.active {
  background-color: var(--overview-overlay-strong);
  border: 1px solid var(--overview-border);
}

.stat-label {
  font-size: 12px;
  font-weight: 700;
  opacity: 0.6;
  text-transform: uppercase;
  margin-bottom: 5px;
}

.stat-value {
  font-size: 20px;
  font-weight: 800;
  margin-bottom: 5px;
}

.stat-month {
  font-size: 12px;
  opacity: 0.5;
}

.right-column {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.daily-card {
  padding: 30px;
  display: flex;
  align-items: center;
  gap: 20px;
  height: 140px;
  position: relative;
  border-radius: 16px;
}

.purple-card {
  background-color: var(--primary-color);
}

.pink-card {
  background-color: var(--card-text);
}

.card-icon-box {
  width: 60px;
  height: 60px;
  background-color: var(--overview-overlay-strong);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(255, 255, 255, 0.10);
}

.card-title-white {
  font-size: 18px;
  font-weight: 800;
  color: var(--on-dark);
  margin-bottom: 4px;
}

.card-desc-white {
  font-size: 13px;
  color: var(--on-dark-muted);
  font-weight: 500;
}

.card-action-circle {
  position: absolute;
  right: 20px;
  bottom: 20px;
  width: 36px;
  height: 36px;
  background-color: var(--surface-0);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: none;
  border: 1px solid var(--card-border);
}

.bottom-stats-row {
  background-color: var(--surface-0);
  border-radius: 16px;
  padding: 30px;
  box-shadow: none;
  border: 1px solid var(--card-border);
}

.small-stat-card {
  text-align: left;
}

.small-stat-label {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-muted);
  margin-bottom: 10px;
}

.small-stat-value {
  font-size: 32px;
  font-weight: 800;
  color: var(--card-text);
  margin-bottom: 5px;
}

.small-stat-desc {
  font-size: 12px;
  color: var(--success);
  font-weight: 700;
}

.report-card {
  padding: 35px;
}

.markdown-body {
  color: var(--card-text-muted);
  line-height: 1.8;
}

.detail-text-area {
  padding: 20px;
  overflow-y: auto;
  height: 100%; /* Fill available height */
}

.keyframes-tab-content {
  height: 100%;
  overflow-y: auto;
  padding: 20px;
}

:deep(.markdown-body h1), :deep(.markdown-body h2) {
  color: var(--card-text);
  border-bottom: none;
  margin-top: 30px;
}

:deep(.markdown-body h3) {
  color: var(--card-text);
  margin-top: 24px;
  margin-bottom: 12px;
  font-size: 1.25em;
}

:deep(.markdown-body table) {
  width: 100%;
  border-collapse: collapse;
  margin: 20px 0;
  font-size: 14px;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: var(--shadow-2);
}

:deep(.markdown-body th), :deep(.markdown-body td) {
  border: 1px solid var(--card-border);
  padding: 12px 16px;
  text-align: left;
}

:deep(.markdown-body th) {
  background-color: var(--surface-1);
  font-weight: 600;
  color: var(--card-text-muted);
  text-transform: uppercase;
  font-size: 12px;
  letter-spacing: 0.05em;
}

:deep(.markdown-body tr:hover) {
  background-color: var(--hover-bg);
}

:deep(.markdown-body img) {
  max-width: 100%;
  border-radius: 12px;
  margin: 16px 0;
  box-shadow: var(--shadow-2);
}

.empty-report-placeholder {
  background-color: var(--surface-0);
  border-radius: 16px;
  height: 300px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-weight: 600;
  border: 1px dashed var(--card-border-strong);
}

.index-card {
  padding: 25px;
  height: 100%;
}

.card-link {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 700;
  cursor: pointer;
}

.segments-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.segment-item {
  display: flex;
  align-items: center;
  gap: 15px;
  cursor: pointer;
  transition: all 0.2s;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid transparent;
}

.segment-item:hover {
  transform: translateX(2px);
  background-color: var(--hover-bg);
  border-color: var(--card-border-strong);
}

.segment-thumb {
  width: 80px;
  height: 60px;
  border-radius: 10px;
  overflow: hidden;
  position: relative;
  flex-shrink: 0;
  border: 1px solid var(--card-border);
}

.segment-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.segment-time-badge {
  position: absolute;
  bottom: 4px;
  right: 4px;
  background-color: var(--badge-bg);
  color: var(--on-dark);
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 4px;
  font-weight: 700;
}

.segment-info {
  flex: 1;
}

.segment-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--card-text);
  line-height: 1.3;
  margin-bottom: 4px;
}

.segment-meta {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 600;
}

.video-actions-bar {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.secondary-actions {
  display: flex;
  gap: 12px;
}

.secondary-actions .arco-btn {
  flex: 1;
}

.analysis-progress {
  background: var(--surface-1);
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--card-border);
}

.progress-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 12px;
}

.progress-text {
  color: var(--card-text);
  font-weight: 500;
}

.progress-percent {
  color: var(--text-sub);
}

.segment-action {
  opacity: 0.5;
}

.empty-index-state {
  height: 300px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
}

.empty-text {
  margin-top: 15px;
  font-weight: 600;
}

.analyze-fab {
  position: fixed;
  bottom: 40px;
  right: 400px;
  height: 60px;
  padding: 0 35px;
  border-radius: 16px;
  font-size: 16px;
  font-weight: 800;
  background-color: var(--primary-color);
  border: none;
  box-shadow: var(--shadow-1);
  z-index: 100;
}

.analyze-fab:hover {
  background-color: var(--primary-hover);
  transform: translateY(-2px);
  box-shadow: var(--shadow-2);
}
</style>
