<template>
  <div class="video-summary-container">
    <div class="summary-content">
      <!-- Left Column: Video & Transcript -->
      <div class="left-panel">
        <input
          ref="localVideoInputRef"
          type="file"
          accept="video/*,audio/*"
          style="display: none"
          @change="handleLocalVideoInputChange"
        />
        <div class="video-topbar">
          <div class="video-topbar-input">
            <a-input-search
              v-model="videoUrlInput"
              placeholder="粘贴视频/音频链接，回车加载"
              button-text="加载"
              search-button
              allow-clear
              :disabled="importingVideo"
              @search="handleUrlSubmit"
            />
          </div>
          <a-button type="outline" @click="openLocalVideoPicker">
            <template #icon><icon-upload /></template>
            上传本地视频/音频
          </a-button>
        </div>
        <div
          class="video-wrapper"
          @dragenter.prevent="handleVideoDragEnter"
          @dragover.prevent="handleVideoDragOver"
          @dragleave.prevent="handleVideoDragLeave"
          @drop.prevent="handleVideoDrop"
        >
          <div v-if="loading" class="video-overlay">
            <ChipLoader :progress="progressPercent" :text="progressMsg" />
          </div>
          <div v-else-if="videoDragActive" class="video-drag-overlay">
            <div class="video-drag-overlay-inner">
              <div class="video-drag-title">松开即可加载本地视频/音频</div>
              <div class="video-drag-sub">支持 mp4/mov/mkv/webm/mp3/m4a/wav 等</div>
            </div>
          </div>
          <div v-if="!videoUrl" class="video-placeholder" @click="openLocalVideoPicker">
            <div class="placeholder-content">
              <icon-plus :style="{ fontSize: '40px' }" />
              <p class="placeholder-title">点击添加媒体源</p>
              <p class="placeholder-desc">支持本地视频/音频上传或粘贴 URL</p>
            </div>
          </div>
          <video
            v-else-if="mediaType !== 'audio'"
            ref="videoRef"
            :src="videoUrl"
            controls
            class="summary-video-player"
            @timeupdate="handleTimeUpdate"
            @play="handleVideoPlay"
            crossorigin="anonymous"
          ></video>
          <div v-else class="audio-stage">
            <div class="audio-center-wave">
              <AudioParticleVisualizer
                ref="audioVizRef"
                :mediaEl="videoRef"
                :active="!!videoUrl"
                variant="radial"
                layout="inline"
                :interactive="false"
                :showHint="false"
                :barDensity="9"
              />
            </div>
            <audio
              ref="videoRef"
              :src="videoUrl"
              preload="metadata"
              class="summary-audio-player"
              @loadedmetadata="handleAudioLoadedMetadata"
              @timeupdate="handleAudioTimeUpdate"
              @play="handleAudioPlay"
              @pause="handleAudioPause"
              @ended="handleAudioEnded"
              @error="handleAudioError"
              crossorigin="anonymous"
            ></audio>
            <div class="summary-audio-controls">
              <button class="audio-ctrl-btn" type="button" :disabled="!audioCanPlay" @click="toggleAudioPlayback">
                <icon-play v-if="!audioPlaying" :style="{ width: '18px', height: '18px' }" />
                <icon-pause v-else :style="{ width: '18px', height: '18px' }" />
              </button>
              <div class="audio-time">{{ formatClock(currentTime) }}</div>
              <div class="audio-progress-wrap">
                <input
                  class="audio-progress"
                  type="range"
                  min="0"
                  max="1000"
                  step="1"
                  :value="audioSeekValue"
                  :disabled="!audioSeekable"
                  :style="{ '--progress': `${audioSeekPercent}%` }"
                  @pointerdown="handleSeekPointerDown"
                  @input="handleSeekInput"
                  @change="handleSeekChange"
                />
              </div>
              <div class="audio-time">{{ formatClock(audioDuration) }}</div>
            </div>
          </div>
        </div>

        <div v-if="videoUrl" class="subtitle-bar">
          <div class="subtitle-lines">
            <div
              v-for="(line, idx) in subtitleLines"
              :key="idx"
              class="subtitle-text"
              :class="idx === 0 ? 'subtitle-text-cn' : 'subtitle-text-en'"
            >
              {{ line }}
            </div>
          </div>
        </div>
        
        <div class="video-actions-bar">
          <a-button type="primary" size="large" @click="handleSubmit" :loading="loading" long>
            <template #icon><icon-robot /></template>
            智能分析与总结
          </a-button>

          <div class="secondary-actions">
            <a-button type="outline" @click="toggleBilingual" :loading="translating">
              EN 双字幕
            </a-button>
            <a-button type="outline" @click="handleGenerateMindmap">
              <template #icon><icon-workflow /></template>
              生成思维导图
            </a-button>
            <a-button type="outline" @click="handleGenerateNotes">
              <template #icon><icon-book-open /></template>
              生成文稿笔记
            </a-button>
            <a-button v-if="mediaType !== 'audio'" type="outline" @click="handleCaptureFrame" :loading="coursewareLoading">
              <template #icon><icon-camera /></template>
              截取当前帧
            </a-button>
            <a-button type="outline"><icon-share-internal /> 分享</a-button>
          </div>
        </div>

        <div class="summary-below-video">
          <div v-if="analysisData">
            <!-- Dynamic Content Mode -->
            <div v-if="activeSegment" class="dynamic-segment-content">
              <div class="segment-header">
                <span class="segment-time-badge">{{ formatTime(activeSegment.timestamp) }}</span>
                <h3 class="segment-title">{{ activeSegment.title }}</h3>
              </div>
              <div class="segment-body">
                 <ul class="segment-points-list">
                   <li v-for="(point, idx) in activeSegment.points" :key="idx">
                     <span class="point-bullet">•</span>
                     <span class="point-text">{{ point }}</span>
                   </li>
                 </ul>
              </div>
            </div>
            
            <!-- Fallback to static summary -->
            <div v-else>
              <h2>{{ analysisData.title }}</h2>
              <p>{{ analysisData.summary }}</p>
              <h3>Knowledge Points</h3>
              <ul class="highlights-list">
                <li v-for="(item, idx) in analysisData.knowledge_table" :key="idx">
                  <span class="bullet" :style="{ background: idx % 2 === 0 ? 'var(--accent-1)' : 'var(--accent-2)' }"></span>
                  <strong>{{ item.point }}:</strong> {{ item.content }} ({{ item.difficulty }})
                </li>
              </ul>
            </div>
          </div>
          <div v-else class="empty-state-below">
            <p>分析完成后，此处将显示视频摘要与核心知识点。</p>
          </div>
        </div>
      </div>

      <!-- Right Column: Tabs & Content -->
      <div class="right-panel">
        <div class="summary-header">
          <a-button type="text" @click="goHome" class="back-btn">
            <template #icon><icon-arrow-left /></template>
            Back to Home
          </a-button>
          <div class="summary-header-title" :title="currentContentTitle">{{ currentContentTitle }}</div>
        </div>
        <a-tabs v-model:active-key="activeRightTab" type="line" size="medium" :animation="true" class="summary-tabs">
          <!-- Tab 1: Transcript -->
          <a-tab-pane key="transcript" title="字幕">
            <div class="transcript-tab-content">
              <div class="transcript-header">
                <h3>原始字幕</h3>
                <div class="transcript-actions">
                  <a-button type="text" size="mini" @click="handleCopyTranscript"><icon-copy /></a-button>
                  <a-button type="text" size="mini"><icon-download /></a-button>
                </div>
              </div>
              <div class="transcript-list">
                <div v-if="transcriptData.length" class="transcript-items-container">
                  <div v-for="(item, idx) in transcriptData" :key="idx" class="transcript-item" @click="jumpToTime(item.timestamp)">
                    <span class="timestamp">{{ formatTime(item.timestamp) }}</span>
                    <div class="transcript-texts">
                      <p class="text">{{ item.text }}</p>
                      <p v-if="bilingualEnabled" class="text-en">{{ translatedTranscriptData[idx]?.text || '' }}</p>
                    </div>
                  </div>
                </div>
                <div v-else class="empty-transcript">
                  <p v-if="loading">正在转录视频...</p>
                  <p v-else>暂无字幕数据</p>
                </div>
              </div>
            </div>
          </a-tab-pane>

          <!-- Tab 2: MindMap -->
          <a-tab-pane key="mindmap" title="思维导图">
            <div class="mindmap-tab-content">
              <div v-if="mindmapLoading" class="mindmap-loading">
                  <icon-refresh-cw spin :style="{ fontSize: '48px', color: 'var(--primary-color)' }" />
                  <p>正在生成思维导图...</p>
              </div>
              <MindMap v-else-if="mindmapData" :data="mindmapData" />
              <div v-else class="mindmap-placeholder">
                <icon-workflow :style="{ fontSize: '48px', color: 'var(--text-muted)' }" />
                <p>点击上方“生成思维导图”按钮</p>
              </div>
            </div>
          </a-tab-pane>

          <!-- Tab 3: Detail -->
          <a-tab-pane key="detail" title="图文详解">
            <div class="detail-text-area">
              <div v-if="report" class="markdown-body" v-html="renderedReport" @click="handleMarkdownClick"></div>
              <div v-else class="empty-state">
                <icon-file :style="{ fontSize: '48px', color: 'var(--text-muted)' }" />
                <p>点击右上角“总结”生成详解报告</p>
              </div>
            </div>
          </a-tab-pane>

          <!-- Tab: Notes -->
          <a-tab-pane key="notes" title="文稿笔记">
            <div class="detail-text-area">
              <div v-if="notesLoading" class="mindmap-loading">
                  <icon-refresh-cw spin :style="{ fontSize: '48px', color: 'var(--primary-color)' }" />
                  <p>正在生成文稿笔记...</p>
              </div>
              <div v-else-if="notesData" class="markdown-body" v-html="renderMarkdown(notesData)"></div>
              <div v-else class="empty-state">
                <icon-book-open :style="{ fontSize: '48px', color: 'var(--text-muted)' }" />
                <p>点击上方“生成文稿笔记”按钮</p>
              </div>
            </div>
          </a-tab-pane>

          <!-- Tab: Refined Transcript -->
          <a-tab-pane key="refined_transcript" title="文稿">
            <div class="detail-text-area">
               <div v-if="transcriptData.length" class="markdown-body">
                  <p v-for="(para, idx) in formattedTranscriptParagraphs" :key="idx" style="text-indent: 2em;">
                    {{ para }}
                  </p>
               </div>
               <div v-else class="empty-state">
                  <icon-file-text :style="{ fontSize: '48px', color: 'var(--text-muted)' }" />
                  <p>暂无文稿数据</p>
               </div>
            </div>
          </a-tab-pane>

           <!-- Tab: Courseware -->
          <a-tab-pane v-if="mediaType !== 'audio'" key="courseware" title="课件">
            <div class="courseware-tab-content">
              <div v-if="coursewareLoading" class="mindmap-loading">
                  <icon-camera spin :style="{ fontSize: '48px', color: 'var(--primary-color)' }" />
                  <p>正在截取...</p>
              </div>
              <div v-else-if="coursewareData && coursewareData.length" class="courseware-grid-wrap">
                <div class="courseware-actions">
                  <a-button type="primary" long :loading="coursewareOcrLoading" @click="handleCoursewareOcr">
                    识别图中内容
                  </a-button>
                </div>
                <div class="courseware-grid">
                  <div v-for="(item, idx) in coursewareData" :key="idx" class="courseware-item" @click="jumpToTime(item.timestamp)">
                    <div class="courseware-thumb">
                      <a-image
                        :src="item.url"
                        :alt="'Screenshot ' + (idx + 1)"
                        fit="cover"
                        width="100%"
                        height="100%"
                      />
                      <div class="courseware-select-wrap" @click.stop>
                        <UVCheckbox
                          class="courseware-select"
                          :modelValue="isCoursewareSelected(getCoursewareKey(item, idx))"
                          @update:modelValue="(checked) => setCoursewareSelected(getCoursewareKey(item, idx), checked)"
                        />
                      </div>
                    </div>
                    <div class="courseware-info">
                      <div class="info-left">
                        <div class="page-num">Page {{ idx + 1 }}</div>
                        <div class="time-stamp">
                           <icon-clock-circle /> {{ formatTime(item.timestamp) }}
                        </div>
                      </div>
                      <div class="info-right">
                        <a-button size="mini" status="danger" @click.stop="handleDeleteCourseware(idx)">
                          <template #icon><IconTrash /></template>
                        </a-button>
                        <a-button type="text" size="mini" :href="item.url" download target="_blank" @click.stop>
                          <icon-download />
                        </a-button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div v-else class="empty-state">
                <icon-camera :style="{ fontSize: '48px', color: 'var(--text-muted)' }" />
                <p>点击上方“截取当前帧”按钮保存重要画面</p>
              </div>
            </div>
          </a-tab-pane>

          <!-- Tab 4: Chat -->
          <a-tab-pane key="chat" title="AI 对话">
            <div class="chat-tab-content">
              <div ref="chatListRef" class="chat-messages">
                <div v-if="!chatMessages.length" class="chat-empty">
                  <icon-message :style="{ fontSize: '48px', color: 'var(--text-muted)' }" />
                  <p>开始与 AI 讨论视频内容</p>
                </div>
                <div v-else class="chat-message-list">
                  <div v-for="(msg, idx) in chatMessages" :key="idx" class="chat-message" :class="[msg.role, msg.kind]">
                    <div class="chat-bubble-wrapper" v-if="msg.role === 'user'">
                      <div class="chat-bubble">{{ msg.content }}</div>
                      <div class="chat-delete-btn" @click="handleDeleteMessage(idx)">
                        <IconTrash />
                      </div>
                    </div>
                    <div class="chat-bubble-container" v-else>
                      <div class="chat-delete-btn" @click="handleDeleteMessage(idx)">
                        <IconTrash />
                      </div>
                      <div v-if="msg.kind === 'reasoning'" class="reasoning-box">
                        <details :open="msg.reasoningExpanded" @toggle="(e) => msg.reasoningExpanded = e.target.open">
                          <summary>
                            <span class="summary-left">
                              <span class="summary-icon"><icon-robot /></span>
                              <span class="summary-title">思考过程</span>
                            </span>
                            <span class="summary-right">
                              <span class="summary-hint">{{ msg.reasoningExpanded ? '收起' : '展开' }}</span>
                              <span class="summary-chevron" :class="{ open: msg.reasoningExpanded }"><icon-chevron-right /></span>
                            </span>
                          </summary>
                          <div class="reasoning-content markdown-body" v-html="renderMarkdown(msg.content)"></div>
                        </details>
                      </div>
                      <div v-else class="chat-bubble markdown-body" v-if="msg.content" v-html="renderMarkdown(msg.content)"></div>
                    </div>
                  </div>
                </div>
              </div>
              <div class="chat-input-area">
                <a-textarea
                  v-model="chatInput"
                  class="chat-input"
                  placeholder="针对视频内容提问..."
                  :auto-size="{ minRows: 1, maxRows: 4 }"
                  @keydown.enter.exact.prevent="handleChatSend"
                />
                <a-button type="primary" :loading="chatLoading" @click="handleChatSend">发送</a-button>
              </div>
            </div>
          </a-tab-pane>

          <!-- Tab 5: Keyframes -->
          <a-tab-pane key="keyframes" title="关键帧索引">
            <div class="keyframes-tab-content">
              <div v-if="analysisData && analysisData.segments" class="segments-list">
                <div 
                  v-for="(seg, idx) in analysisData.segments" 
                  :key="idx" 
                  class="segment-item"
                  @click="jumpToTime(seg.timestamp)"
                >
                  <div class="segment-thumb">
                    <img v-if="seg.image_url" :src="seg.image_url" :alt="seg.title" />
                    <div class="segment-time-badge">{{ formatTime(seg.timestamp) }}</div>
                  </div>
                  <div class="segment-info">
                    <div class="segment-title">{{ seg.title }}</div>
                    <div class="segment-meta">{{ seg.points ? seg.points[0] : '' }}</div>
                  </div>
                </div>
              </div>
              <div v-else class="empty-state">
                <icon-list :style="{ fontSize: '48px', color: 'var(--text-muted)' }" />
                <p>暂无关键帧数据</p>
              </div>
            </div>
          </a-tab-pane>
        </a-tabs>
      </div>
    </div>

    <a-modal v-model:visible="coursewareOcrModalVisible" title="课件 OCR 结果" :footer="false" width="960px" draggable>
      <div v-if="coursewareOcrResults.length" class="courseware-ocr-results">
        <div v-for="(res, idx) in coursewareOcrResults" :key="idx" class="courseware-ocr-item">
          <div class="courseware-ocr-item-header">
            <span class="ocr-time">{{ formatTime(res.timestamp) }}</span>
            <span class="ocr-name">{{ res.name }}</span>
          </div>
          <div class="courseware-ocr-text markdown-body" v-html="renderMarkdownPreview(res.text)"></div>
        </div>
      </div>
      <div v-else class="empty-state">
        <p>暂无识别结果</p>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useConfigStore } from '../stores/config'
import { Message } from '@arco-design/web-vue'
import { marked } from 'marked'
import { processStreamedOutput, flushStreamBuffer } from '../utils/processStreamedOutput'
import ChipLoader from '../components/ChipLoader.vue'
import MindMap from '../components/MindMap.vue'
import UVCheckbox from '../components/UVCheckbox.vue'
import AudioParticleVisualizer from '../components/AudioParticleVisualizer.vue'
import { 
  List as IconList,
  Copy as IconCopy,
  Download as IconDownload,
  File as IconFile,
  Plus as IconPlus,
  Play as IconPlay,
  Pause as IconPause,
  RefreshCw as IconRefreshCw,
  Share as IconShareInternal,
  Bot as IconRobot,
  ChevronRight as IconChevronRight,
  Link as IconLink,
  Upload as IconUpload,
  ArrowLeft as IconArrowLeft,
  Workflow as IconWorkflow,
  BookOpen as IconBookOpen,
  FileText as IconFileText,
  Trash2 as IconTrash
} from 'lucide-vue-next'

const router = useRouter()
const route = useRoute()
const configStore = useConfigStore()
const backendBaseUrl = computed(() => (configStore.backend_base_url || '').replace(/\/+$/, ''))
const backendWsBaseUrl = computed(() => {
  const base = backendBaseUrl.value
  if (base.startsWith('https://')) return base.replace(/^https:/, 'wss:')
  if (base.startsWith('http://')) return base.replace(/^http:/, 'ws:')
  return base
})

// State
const videoRef = ref(null)
const loading = ref(false)
const progressPercent = ref(0)
const progressMsg = ref('')
const report = ref('')
const analysisData = ref(null)
const videoUrl = ref('')
const videoPath = ref('')
const videoMd5 = ref('')
const videoFile = ref(null)
const mediaType = ref('video')
const videoUrlInput = ref('')
const importingVideo = ref(false)
const activeRightTab = ref('transcript')
const transcriptData = ref([])
const translatedTranscriptData = ref([])
const bilingualEnabled = ref(false)
const translating = ref(false)
const currentTime = ref(0)
const audioDuration = ref(0)
const audioPlaying = ref(false)
const audioSeeking = ref(false)
const audioSeekValue = ref(0)
const audioVizRef = ref(null)
const chatMessages = ref([])
const chatInput = ref('')
const chatLoading = ref(false)
const chatListRef = ref(null)
const mindmapData = ref(null)
const mindmapLoading = ref(false)
const notesData = ref('')
const notesLoading = ref(false)
const coursewareData = ref([])
const coursewareLoading = ref(false)
const selectedCoursewareKeys = ref(new Set())
const coursewareOcrLoading = ref(false)
const coursewareOcrModalVisible = ref(false)
const coursewareOcrResults = ref([])
const localVideoInputRef = ref(null)
const videoDragActive = ref(false)

const getCoursewareKey = (item, idx) => `${idx}|${item?.timestamp ?? ''}|${item?.url ?? ''}`

const isCoursewareSelected = (key) => selectedCoursewareKeys.value.has(key)

const setCoursewareSelected = (key, checked) => {
  const next = new Set(selectedCoursewareKeys.value)
  if (checked) {
    next.add(key)
  } else {
    next.delete(key)
  }
  selectedCoursewareKeys.value = next
}

const handleDeleteCourseware = (idx) => {
  if (coursewareData.value) {
    coursewareData.value.splice(idx, 1);
  }
}

const handleCoursewareOcr = async () => {
  if (!coursewareData.value || !coursewareData.value.length) {
    Message.warning('暂无课件图片')
    return
  }

  const selectedItems = coursewareData.value
    .map((item, idx) => ({
      key: getCoursewareKey(item, idx),
      url: item.url,
      timestamp: item.timestamp,
      name: `Page ${idx + 1}`,
    }))
    .filter(item => isCoursewareSelected(item.key))
    .map(({ key, ...rest }) => rest)

  if (!selectedItems.length) {
    Message.warning('请先勾选要识别的图片')
    return
  }

  coursewareOcrLoading.value = true
  try {
    const config = buildConfig()
    const response = await fetch(`${backendBaseUrl.value}/ocr_courseware`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: selectedItems, config: config, video_md5: videoMd5.value || '' }),
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(errorText || 'OCR failed')
    }

    const data = await response.json()
    const results = Array.isArray(data.results) ? data.results : []
    results.sort((a, b) => (a.timestamp ?? 0) - (b.timestamp ?? 0))
    coursewareOcrResults.value = results
    coursewareOcrModalVisible.value = true
  } catch (e) {
    Message.error(e.message || '识别失败')
  } finally {
    coursewareOcrLoading.value = false
  }
}

const handleGenerateNotes = async () => {
  if (!transcriptData.value || !transcriptData.value.length) {
    Message.warning('请先完成视频分析生成字幕')
    return
  }
  
  notesLoading.value = true
  activeRightTab.value = 'notes'
  notesData.value = ''

  try {
      const fullTranscript = transcriptData.value.map(t => t.text).join('\n');
      const config = buildConfig();

      const response = await fetch(`${backendBaseUrl.value}/generate_notes`, {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json'
          },
          body: JSON.stringify({
              transcript: fullTranscript,
              config: config,
              video_md5: videoMd5.value || ''
          })
      });

      if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          const errorMessage = errorData.detail || response.statusText;
          throw new Error(`API Error: ${errorMessage}`);
      }

      const data = await response.json();
      notesData.value = data.notes;
      Message.success('文稿笔记生成成功');

  } catch (e) {
      console.error(e);
      Message.error('文稿笔记生成失败: ' + e.message);
  } finally {
      notesLoading.value = false;
  }
}

const handleGenerateCourseware = async () => {
    if (!videoPath.value) {
        Message.warning('请先完成视频分析')
        return
    }
    
    coursewareLoading.value = true
    activeRightTab.value = 'courseware'
    coursewareData.value = []
    
    try {
        const config = buildConfig()
        const response = await fetch('http://localhost:8999/generate_courseware', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                video_filename: videoPath.value,
                config: config
            })
        })
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}))
            throw new Error(errorData.detail || response.statusText)
        }
        
        const data = await response.json()
        coursewareData.value = data.images
        Message.success('课件提取成功')
    } catch (e) {
        Message.error(e.message || '课件提取失败')
    } finally {
        coursewareLoading.value = false
    }
}

const handleGenerateMindmap = async () => {
  if (!transcriptData.value || !transcriptData.value.length) {
    Message.warning('请先完成视频分析生成字幕')
    return
  }
  
  mindmapLoading.value = true
  activeRightTab.value = 'mindmap'
  mindmapData.value = null

  try {
      const fullTranscript = transcriptData.value.map(t => t.text).join('\n');
      const config = buildConfig();

      const response = await fetch(`${backendBaseUrl.value}/generate_mindmap`, {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json'
          },
          body: JSON.stringify({
              transcript: fullTranscript,
              config: config,
              video_md5: videoMd5.value || ''
          })
      });

      if (!response.ok) {
          throw new Error(`API Error: ${response.statusText}`);
      }

      const data = await response.json();
      mindmapData.value = data;
      Message.success('思维导图生成成功');

  } catch (e) {
      console.error(e);
      Message.error('思维导图生成失败: ' + e.message);
  } finally {
      mindmapLoading.value = false;
  }
}

// Computed
const renderedReport = computed(() => {
  if (!report.value) return ''
  const linkedReport = report.value.replace(/(\d{2}:\d{2}:\d{2})/g, '[$1](timestamp:$1)')
  return marked(linkedReport)
})



const renderChatMarkdown = (content) => {
  if (!content) return ''
  return marked(content)
}

const activeSegment = computed(() => {
  if (!analysisData.value || !analysisData.value.segments || !analysisData.value.segments.length) return null
  
  const segments = analysisData.value.segments
  let current = null
  
  for (let i = 0; i < segments.length; i++) {
    if (currentTime.value >= segments[i].timestamp) {
      current = segments[i]
    } else {
      break
    }
  }
  return current
})

const currentContentTitle = computed(() => {
  const analysisTitle = String(analysisData.value?.title || '').trim()
  const segTitle = String(activeSegment.value?.title || '').trim()
  if (analysisTitle && segTitle && segTitle !== analysisTitle) return `${analysisTitle} · ${segTitle}`
  if (analysisTitle) return analysisTitle
  const localName = String(videoFile.value?.name || '').trim()
  if (localName) return localName
  const path = String(videoPath.value || '').trim()
  if (path) return path
  const url = String(videoUrlInput.value || videoUrl.value || '').trim()
  if (url) return url
  return '未加载内容'
})

const formattedTranscriptParagraphs = computed(() => {
  if (!transcriptData.value.length) return []
  
  const paragraphs = []
  let currentPara = ''
  
  transcriptData.value.forEach(item => {
    const text = item.text.trim()
    if (!text) return
    
    // Add comma if no punctuation at end (simple heuristic)
    const hasPunctuation = /[\.\!\?。！？]$/.test(text)
    currentPara += text + (hasPunctuation ? ' ' : '，')
    
    if (currentPara.length > 500) {
      // Replace trailing comma with period for paragraph end
      paragraphs.push(currentPara.replace(/[，]\s*$/, '。').trim())
      currentPara = ''
    }
  })
  
  if (currentPara) {
    paragraphs.push(currentPara.replace(/[，]\s*$/, '。').trim())
  }
  
  return paragraphs
})

const currentSubtitle = computed(() => {
  if (!transcriptData.value.length) return ''
  let current = ''
  for (let i = 0; i < transcriptData.value.length; i++) {
    if (currentTime.value >= transcriptData.value[i].timestamp) {
      current = transcriptData.value[i].text
    } else {
      break
    }
  }
  return current
})


const renderMarkdown = (text) => {
    try {
      return marked.parse(text || '', { 
        gfm: true,
        breaks: true 
      })
    } catch (e) {
      console.error('Markdown rendering failed:', e)
      return text
    }
  }

const normalizeMarkdownPreview = (text) => {
  const raw = String(text ?? '')
  const fenced = raw.match(/^\s*```(?:markdown|md)?\s*\r?\n([\s\S]*?)\r?\n```\s*$/i)
  return fenced ? fenced[1] : raw
}

const renderMarkdownPreview = (text) => renderMarkdown(normalizeMarkdownPreview(text))

const currentSubtitleEn = computed(() => {
  if (!translatedTranscriptData.value.length) return ''
  let current = ''
  for (let i = 0; i < translatedTranscriptData.value.length; i++) {
    if (currentTime.value >= translatedTranscriptData.value[i].timestamp) {
      current = translatedTranscriptData.value[i].text
    } else {
      break
    }
  }
  return current
})


const subtitleLines = computed(() => {
  const cn = String(currentSubtitle.value || '').trim()
  const en = String(currentSubtitleEn.value || '').trim()
  if (!bilingualEnabled.value) return [cn || '暂无字幕']
  if (!cn && !en) return ['暂无字幕']
  if (cn && en) return [cn, en]
  return [cn || en]
})

// Methods
const goHome = () => {
  router.push({ name: 'Dashboard' })
}

const handleLocalVideoUpload = (_, fileItem) => {
  const file = fileItem.file
  if (!file) return
  setLocalVideoFile(file)
}

const openLocalVideoPicker = () => {
  const el = localVideoInputRef.value
  if (!el) return
  el.value = ''
  el.click()
}

const handleVideoDragEnter = () => {
  if (loading.value) return
  videoDragActive.value = true
}

const handleVideoDragOver = () => {
  if (loading.value) return
  videoDragActive.value = true
}

const handleVideoDragLeave = (e) => {
  const next = e?.relatedTarget
  if (next && e?.currentTarget && e.currentTarget.contains(next)) return
  videoDragActive.value = false
}

const handleVideoDrop = (e) => {
  videoDragActive.value = false
  if (loading.value) {
    Message.warning('分析中，稍后再试')
    return
  }
  const file = e?.dataTransfer?.files?.[0] || null
  if (!file) return
  const type = String(file.type || '').toLowerCase()
  const name = String(file.name || '').toLowerCase()
  const looksVideo = type.startsWith('video/') || /\.(mp4|mov|mkv|webm|avi|flv|m4v)$/.test(name)
  const looksAudio = type.startsWith('audio/') || /\.(mp3|m4a|wav|flac|aac|ogg|opus)$/.test(name)
  if (!looksVideo && !looksAudio) {
    Message.warning('请拖拽视频或音频文件')
    return
  }
  setLocalVideoFile(file)
}

const handleLocalVideoInputChange = (e) => {
  const file = e?.target?.files?.[0] || null
  if (!file) return
  setLocalVideoFile(file)
}

const setLocalVideoFile = (file) => {
  const prev = videoUrl.value
  if (prev && typeof prev === 'string' && prev.startsWith('blob:')) {
    try {
      URL.revokeObjectURL(prev)
    } catch (e) {}
  }

  const type = String(file?.type || '').toLowerCase()
  const name = String(file?.name || '').toLowerCase()
  const looksAudio = type.startsWith('audio/') || /\.(mp3|m4a|wav|flac|aac|ogg|opus)$/.test(name)
  mediaType.value = looksAudio ? 'audio' : 'video'
  if (mediaType.value === 'audio' && activeRightTab.value === 'courseware') {
    activeRightTab.value = 'transcript'
  }

  videoFile.value = file
  videoPath.value = ''
  videoUrl.value = URL.createObjectURL(file)

  report.value = ''
  analysisData.value = null
  transcriptData.value = []
  translatedTranscriptData.value = []
  mindmapData.value = null
  notesData.value = ''
  coursewareData.value = []
  selectedCoursewareKeys.value = new Set()

  Message.success(mediaType.value === 'audio' ? '本地音频已加载' : '本地视频已加载')
}

const handleUrlSubmit = () => {
  if (!videoUrlInput.value) return

  importingVideo.value = true
  fetch(`${backendBaseUrl.value}/import_video_url`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url: videoUrlInput.value }),
  })
    .then(async (res) => {
      if (!res.ok) {
        const err = await res.json().catch(() => null)
        const msg = err?.detail || (await res.text().catch(() => '')) || '解析失败'
        throw new Error(msg)
      }
      return res.json()
    })
    .then((data) => {
      const prev = videoUrl.value
      if (prev && typeof prev === 'string' && prev.startsWith('blob:')) {
        try {
          URL.revokeObjectURL(prev)
        } catch (e) {}
      }

      videoUrl.value = data.video_url
      videoPath.value = data.object_key || data.video_path || ''
      videoFile.value = null
      mediaType.value = data.media_type === 'audio' ? 'audio' : 'video'
      if (mediaType.value === 'audio' && activeRightTab.value === 'courseware') {
        activeRightTab.value = 'transcript'
      }
      report.value = ''
      analysisData.value = null
      transcriptData.value = []
      translatedTranscriptData.value = []
      Message.success(mediaType.value === 'audio' ? '音频解析成功' : '视频解析成功')
    })
    .catch((e) => {
      Message.error(e?.message || '解析失败')
    })
    .finally(() => {
      importingVideo.value = false
    })
}

const formatTime = (seconds) => {
  if (!seconds && seconds !== 0) return '00:00:00'
  return new Date(seconds * 1000).toISOString().substr(11, 8)
}

const formatClock = (seconds) => {
  const s = Number(seconds || 0)
  if (!Number.isFinite(s) || s <= 0) return '00:00'
  const hh = Math.floor(s / 3600)
  const mm = Math.floor((s % 3600) / 60)
  const ss = Math.floor(s % 60)
  const pad2 = (n) => String(n).padStart(2, '0')
  if (hh > 0) return `${pad2(hh)}:${pad2(mm)}:${pad2(ss)}`
  return `${pad2(mm)}:${pad2(ss)}`
}

const handleTimeUpdate = (e) => {
  currentTime.value = e.target.currentTime
}

const audioCanPlay = computed(() => !!videoUrl.value)
const audioSeekable = computed(() => Number.isFinite(audioDuration.value) && audioDuration.value > 0)

const audioSeekPercent = computed(() => (audioSeekValue.value / 1000) * 100)

const syncAudioSeekValue = () => {
  if (!audioSeekable.value) {
    audioSeekValue.value = 0
    return
  }
  const ratio = audioDuration.value ? currentTime.value / audioDuration.value : 0
  audioSeekValue.value = Math.round(Math.max(0, Math.min(1, ratio)) * 1000)
}

const handleAudioLoadedMetadata = (e) => {
  const d = Number(e?.target?.duration)
  audioDuration.value = Number.isFinite(d) && d > 0 ? d : 0
  syncAudioSeekValue()
}

const handleAudioTimeUpdate = (e) => {
  handleTimeUpdate(e)
  if (!audioSeeking.value) syncAudioSeekValue()
}

const handleAudioPlay = () => {
  audioPlaying.value = true
  ensureTranslationOnPlay()
}

const handleAudioPause = () => {
  audioPlaying.value = false
}

const handleAudioEnded = () => {
  audioPlaying.value = false
}

const handleVideoPlay = () => {
  ensureTranslationOnPlay()
}

let lastTranslateAttemptAt = 0

const ensureTranslationOnPlay = async () => {
  if (!bilingualEnabled.value) return
  if (!transcriptData.value.length) return
  if (translatedTranscriptData.value.length) return
  if (translating.value) return

  const now = Date.now()
  if (now - lastTranslateAttemptAt < 8000) return
  lastTranslateAttemptAt = now
  await translateTranscripts()
}

const toggleAudioPlayback = async () => {
  try {
    await audioVizRef.value?.unlock?.()
  } catch (e) {}
  const el =
    videoRef.value ||
    document.querySelector(mediaType.value === 'audio' ? '.summary-audio-player' : '.summary-video-player')
  if (!el) return
  if (el.paused) {
    try {
      if (el.readyState === 0) el.load()
    } catch (e) {}
    try {
      const p = el.play()
      if (p && typeof p.then === 'function') await p
    } catch (err) {
      const msg = String(err?.message || err || '').trim()
      Message.error(msg ? `播放失败：${msg}` : '播放失败')
    }
  } else {
    el.pause()
  }
}

const handleSeekPointerDown = () => {
  audioSeeking.value = true
}

const handleSeekInput = (e) => {
  const v = Number(e?.target?.value || 0) || 0
  audioSeekValue.value = Math.max(0, Math.min(1000, v))
  if (!audioSeekable.value) return
  currentTime.value = (audioSeekValue.value / 1000) * audioDuration.value
}

const handleSeekChange = () => {
  const el = videoRef.value
  audioSeeking.value = false
  if (!el || !audioSeekable.value) return
  el.currentTime = (audioSeekValue.value / 1000) * audioDuration.value
}

watch([videoUrl, mediaType], () => {
  audioDuration.value = 0
  audioPlaying.value = false
  audioSeeking.value = false
  audioSeekValue.value = 0
})

const handleAudioError = (e) => {
  audioPlaying.value = false
  const mediaError = e?.target?.error
  const code = mediaError?.code
  const msg = code ? `音频加载失败（code ${code}）` : '音频加载失败'
  Message.error(msg)
}

const jumpToTime = (seconds) => {
  let videoEl = videoRef.value
  if (!videoEl) {
    videoEl = document.querySelector('.summary-video-player')
    if (!videoEl) videoEl = document.querySelector('.summary-audio-player')
  }

  if (videoEl) {
    videoEl.currentTime = seconds
    videoEl.play().catch(e => console.log('Auto-play prevented:', e))
  } else {
    Message.warning('Video player not ready')
  }
}

const handleMarkdownClick = (event) => {
  const link = event.target.closest('a')
  if (link) {
    const href = link.getAttribute('href')
    if (href && href.startsWith('timestamp:')) {
      event.preventDefault()
      const timeStr = href.substring(10)
      const parts = timeStr.split(':').map(Number)
      if (parts.length === 3) {
        const seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
        jumpToTime(seconds)
      }
    }
  }
}

const handleCopyTranscript = async () => {
  if (!transcriptData.value.length) return
  
  const text = transcriptData.value
    .map(item => `[${formatTime(item.timestamp)}] ${item.text}`)
    .join('\n')
    
  try {
    await navigator.clipboard.writeText(text)
    Message.success('Transcript copied to clipboard')
  } catch (err) {
    try {
      const textArea = document.createElement("textarea")
      textArea.value = text
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)
      Message.success('Transcript copied to clipboard (fallback)')
    } catch (fallbackErr) {
      console.error('Copy failed:', err, fallbackErr)
      Message.error('Failed to copy text')
    }
  }
}

const buildConfig = () => ({
  openai_api_key: configStore.openai_api_key,
  openai_base_url: configStore.openai_base_url,
  llm_model: configStore.llm_model,
  ocr_engine: configStore.ocr_engine,
  vl_model: configStore.vl_model,
  vl_base_url: configStore.vl_base_url,
  vl_api_key: configStore.vl_api_key,
  model_size: configStore.model_size,
  device: configStore.device,
  compute_type: configStore.compute_type,
  capture_offset: configStore.capture_offset,
})

const loadFromMd5 = async (md5) => {
  const v = String(md5 || '').trim().toLowerCase()
  if (!v) return
  try {
    const res = await fetch(`${backendBaseUrl.value}/analysis/by_md5/${encodeURIComponent(v)}`)
    if (!res.ok) {
      const txt = await res.text()
      throw new Error(txt || 'Load failed')
    }
    const payload = await res.json()
    console.log('Loaded artifacts payload:', payload)
    const artifacts = payload.artifacts || {}
    const pick = (type) => (Array.isArray(artifacts[type]) && artifacts[type].length ? artifacts[type][0] : null)

    videoMd5.value = payload?.asset?.md5 || v
    videoUrl.value = payload?.access?.primary_url || ''
    videoPath.value = payload?.asset?.source_ref || ''

    const analysis = pick('ai_analysis')?.json || null
    const reportText = pick('report_markdown')?.text || ''
    analysisData.value = analysis
    report.value = reportText

    const mt = String(payload?.asset?.media_type || analysis?.media_type || '').trim()
    if (mt === 'audio') {
      mediaType.value = 'audio'
      if (activeRightTab.value === 'courseware') activeRightTab.value = 'transcript'
    } else if (mt === 'video') {
      mediaType.value = 'video'
    }

    const subtitleLines = pick('subtitle_lines')?.json?.lines
    if (Array.isArray(subtitleLines) && subtitleLines.length) {
      transcriptData.value = subtitleLines.map((x) => ({ timestamp: x.timestamp, text: x.text }))
    } else if (analysis?.raw_transcript) {
      const lines = String(analysis.raw_transcript || '').split('\n')
      transcriptData.value = lines
        .map(line => {
          const match = line.match(/^\[(\d+(?:\.\d+)?)s\]\s*(.*)$/)
          if (match) {
            return { timestamp: parseFloat(match[1]), text: match[2] }
          }
          return null
        })
        .filter(Boolean)
    } else {
      transcriptData.value = []
    }

    const transEn = pick('subtitle_translation_en')?.json?.lines
    if (Array.isArray(transEn) && transEn.length) {
      translatedTranscriptData.value = transEn.map((x) => ({ timestamp: x.timestamp, text: x.text }))
    } else {
      translatedTranscriptData.value = []
    }

    const mm = pick('mindmap_g6')?.json
    mindmapData.value = mm || null

    const notes = pick('notes_markdown')?.text
    notesData.value = notes || ''

    // 尝试加载 captured_frames (新逻辑: 列表存在单个 artifact 中) 或 captured_frame (旧逻辑: 多个 artifacts)
    let framesData = []
    const framesArtifact = pick('captured_frames')
    if (framesArtifact && Array.isArray(framesArtifact.json)) {
      framesData = framesArtifact.json
    } else if (Array.isArray(artifacts.captured_frame)) {
      framesData = artifacts.captured_frame.map(x => x?.json)
    }

    if (framesData.length) {
      coursewareData.value = framesData
        .filter(Boolean)
        .map((x) => ({ url: x.url, timestamp: x.timestamp, object_key: x.object_key }))
    }

    const lastChat = pick('chat_session')?.json
    if (lastChat && Array.isArray(lastChat.messages) && lastChat.messages.length) {
      chatMessages.value = lastChat.messages
    }

    Message.success('已从 md5 加载')
  } catch (e) {
    Message.error(e.message || 'Load failed')
  }
}

watch(
  () => route.query.md5,
  (md5) => {
    if (md5) loadFromMd5(md5)
  },
  { immediate: true }
)

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
          if (data.message.includes('视频上传成功') || data.message.includes('视频加载成功')) progressPercent.value = 5
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
          if (analysisData.value?.media_type === 'audio') {
            mediaType.value = 'audio'
            if (activeRightTab.value === 'courseware') activeRightTab.value = 'transcript'
          } else if (analysisData.value?.media_type === 'video') {
            mediaType.value = 'video'
          }
          if (analysisData.value.segments && Array.isArray(analysisData.value.segments)) {
            analysisData.value.segments.sort((a, b) => a.timestamp - b.timestamp)
          }
          if (!videoFile.value && data.video_url) {
            videoUrl.value = data.video_url
          }
          videoPath.value = data.object_key || data.video_path || ''
          if (data.video_md5) videoMd5.value = String(data.video_md5 || '').trim().toLowerCase()

          if (data.data.raw_transcript) {
            const lines = data.data.raw_transcript.split('\n')
            transcriptData.value = lines
              .map(line => {
                const match = line.match(/^\[(\d+(?:\.\d+)?)s\] (.*)$/)
                if (match) {
                  return {
                    timestamp: parseFloat(match[1]),
                    text: match[2]
                  }
                }
                return null
              })
              .filter(item => item !== null)
          }

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

const analyzeByObjectKey = async (objectKey, config) => {
  const response = await fetch(`${backendBaseUrl.value}/analyze_path`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ video_path: objectKey, config }),
  })
  await readSseResponse(response)
}

const directUploadToMinioAndAnalyze = async (file, config) => {
  progressPercent.value = 0
  progressMsg.value = '请求上传地址...'

  const presignRes = await fetch(`${backendBaseUrl.value}/minio/presign_upload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename: file.name, content_type: file.type || 'application/octet-stream' }),
  })
  if (!presignRes.ok) {
    const err = await presignRes.json().catch(() => null)
    throw new Error(err?.detail || '获取 MinIO 上传地址失败')
  }
  const presign = await presignRes.json()

  const objectKey = presign.object_key
  const uploadUrl = presign.upload_url
  const previewUrl = presign.video_url

  if (objectKey) videoPath.value = objectKey

  await new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('PUT', uploadUrl, true)
    try {
      xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream')
    } catch (e) {}

    xhr.upload.onprogress = (evt) => {
      if (!evt.lengthComputable) {
        progressMsg.value = '上传中...'
        return
      }
      const pct = Math.max(0, Math.min(99, Math.round((evt.loaded / evt.total) * 100)))
      progressPercent.value = pct
      progressMsg.value = `上传中... ${pct}%`
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve()
      else reject(new Error(`上传失败: ${xhr.status}`))
    }
    xhr.onerror = () => reject(new Error('上传失败: 网络错误'))
    xhr.send(file)
  })

  progressMsg.value = '上传完成，开始分析...'
  progressPercent.value = 5
  await analyzeByObjectKey(objectKey, config)
}

const getTranscriptContext = () => {
  if (!transcriptData.value.length) return ''
  const text = transcriptData.value
    .map(item => `[${formatTime(item.timestamp)}] ${item.text}`)
    .join('\n')
  const limit = 12000
  return text.length > limit ? text.slice(0, limit) : text
}

const getSummaryContext = () => {
  if (analysisData.value && analysisData.value.summary) return analysisData.value.summary
  return ''
}

const scrollChatToBottom = () => {
  const el = chatListRef.value
  if (el) {
    el.scrollTop = el.scrollHeight
  }
}

const handleDeleteMessage = (index) => {
  chatMessages.value.splice(index, 1)
}

const handleChatSend = async () => {
  const content = chatInput.value.trim()
  if (!content) return
  if (!transcriptData.value.length && !analysisData.value) {
    Message.warning('请先完成视频分析生成字幕')
    return
  }

  const userMessage = { role: 'user', content }
  chatMessages.value.push(userMessage)
  chatInput.value = ''

  const assistantContentMessageRaw = { role: 'assistant', kind: 'content', content: '' }
  chatMessages.value.push(assistantContentMessageRaw)
  const assistantContentMessage = chatMessages.value[chatMessages.value.length - 1]
  let assistantReasoningMessage = null
   
   chatLoading.value = true
  await nextTick()
  scrollChatToBottom()

  let ws = null
  // 打字机队列
  const streamQueue = []
  let isTyping = false
  let typingLoopRunning = false
  let currentItem = null
  let currentIndex = 0

  const thinkState = { buffer: '', inThink: false }

  const startTypingLoop = () => {
    if (typingLoopRunning) return
    typingLoopRunning = true
    requestAnimationFrame(processQueue)
  }

  const processQueue = async () => {
    if (!currentItem && streamQueue.length > 0) {
      currentItem = streamQueue.shift()
      currentIndex = 0
    }

    if (!currentItem) {
      isTyping = false
      typingLoopRunning = false
      return
    }

    isTyping = true

    const text = currentItem.text || ''
    const remaining = text.length - currentIndex
    const charsPerFrame = streamQueue.length > 20 ? 12 : 6
    const take = Math.min(remaining, charsPerFrame)
    const slice = text.slice(currentIndex, currentIndex + take)
    currentIndex += take

    if (currentItem.type === 'reasoning') {
      if (!assistantReasoningMessage) {
        const reasoningMessageRaw = { role: 'assistant', kind: 'reasoning', content: '', reasoningExpanded: false }
        const contentIndex = chatMessages.value.indexOf(assistantContentMessage)
        const insertIndex = contentIndex >= 0 ? contentIndex : chatMessages.value.length
        chatMessages.value.splice(insertIndex, 0, reasoningMessageRaw)
        assistantReasoningMessage = chatMessages.value[insertIndex]
      }
      assistantReasoningMessage.content += slice
    } else {
      assistantContentMessage.content += slice
    }

    if (currentIndex >= text.length) {
      currentItem = null
      currentIndex = 0
    }

    await nextTick()
    scrollChatToBottom()
    requestAnimationFrame(processQueue)
  }

  try {
    ws = new WebSocket(`${backendWsBaseUrl.value}/ws/chat`)
    
    ws.onopen = () => {
      console.log('WS Connected')
      ws.send(JSON.stringify({
        messages: chatMessages.value
          .filter(item => item.role === 'user' || (item.role === 'assistant' && item.kind !== 'reasoning'))
          .filter(item => item !== assistantContentMessage),
        transcript: getTranscriptContext(),
        summary: getSummaryContext(),
        config: buildConfig(),
        video_md5: videoMd5.value || '',
      }))
    }

    ws.onmessage = async (event) => {
      const data = event.data
      let payloads = []

      // Attempt to parse one or more JSON objects
      try {
        const payload = JSON.parse(data)
        payloads.push(payload)
      } catch (e) {
        // Fallback for concatenated JSONs or non-JSON data
        // Try to split by {"type": pattern which is common in our backend
        const rawParts = data.split(/(?=\{"type":)/g).filter(p => p.trim())
        let parsedAny = false
        for (const part of rawParts) {
            try {
                payloads.push(JSON.parse(part))
                parsedAny = true
            } catch (err) {
                // Ignore individual parse errors
            }
        }
        
        // If we couldn't parse any JSON, treat as raw string
        if (!parsedAny) {
           if (data === '[DONE]') {
              flushStreamBuffer(thinkState).forEach(item => streamQueue.push(item))
              chatLoading.value = false
              ws.close()
              startTypingLoop()
              return
           }
           if (typeof data === 'string' && data.startsWith('Error:')) {
              Message.error(data)
              chatLoading.value = false
              ws.close()
              return
           }
           
           // Treat as raw content
           processStreamedOutput(String(data), thinkState).forEach(item => streamQueue.push(item))
           if (!isTyping) startTypingLoop()
           return
        }
      }

      // Process parsed payloads
      for (const payload of payloads) {
          if (payload.type === 'done') {
            flushStreamBuffer(thinkState).forEach(item => streamQueue.push(item))
            chatLoading.value = false
            ws.close()
            startTypingLoop()
            return
          }
          if (payload.type === 'error') {
            Message.error(payload.message || 'Chat failed')
            chatLoading.value = false
            ws.close()
            return
          }
          if (payload.type === 'reasoning' && payload.delta) {
            streamQueue.push({ type: 'reasoning', text: payload.delta })
            startTypingLoop()
            continue
          }
          if (payload.type === 'content' && payload.delta) {
            processStreamedOutput(payload.delta, thinkState).forEach(item => streamQueue.push(item))
            startTypingLoop()
            continue
          }
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      Message.error('Chat connection failed')
      chatLoading.value = false
    }

    ws.onclose = () => {
      chatLoading.value = false
      startTypingLoop()
    }

  } catch (error) {
    Message.error(error.message || 'Chat failed')
    chatLoading.value = false
  }
}

const translateTranscripts = async () => {
  if (!transcriptData.value.length) {
    Message.warning('暂无字幕可翻译')
    return
  }

  translating.value = true
  try {
    const response = await fetch(`${backendBaseUrl.value}/translate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        lines: transcriptData.value,
        config: buildConfig(),
        video_md5: videoMd5.value || '',
      }),
    })

    if (!response.ok) {
      const text = await response.text()
      throw new Error(text || 'Translate failed')
    }

    const data = await response.json()
    const translations = Array.isArray(data.translations) ? data.translations : []
    if (!translations.length) {
      Message.warning('翻译结果为空')
      return
    }

    const byIndex = new Map()
    translations.forEach((item, idx) => {
      if (item && typeof item.index === 'number') {
        byIndex.set(item.index, item.text || '')
      } else if (item && typeof item.text === 'string') {
        byIndex.set(idx, item.text)
      }
    })

    translatedTranscriptData.value = transcriptData.value.map((line, idx) => ({
      timestamp: line.timestamp,
      text: byIndex.get(idx) || '',
    }))
    Message.success('English subtitles ready')
  } catch (error) {
    Message.error(error.message || 'Translate failed')
  } finally {
    translating.value = false
  }
}

const toggleBilingual = async () => {
  bilingualEnabled.value = !bilingualEnabled.value
  if (bilingualEnabled.value && !translatedTranscriptData.value.length) {
    await translateTranscripts()
  }
}

watch(transcriptData, () => {
  translatedTranscriptData.value = []
  lastTranslateAttemptAt = 0
  if (bilingualEnabled.value) {
    translateTranscripts()
  }
})

const handleCaptureFrame = async () => {
  if (mediaType.value === 'audio') {
    Message.warning('音频不支持截取当前帧')
    return
  }
  if (!videoPath.value) {
    Message.warning('请先上传并分析视频')
    return
  }
  
  if (!videoRef.value) {
    Message.warning('播放器未就绪')
    return
  }
  
  const currentTime = videoRef.value.currentTime
  coursewareLoading.value = true
  
  try {
    const response = await fetch(`${backendBaseUrl.value}/capture_frame`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        video_filename: videoPath.value,
        timestamp: currentTime,
        video_md5: videoMd5.value || '',
      }),
    })
    
    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(errorText || 'Capture failed')
    }
    
    const data = await response.json()
    if (data.video_md5 && !videoMd5.value) videoMd5.value = String(data.video_md5 || '').trim().toLowerCase()
    // Add to existing list instead of replacing
    if (!coursewareData.value) coursewareData.value = []
    coursewareData.value.push({
      url: data.url,
      timestamp: data.timestamp,
      object_key: data.object_key
    })
    
    // Switch to courseware tab to show result
    activeRightTab.value = 'courseware'
    Message.success('截图成功')
    
  } catch (error) {
    console.error(error)
    Message.error('截图失败: ' + error.message)
  } finally {
    coursewareLoading.value = false
  }
}

const handleSubmit = async () => {
  const hasUploadFile = !!videoFile.value
  const hasImportedPath = !!videoPath.value
  if (!hasUploadFile && !hasImportedPath) {
    Message.warning('请先选择视频/音频或输入链接解析')
    return
  }
  
  if (!configStore.openai_api_key) {
    Message.warning('Please set API Key in Settings first')
    return
  }

  loading.value = true
  progressPercent.value = 0
  progressMsg.value = hasUploadFile ? 'Preparing upload...' : 'Preparing analysis...'
  report.value = ''
  analysisData.value = null
  
  const config = buildConfig()

  try {
    if (hasUploadFile) {
      const file = videoFile.value
      await directUploadToMinioAndAnalyze(file, config)
    } else {
      const response = await fetch(`${backendBaseUrl.value}/analyze_path`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_path: videoPath.value, config }),
      })
      await readSseResponse(response)
    }
  } catch (error) {
    Message.error(error.message || 'Unknown error during analysis')
    progressMsg.value = 'Error: ' + (error.message || 'Unknown error')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.video-summary-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: var(--surface-1);
}

.summary-header {
  padding: 10px 20px;
  border-bottom: 1px solid var(--card-border);
  display: flex;
  align-items: center;
  background: var(--surface-0);
  flex-shrink: 0;
}

.back-btn {
  color: var(--text-sub);
}

.summary-header-title {
  margin-left: auto;
  max-width: 70%;
  min-width: 0;
  color: transparent;
  font-size: 14px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: right;
  letter-spacing: 0.2px;
  background: linear-gradient(
    90deg,
    rgba(255, 255, 255, 0.72) 0%,
    rgba(255, 255, 255, 0.90) 18%,
    rgba(130, 170, 255, 0.95) 36%,
    rgba(255, 170, 210, 0.92) 52%,
    rgba(255, 224, 160, 0.92) 68%,
    rgba(255, 255, 255, 0.82) 100%
  );
  background-size: 220% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  filter: drop-shadow(0 0 10px rgba(130, 170, 255, 0.10));
  animation: headerTitleShimmer 6s ease-in-out infinite;
}

@keyframes headerTitleShimmer {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}

@media (prefers-reduced-motion: reduce) {
  .summary-header-title {
    animation: none;
  }
}

.summary-content {
  display: flex;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.left-panel {
  width: 50%;
  padding: 24px 24px 80px 24px;
  border-right: 1px solid var(--card-border);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  background-color: var(--surface-1);
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.left-panel::-webkit-scrollbar {
  display: none;
}

.right-panel {
  width: 50%;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  min-height: 0;
  background-color: var(--surface-0);
}

.video-topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.video-topbar-input {
  flex: 1;
  min-width: 0;
}

.video-wrapper {
  background-color: var(--media-bg);
  border-radius: 5px;
  aspect-ratio: 16/9;
  overflow: hidden;
  position: relative;
  flex-shrink: 0;
  margin-bottom: 16px;
  border: 3px solid #323232;
  box-shadow: 5px 5px #323232;
}

.video-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: var(--overlay-bg);
  backdrop-filter: blur(2px);
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
}

.summary-video-player {
  width: 100%;
  height: 100%;
}

.audio-stage {
  position: relative;
  width: 100%;
  height: 100%;
  background-image: url('../assert/bg2.png');
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
}

.audio-center-wave {
  position: absolute;
  left: 50%;
  top: 48%;
  transform: translate(-50%, -50%);
  width: min(520px, 70%);
  aspect-ratio: 1 / 1;
  border-radius: var(--border-radius-circle);
  overflow: hidden;
  z-index: 2;
  background: radial-gradient(circle at 50% 50%, color-mix(in srgb, var(--color-fill-2) 55%, transparent) 0%, transparent 70%);
  border: 1px solid var(--color-border-2);
  box-shadow: 0 18px 36px rgba(0, 0, 0, 0.34);
}

.summary-audio-player {
  position: absolute;
  left: 0;
  bottom: 0;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.summary-audio-controls {
  position: absolute;
  left: 14px;
  right: 14px;
  bottom: 14px;
  z-index: 3;
  height: 20px;
  padding: 10px 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  border-radius: var(--border-radius-large);
  border: 0;
  background: var(--color-bg-5);
  background: color-mix(in srgb, var(--color-bg-5) 62%, transparent);
  backdrop-filter: blur(0px);
  box-shadow: 0 14px 26px rgba(0, 0, 0, 0.38);
}

.audio-ctrl-btn {
  width: 34px;
  height: 34px;
  border-radius: var(--border-radius-circle);
  border: 1px solid var(--color-border-2);
  background: var(--color-fill-2);
  background: color-mix(in srgb, var(--color-fill-2) 72%, transparent);
  color: var(--color-text-1);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: transform 0.15s ease, background 0.15s ease, border-color 0.15s ease;
}

.audio-ctrl-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.audio-ctrl-btn:not(:disabled):hover {
  transform: translateY(-1px);
  background: var(--color-fill-3);
  background: color-mix(in srgb, var(--color-fill-3) 78%, transparent);
  border-color: var(--primary-6);
}

.audio-time {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 12px;
  color: var(--color-text-2);
  width: 52px;
  text-align: center;
  flex-shrink: 0;
}

.audio-progress-wrap {
  position: relative;
  flex: 1;
  height: 22px;
  display: flex;
  align-items: center;
}

.audio-progress {
  width: 100%;
  height: 10px;
  border-radius: var(--border-radius-circle);
  background: linear-gradient(
    90deg,
    color-mix(in srgb, var(--primary-6) 88%, transparent) 0%,
    color-mix(in srgb, var(--primary-6) 88%, transparent) var(--progress),
    var(--color-fill-3) var(--progress),
    var(--color-fill-3) 100%
  );
  outline: none;
  cursor: pointer;
  -webkit-appearance: none;
  appearance: none;
  border: 1px solid var(--color-border-2);
  box-shadow: inset 0 1px 0 rgba(0, 0, 0, 0.35);
  z-index: 1;
}

.audio-progress:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.audio-progress::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 14px;
  height: 14px;
  border-radius: var(--border-radius-circle);
  background: var(--primary-6);
  border: 2px solid var(--color-bg-white);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.45);
}

.audio-progress::-moz-range-thumb {
  width: 14px;
  height: 14px;
  border-radius: var(--border-radius-circle);
  background: var(--primary-6);
  border: 2px solid var(--color-bg-white);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.45);
}

.audio-progress::-moz-range-track {
  height: 10px;
  border-radius: 999px;
  background: transparent;
}

.video-drag-overlay {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px dashed rgba(255, 255, 255, 0.65);
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.45);
  pointer-events: none;
}

.video-drag-overlay-inner {
  text-align: center;
  color: rgba(255, 255, 255, 0.95);
}

.video-drag-title {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 6px;
}

.video-drag-sub {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);
}

.video-placeholder {
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  background-color: var(--surface-1);
  border: 2px dashed var(--text-strong);
  border-radius: 8px;
  transition: all 0.2s ease-in-out;
}

.video-placeholder:hover {
  border-color: var(--text-strong);
  background-color: var(--video-placeholder-hover-bg);
}

.subtitle-bar {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px 14px;
  margin-bottom: 16px;
  border-radius: 2px;
  background: rgba(0, 0, 0, 0.55);
  color: #ffffff;
}

.subtitle-lines {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.subtitle-text {
  width: 100%;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 14px;
  line-height: 1.4;
}

.subtitle-text-en {
  color: rgba(255, 255, 255, 0.85);
  font-size: 13px;
}

.placeholder-content {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: var(--text-sub);
}

.video-actions-bar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 24px;
}

.secondary-actions {
  display: flex;
  gap: 12px;
}

.secondary-actions .arco-btn {
  flex: 1;
}

.analysis-progress {
  background: var(--surface-0);
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

.summary-below-video {
  background: var(--surface-0);
  border-radius: 12px;
  padding: 24px;
  box-shadow: var(--shadow-2);
  flex: 1;
}

.summary-below-video h2 {
  font-size: 20px;
  margin-bottom: 16px;
  color: var(--card-text);
}

.summary-below-video p {
  color: var(--card-text-muted);
  line-height: 1.8;
  margin-bottom: 24px;
}

.highlights-list {
  list-style: none;
  padding: 0;
}

.highlights-list li {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
  color: var(--card-text);
  line-height: 1.5;
}

.highlights-list .bullet {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 6px;
  flex-shrink: 0;
}

.empty-state-below {
  padding: 40px;
  text-align: center;
  color: var(--text-sub);
  border: 2px dashed var(--card-border);
  border-radius: 12px;
}

/* Dynamic Segment Styles */
.dynamic-segment-content {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(5px); }
  to { opacity: 1; transform: translateY(0); }
}

.segment-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  border-bottom: 1px solid var(--card-border);
  padding-bottom: 12px;
}

.segment-time-badge {
  background: var(--hover-bg);
  color: var(--primary-color);
  padding: 4px 8px;
  border-radius: 4px;
  font-family: monospace;
  font-weight: 600;
  font-size: 14px;
}

.segment-title {
  margin: 0;
  font-size: 18px;
  color: var(--card-text);
}

.segment-points-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.segment-points-list li {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 12px;
  font-size: 15px;
  line-height: 1.6;
  color: var(--card-text-muted);
  background: var(--surface-1);
  padding: 10px 14px;
  border-radius: 8px;
  transition: background 0.2s;
}

.segment-points-list li:hover {
  background: var(--hover-bg);
  color: var(--card-text);
}

.point-bullet {
  color: var(--primary-color);
  font-weight: bold;
  font-size: 18px;
  line-height: 1;
  margin-top: 2px;
}

/* Tabs & Right Panel */
.summary-tabs {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

:deep(.arco-tabs-content) {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
  padding-top: 0;
  min-height: 0;
}

:deep(.arco-tabs-content-list) {
  flex: 1;
  min-height: 0;
  height: 100%;
}

:deep(.arco-tabs-pane) {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  height: 100%;
}

.transcript-tab-content {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.transcript-header {
  padding: 16px 20px;
  border-bottom: 1px solid var(--card-border);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.transcript-header h3 {
  margin: 0;
  font-size: 16px;
  color: var(--text-strong);
}

.transcript-list {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  padding-bottom: 40px;
}

.transcript-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  cursor: pointer;
  transition: background-color 0.2s;
  border-bottom: 1px solid var(--card-border);
}

.transcript-item:hover {
  background-color: var(--hover-bg);
}

.transcript-item .timestamp {
  font-family: monospace;
  color: var(--accent-1);
  font-weight: 600;
  font-size: 13px;
  flex-shrink: 0;
  width: 60px;
}

.transcript-texts {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.transcript-item .text {
  margin: 0;
  color: var(--text-main);
  font-size: 14px;
  line-height: 1.5;
}

.transcript-item .text-en {
  margin: 0;
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.5;
}

.empty-transcript {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
}

/* Detail Tab */
.detail-text-area {
  padding: 20px 20px 40px 20px;
  overflow-y: auto;
  height: 100%;
  min-height: 0;
}

/* Markdown Styles */
.markdown-body {
  color: var(--text-main);
  line-height: 1.6;
  font-size: 14px;
}

.markdown-body :deep(p) {
  margin-bottom: 12px;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  color: var(--text-strong);
  font-weight: 700;
  margin: 24px 0 12px;
  line-height: 1.4;
  border-bottom: none;
}

.markdown-body :deep(h1:first-child),
.markdown-body :deep(h2:first-child),
.markdown-body :deep(h3:first-child) {
  margin-top: 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 20px;
  margin: 12px 0;
}

.markdown-body :deep(li) {
  margin-bottom: 4px;
  list-style: inherit;
}

.markdown-body :deep(blockquote) {
  border-left: 4px solid var(--card-border-strong);
  padding-left: 12px;
  margin: 12px 0;
  color: var(--text-sub);
  font-style: italic;
  background: var(--surface-1);
  padding: 8px 12px;
  border-radius: 4px;
}

.markdown-body :deep(pre) {
  background: var(--surface-2);
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 12px 0;
  border: 1px solid var(--card-border);
}

.markdown-body :deep(code) {
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  background: rgba(150, 150, 150, 0.15);
  padding: 2px 5px;
  border-radius: 4px;
  color: var(--primary-color);
  font-size: 0.9em;
}

.markdown-body :deep(pre) :deep(code) {
  background: transparent;
  padding: 0;
  color: inherit;
  font-size: inherit;
}

.markdown-body :deep(strong) {
  font-weight: 700;
  color: var(--text-strong);
}

.markdown-body :deep(em) {
  font-style: italic;
}

.markdown-body :deep(a) {
  color: var(--primary-color);
  text-decoration: none;
  font-weight: 500;
}

.markdown-body :deep(a:hover) {
  text-decoration: underline;
}

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 20px 0;
  font-size: 14px;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: var(--shadow-2);
  display: block;
  overflow-x: auto;
}

.markdown-body :deep(th), 
.markdown-body :deep(td) {
  border: 1px solid var(--card-border);
  padding: 12px 16px;
  text-align: left;
}

.markdown-body :deep(th) {
  background-color: var(--surface-1);
  font-weight: 600;
  color: var(--text-sub);
  text-transform: uppercase;
  font-size: 12px;
  letter-spacing: 0.05em;
}

.markdown-body :deep(tr:hover) {
  background-color: var(--hover-bg);
}

.markdown-body :deep(img) {
  max-width: 100%;
  border-radius: 12px;
  margin: 16px 0;
  box-shadow: var(--shadow-2);
}

.empty-state {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  gap: 16px;
}

/* Keyframes Tab */
.keyframes-tab-content {
  height: 100%;
  overflow-y: auto;
  padding: 16px;
  background-color: var(--surface-1);
  min-height: 0;
}

.chat-message-list {
  padding-bottom: 40px;
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.segments-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 40px;
}

.detail-text-area .markdown-body {
  padding-bottom: 40px;
}

.courseware-grid::after {
  content: "";
  height: 40px;
  grid-column: 1 / -1;
}

.segment-item {
  display: flex;
  flex-direction: row;
  gap: 16px;
  padding: 12px;
  background: var(--surface-0);
  border: 1px solid var(--card-border);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  align-items: flex-start;
}

.segment-item:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-2);
  border-color: var(--primary-color);
}

.segment-thumb {
  width: 120px;
  height: 68px;
  border-radius: 6px;
  overflow: hidden;
  position: relative;
  flex-shrink: 0;
  background: var(--surface-1);
  border: 1px solid var(--card-border-strong);
}

.segment-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease;
}

.segment-item:hover .segment-thumb img {
  transform: scale(1.05);
}

.segment-thumb .segment-time-badge {
  position: absolute;
  bottom: 4px;
  right: 4px;
  background: var(--badge-bg);
  color: var(--on-dark);
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
  font-weight: 500;
  line-height: 1;
}

.segment-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 0;
  height: 68px;
}

.segment-info .segment-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-strong);
  margin-bottom: 4px;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.segment-meta {
  font-size: 13px;
  color: var(--text-sub);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-weight: normal;
}

.mindmap-placeholder, .chat-placeholder, .chat-empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  gap: 16px;
}

.chat-tab-content {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.chat-message {
  display: flex;
}

.chat-message.user {
  justify-content: flex-end;
}

.chat-message.assistant {
  justify-content: flex-start;
}

.chat-bubble-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 88%;
}

.reasoning-box {
  background: var(--surface-1);
  border-radius: 8px;
  border: 1px solid var(--card-border);
  overflow: hidden;
  font-size: 13px;
  margin-bottom: 4px;
  transition: all 0.2s ease;
}

.reasoning-box:hover {
  border-color: var(--text-muted);
}

.reasoning-box details summary {
  padding: 8px 12px;
  cursor: pointer;
  color: var(--text-sub);
  font-weight: 500;
  user-select: none;
  background: var(--surface-1);
  display: flex;
  align-items: center;
  justify-content: space-between;
  transition: background 0.2s;
}

.reasoning-box details summary:hover {
  background: var(--hover-bg);
  color: var(--text-main);
}

.reasoning-box details summary::marker {
  content: '';
}

.reasoning-box details summary::-webkit-details-marker {
  display: none;
}

.summary-left,
.summary-right {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.summary-icon {
  display: flex;
  align-items: center;
  color: var(--text-muted);
  font-size: 14px;
}

.summary-title {
  color: var(--text-sub);
  font-weight: 600;
}

.summary-hint {
  font-size: 12px;
  color: var(--text-muted);
  opacity: 0.8;
}

.summary-chevron {
  display: flex;
  align-items: center;
  color: var(--text-muted);
  transform: rotate(0deg);
  transition: transform 0.2s ease;
}

.summary-chevron.open {
  transform: rotate(90deg);
}

.reasoning-content {
  padding: 12px 16px;
  border-top: 1px solid var(--card-border);
  color: var(--text-sub);
  background: var(--surface-1);
  max-height: 400px;
  overflow-y: auto;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
}

.chat-message.assistant.reasoning .chat-bubble-container {
  max-width: 80%;
}

.chat-bubble-wrapper {
  position: relative;
  display: flex;
  max-width: 88%;
  overflow: visible;
}

.chat-bubble-container {
  position: relative;
  overflow: visible;
}

.chat-delete-btn {
  position: absolute;
  top: -12px;
  right: -12px;
  width: 24px;
  height: 24px;
  background: #fff;
  border: 2px solid #323232;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  opacity: 1;
  transition: all 0.2s;
  z-index: 100;
  box-shadow: 2px 2px #323232;
  color: #323232;
}
  
  .chat-bubble-wrapper:hover .chat-delete-btn,
  .chat-bubble-container:hover .chat-delete-btn {
    opacity: 1;
  }

.chat-delete-btn:hover {
  transform: scale(1.1);
  background: #ffebeb;
  color: #f53f3f;
}

/* Chat Bubbles */
.chat-bubble {
  max-width: 100%;
  padding: 14px 18px;
  border-radius: 5px;
  background: #fff;
  color: #1a1a1a;
  border: 3px solid #323232;
  line-height: 1.7;
  white-space: pre-wrap;
  box-shadow: 5px 5px #323232;
  transition: transform 0.1s ease, box-shadow 0.1s ease;
}

.chat-message.assistant .chat-bubble {
  border-radius: 5px;
  background-color: #fff;
}

.chat-message.user .chat-bubble {
  border-radius: 5px;
  background: #fff;
  color: #1a1a1a;
  border: 3px solid #323232;
  box-shadow: 5px 5px #323232;
}

/* Markdown Styles inside Bubble */
.chat-bubble.markdown-body {
  white-space: normal;
  word-break: break-word;
}

.chat-bubble.markdown-body :deep(p) {
  margin-bottom: 12px;
}

.chat-bubble.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.chat-bubble.markdown-body :deep(pre) {
  background: var(--surface-1);
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 12px 0;
  border: 1px solid var(--card-border);
}

.chat-bubble.markdown-body :deep(code) {
  font-family: monospace;
  background: rgba(150, 150, 150, 0.1);
  padding: 2px 5px;
  border-radius: 4px;
  color: var(--primary-color);
}

.chat-message.user .chat-bubble :deep(code) {
  background: rgba(127, 127, 127, 0.2);
  color: var(--text-main);
}

.chat-bubble.markdown-body :deep(strong) {
  font-weight: 700;
  color: inherit;
}

.chat-bubble.markdown-body :deep(em) {
  font-style: italic;
}

.chat-bubble.markdown-body :deep(ul), 
.chat-bubble.markdown-body :deep(ol) {
  padding-left: 20px;
  margin: 8px 0;
}

.chat-bubble.markdown-body :deep(li) {
  list-style: inherit;
  margin-bottom: 4px;
}

.chat-bubble.markdown-body :deep(blockquote) {
  border-left: 4px solid var(--card-border-strong);
  padding-left: 12px;
  margin: 12px 0;
  color: var(--text-sub);
  font-style: italic;
}

.chat-bubble.markdown-body :deep(h1),
.chat-bubble.markdown-body :deep(h2),
.chat-bubble.markdown-body :deep(h3),
.chat-bubble.markdown-body :deep(h4) {
  font-weight: 700;
  margin: 20px 0 10px;
  line-height: 1.4;
  color: inherit;
}

.chat-bubble.markdown-body :deep(h1:first-child),
.chat-bubble.markdown-body :deep(h2:first-child),
.chat-bubble.markdown-body :deep(h3:first-child) {
  margin-top: 0;
}

.chat-bubble.markdown-body :deep(a) {
  color: var(--primary-color);
  text-decoration: none;
  font-weight: 500;
}

.chat-message.user .chat-bubble :deep(a) {
  color: #fff;
  text-decoration: underline;
}

.chat-bubble.markdown-body :deep(a:hover) {
  text-decoration: underline;
}

.chat-input-area {
  padding: 12px 16px;
  border-top: 1px solid var(--card-border);
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.chat-input {
  flex: 1;
}

.chat-input :deep(.arco-textarea-wrapper) {
  background-color: var(--input-bg);
  border: 1px solid var(--input-border);
  border-radius: 16px;
}

/* Modal Styles */
.mindmap-loading {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  gap: 16px;
  min-height: 400px;
}

.mindmap-tab-content {
  flex: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.mindmap-placeholder {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  gap: 16px;
}

.courseware-tab-content {
  flex: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  background-color: var(--surface-1);
  padding-bottom: 40px;
}

.courseware-grid-wrap {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.courseware-grid {
  flex: none;
  overflow: visible;
  padding: 16px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  align-content: start;
  min-height: 0;
}

.courseware-actions {
  padding: 16px 16px 0;
}

.courseware-item {
  background: var(--surface-0);
  border: 1px solid var(--card-border);
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: all 0.2s;
}

.courseware-item:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-2);
  border-color: var(--primary-color);
}

.courseware-thumb {
  aspect-ratio: 16/9;
  min-height: 120px;
  overflow: hidden;
  background: var(--surface-2);
  position: relative;
}

.courseware-select-wrap {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 2;
  /* Removed background and padding to let UVCheckbox stand alone */
}

.courseware-select {
  margin: 0;
}

.courseware-ocr-results {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.courseware-ocr-item {
  border: 1px solid var(--card-border);
  border-radius: 12px;
  background: var(--surface-0);
  padding: 12px 14px;
}

.courseware-ocr-item-header {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 8px;
  color: var(--text-sub);
  font-size: 13px;
}

.courseware-ocr-item-header .ocr-time {
  font-family: monospace;
  color: var(--primary-color);
  font-weight: 600;
}

.courseware-ocr-text {
  word-break: break-word;
  color: var(--text-main);
  overflow-x: auto;
  max-width: 100%;
}

.courseware-info {
  padding: 8px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid var(--card-border);
  color: var(--text-sub);
  font-size: 13px;
}

.courseware-info .info-right {
  display: flex;
  gap: 4px;
}

.courseware-info .info-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.courseware-info .time-stamp {
  font-size: 12px; 
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 4px;
}

/* Custom Scrollbar */
.transcript-list::-webkit-scrollbar,
.detail-text-area::-webkit-scrollbar,
.keyframes-tab-content::-webkit-scrollbar,
.courseware-tab-content::-webkit-scrollbar,
.chat-messages::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.transcript-list::-webkit-scrollbar-thumb,
.detail-text-area::-webkit-scrollbar-thumb,
.keyframes-tab-content::-webkit-scrollbar-thumb,
.courseware-tab-content::-webkit-scrollbar-thumb,
.chat-messages::-webkit-scrollbar-thumb {
  background: var(--text-muted);
  border-radius: 3px;
  opacity: 0.5;
}

.transcript-list::-webkit-scrollbar-track,
.detail-text-area::-webkit-scrollbar-track,
.keyframes-tab-content::-webkit-scrollbar-track,
.courseware-tab-content::-webkit-scrollbar-track,
.chat-messages::-webkit-scrollbar-track {
  background: transparent;
}

.transcript-list::-webkit-scrollbar-button,
.detail-text-area::-webkit-scrollbar-button,
.keyframes-tab-content::-webkit-scrollbar-button,
.courseware-tab-content::-webkit-scrollbar-button,
.chat-messages::-webkit-scrollbar-button {
  display: none;
}
</style>
