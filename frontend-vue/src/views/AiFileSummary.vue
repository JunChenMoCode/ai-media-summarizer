<template>
  <div class="video-summary-container">
    <div class="summary-content">
      <!-- Left Column: File Preview -->
      <div class="left-panel">
        <input
          ref="localFileInputRef"
          type="file"
          accept=".pdf,.docx,.doc,.pptx,.ppt,.txt,.md"
          style="display: none"
          @change="handleLocalFileInputChange"
        />
        <div class="video-topbar">
          <div class="video-topbar-input">
            <a-input-search
              v-model="fileUrlInput"
              placeholder="粘贴文件直链，回车加载"
              button-text="加载"
              search-button
              allow-clear
              :disabled="importingFile"
              @search="handleUrlSubmit"
            />
          </div>
          <a-button type="outline" @click="openLocalFilePicker">
            <template #icon><icon-upload /></template>
            上传文档
          </a-button>
        </div>
        <div
          class="video-wrapper"
          @dragenter.prevent="handleFileDragEnter"
          @dragover.prevent="handleFileDragOver"
          @dragleave.prevent="handleFileDragLeave"
          @drop.prevent="handleFileDrop"
        >
          <div v-if="loading" class="video-overlay">
            <ChipLoader :progress="progressPercent" :text="progressMsg" />
          </div>
          <div v-else-if="fileDragActive" class="video-drag-overlay">
            <div class="video-drag-overlay-inner">
              <div class="video-drag-title">松开即可加载文档</div>
              <div class="video-drag-sub">支持 PDF, Word, PPT, TXT, MD</div>
            </div>
          </div>
          <div v-if="!fileUrl && !fileContent" class="video-placeholder" @click="openLocalFilePicker">
            <div class="placeholder-content">
              <icon-file :style="{ fontSize: '40px' }" />
              <p class="placeholder-title">点击添加文档</p>
              <p class="placeholder-desc">支持 PDF, Word, PPT, TXT, MD</p>
            </div>
          </div>
          
          <!-- PDF Preview -->
          <iframe 
            v-else-if="fileType === '.pdf' && fileUrl" 
            :src="fileUrl" 
            class="summary-video-player"
            style="border:none; width: 100%; height: 100%; background: white;"
          ></iframe>

          <!-- DOCX Preview -->
          <VueOfficeDocx
            v-else-if="(fileType === '.docx' || fileType === '.doc') && fileUrl"
            :src="fileUrl"
            style="width: 100%; height: 100%; overflow-y: auto; background: white;"
          />

          <!-- PPTX Preview -->
          <VueOfficePptx
            v-else-if="(fileType === '.pptx' || fileType === '.ppt') && fileUrl"
            :src="fileUrl"
            style="width: 100%; height: 100%; overflow-y: auto; background: white;"
          />

          <!-- MD Preview -->
          <div v-else-if="fileType === '.md'" class="markdown-body" style="padding: 20px; overflow-y: auto; height: 100%; background: var(--surface-1);" v-html="renderedFilePreview"></div>

          <!-- Text Preview (Show Extracted Text) -->
          <div v-else class="file-preview-text" style="padding: 20px; overflow-y: auto; height: 100%; background: var(--surface-1); color: var(--text-1); white-space: pre-wrap; font-family: monospace;">
            <div v-if="fileContent">{{ fileContent }}</div>
            <div v-else class="preview-unavailable" style="display: flex; align-items: center; justify-content: center; height: 100%;">
              <p>Preview not available</p>
            </div>
          </div>
        </div>

        <div class="video-actions-bar">
          <a-button type="primary" size="large" @click="handleSubmit" :loading="loading" long>
            <template #icon><icon-robot /></template>
            智能分析与总结
          </a-button>

          <div class="secondary-actions">
            <a-button type="outline" @click="handleGenerateMindmap">
              <template #icon><icon-workflow /></template>
              生成思维导图
            </a-button>
            <a-button type="outline"><icon-share-internal /> 分享</a-button>
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
        <div class="summary-tags-bar" v-if="analysisData?.tags && analysisData.tags.length">
            <span v-for="(tag, idx) in analysisData.tags" :key="idx" class="tag-badge">
              #{{ tag }}
            </span>
        </div>
        <a-tabs v-model:active-key="activeRightTab" type="line" size="medium" :animation="true" class="summary-tabs">
          <!-- Tab 1: Detail -->
          <a-tab-pane key="detail" title="文稿笔记">
            <div class="detail-text-area" style="padding: 0; overflow: hidden; display: flex; flex-direction: column; position: relative;">
               <FloatingToggle v-model="isEditable" @change="toggleEditable" />
               <div v-show="isEditable" ref="editorRef" style="height: 100%;"></div>
               <div v-if="!isEditable" class="markdown-body" style="padding: 20px; overflow-y: auto; height: 100%;" v-html="renderedReport"></div>
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

          <!-- Tab 3: Chat -->
          <a-tab-pane key="chat" title="AI 对话">
            <div class="chat-tab-content">
              <div ref="chatListRef" class="chat-messages">
                <div v-if="!chatMessages.length" class="chat-empty">
                  <icon-message :style="{ fontSize: '48px', color: 'var(--text-muted)' }" />
                  <p>开始与 AI 讨论文件内容</p>
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
                  placeholder="针对文件内容提问..."
                  :auto-size="{ minRows: 1, maxRows: 4 }"
                  @keydown.enter.exact.prevent="handleChatSend"
                />
                <a-button type="primary" :loading="chatLoading" @click="handleChatSend">发送</a-button>
      </div>
    </div>
  </a-tab-pane>
</a-tabs>

<a-modal v-model:visible="showTitleModal" title="开始分析" @ok="startAnalysis" :ok-text="'开始分析'" :cancel-text="'取消'">
  <div style="padding: 20px;">
    <p style="margin-bottom: 16px;">请选择分析结果的标题命名方式：</p>
    <a-radio-group v-model="titlePreference" direction="vertical">
      <a-radio value="ai">使用 AI 生成的标题 (推荐)</a-radio>
      <a-radio value="filename">使用原文件名</a-radio>
    </a-radio-group>
  </div>
</a-modal>
</div>
    </div>
  </div>
</template>

<script setup>
import { AiEditor } from "aieditor";
import "aieditor/dist/style.css"
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useConfigStore } from '../stores/config'
import { useHistoryStore } from '../stores/history'
import { Message } from '@arco-design/web-vue'
import { marked } from 'marked'
import { processStreamedOutput, flushStreamBuffer } from '../utils/processStreamedOutput'
import ChipLoader from '../components/ChipLoader.vue'
import MindMap from '../components/MindMap.vue'
import FloatingToggle from '../components/FloatingToggle.vue'
import VueOfficeDocx from '@vue-office/docx'
import '@vue-office/docx/lib/index.css'
import VueOfficePptx from '@vue-office/pptx'
import { 
  File as IconFile,
  Upload as IconUpload,
  ArrowLeft as IconArrowLeft,
  Workflow as IconWorkflow,
  Bot as IconRobot,
  Trash2 as IconTrash,
  MessageSquare as IconMessage,
  ChevronRight as IconChevronRight,
  Share as IconShareInternal,
  RefreshCw as IconRefreshCw
} from 'lucide-vue-next'

const router = useRouter()
const route = useRoute()
const configStore = useConfigStore()
const historyStore = useHistoryStore()
const backendBaseUrl = computed(() => (configStore.backend_base_url || '').replace(/\/+$/, ''))
const backendWsBaseUrl = computed(() => {
  const base = backendBaseUrl.value
  if (base.startsWith('https://')) return base.replace(/^https:/, 'wss:')
  if (base.startsWith('http://')) return base.replace(/^http:/, 'ws:')
  return base
})

// State
const loading = ref(false)
const progressPercent = ref(0)
const progressMsg = ref('')
const report = ref('')
const analysisData = ref(null)
const fileUrl = ref('')
const filePath = ref('')
const fileMd5 = ref('')
const fileObj = ref(null)
const fileType = ref('')
const fileContent = ref('')
const fileUrlInput = ref('')
const importingFile = ref(false)
const activeRightTab = ref('detail')
const chatMessages = ref([])
const chatInput = ref('')
const chatLoading = ref(false)
const chatListRef = ref(null)
const mindmapData = ref(null)
const mindmapLoading = ref(false)
const localFileInputRef = ref(null)
const fileDragActive = ref(false)
const showTitleModal = ref(false)
const titlePreference = ref('ai')

// Editor state
const editorRef = ref(null)
const editorInstance = ref(null)
const isEditable = ref(false)

const resolveUrl = (url) => {
  const u = String(url || '').trim()
  if (!u) return ''
  if (u.match(/^https?:\/\//) || u.startsWith('blob:') || u.startsWith('data:')) return u
  if (u.startsWith('/static/')) {
    return `${backendBaseUrl.value}${u}`
  }
  return u
}

const resolveMarkdownImages = (text) => {
  if (!text) return ''
  return text.replace(/!\[(.*?)\]\((.*?)\)/g, (match, alt, url) => {
    return `![${alt}](${resolveUrl(url)})`
  })
}

const toggleEditable = (val) => {
  if (val) {
    nextTick(async () => {
       if (!editorInstance.value) {
           await initEditor()
       } else {
           if (editorInstance.value) {
              const content = report.value || ''
              const resolvedContent = resolveMarkdownImages(content)
              let htmlContent = marked.parse(resolvedContent)
              if (htmlContent instanceof Promise) htmlContent = await htmlContent
              editorInstance.value.setContent(htmlContent)
           }
       }
    })
  }
}

const initEditor = async () => {
  if (editorInstance.value) return
  if (!editorRef.value) return
  
  try {
    const content = report.value || ''
    console.log('[Debug] initEditor content length:', content.length)
    
    let htmlContent = ''
    try {
      const resolvedContent = resolveMarkdownImages(content)
      const parsed = marked.parse(resolvedContent)
      htmlContent = parsed instanceof Promise ? await parsed : parsed
    } catch (err) {
      console.error('[Debug] marked.parse failed:', err)
      htmlContent = `<p style="color:red">Markdown render error: ${err.message}</p><pre>${content}</pre>`
    }

    if (!htmlContent && content) {
        console.warn('[Debug] htmlContent is empty but content exists. Fallback to raw.')
        htmlContent = `<pre>${content}</pre>`
    }

    console.log('[Debug] htmlContent length:', htmlContent.length)

    const editorOptions = {
      element: editorRef.value,
      placeholder: "等待生成详解报告...",
      content: htmlContent,
      editable: true,
      image: {
        allowBase64: true,
        defaultSize: 350,
      }
    }

    if (configStore.openai_api_key) {
      editorOptions.ai = {
        models: {
          openai: {
            customUrl: `${configStore.openai_base_url.replace(/\/+$/, '')}/chat/completions`,
            apiKey: configStore.openai_api_key,
            model: configStore.llm_model,
          }
        }
      }
    }

    editorInstance.value = new AiEditor(editorOptions)
    console.log('[Debug] AiEditor instance created')
  } catch (e) {
    console.error('Failed to init AiEditor:', e)
    Message.error('编辑器初始化失败: ' + e.message)
  }
}

onMounted(() => {
  // Do not init editor on mount if not editable
  if (activeRightTab.value === 'detail' && isEditable.value) {
    nextTick(() => initEditor())
  }
})

watch(activeRightTab, (newVal) => {
  if (newVal === 'detail') {
    if (isEditable.value) {
      nextTick(() => {
        initEditor()
      })
    }
  }
})

let updateTimer = null

watch(report, (newVal) => {
  if (editorInstance.value) {
    if (updateTimer) clearTimeout(updateTimer)
    updateTimer = setTimeout(async () => {
      try {
        if (!editorInstance.value) return
        const resolved = resolveMarkdownImages(newVal || '')
        let html = marked.parse(resolved)
        if (html instanceof Promise) html = await html
        editorInstance.value.setContent(html)
      } catch (e) {
        console.warn('Editor update skipped:', e)
      }
    }, 300) // Throttle updates to 300ms
  }
})

onUnmounted(() => {
  if (updateTimer) clearTimeout(updateTimer)
  if (editorInstance.value) {
    editorInstance.value.destroy()
    editorInstance.value = null
  }
})

// Computed
const renderedReport = computed(() => {
  if (!report.value) return ''
  try {
    return marked.parse(report.value)
  } catch (e) {
    console.error('Render report error:', e)
    return report.value
  }
})

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

const inferFileType = (nameOrUrl, mimeType) => {
  const n = String(nameOrUrl || '').trim()
  if (n) {
    const clean = n.split('?', 1)[0].split('#', 1)[0]
    const idx = clean.lastIndexOf('.')
    if (idx > -1 && idx < clean.length - 1) {
      return '.' + clean.slice(idx + 1).toLowerCase()
    }
  }
  const mt = String(mimeType || '').toLowerCase()
  if (mt.includes('markdown')) return '.md'
  if (mt.includes('pdf')) return '.pdf'
  if (mt.includes('word')) return '.docx'
  if (mt.includes('powerpoint') || mt.includes('presentation')) return '.pptx'
  if (mt.includes('text')) return '.txt'
  return ''
}

const currentContentTitle = computed(() => {
  const analysisTitle = decodeTitle(analysisData.value?.title || '')
  if (analysisTitle) return analysisTitle
  const localName = String(fileObj.value?.name || '').trim()
  if (localName) return localName
  const path = decodeTitle(filePath.value || '')
  if (path) return path
  const url = decodeTitle(fileUrlInput.value || fileUrl.value || '')
  if (url) return url
  return '未加载内容'
})

const renderedFilePreview = computed(() => {
  if (fileType.value !== '.md') return ''
  if (!fileContent.value) return ''
  try {
    return marked.parse(fileContent.value, { gfm: true, breaks: true })
  } catch (e) {
    return fileContent.value
  }
})

// Methods
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

const goHome = () => {
  router.push({ name: 'Dashboard' })
}

const openLocalFilePicker = () => {
  const el = localFileInputRef.value
  if (!el) return
  el.value = ''
  el.click()
}

const handleFileDragEnter = () => {
  if (loading.value) return
  fileDragActive.value = true
}

const handleFileDragOver = () => {
  if (loading.value) return
  fileDragActive.value = true
}

const handleFileDragLeave = (e) => {
  const next = e?.relatedTarget
  if (next && e?.currentTarget && e.currentTarget.contains(next)) return
  fileDragActive.value = false
}

const handleFileDrop = (e) => {
  fileDragActive.value = false
  if (loading.value) {
    Message.warning('分析中，稍后再试')
    return
  }
  const file = e?.dataTransfer?.files?.[0] || null
  if (!file) return
  
  const name = String(file.name || '').toLowerCase()
  const validExt = /\.(pdf|docx|doc|pptx|ppt|txt|md)$/.test(name)
  
  if (!validExt) {
    Message.warning('不支持的文件格式。请上传 PDF, Word, PPT, TXT, MD')
    return
  }
  setLocalFile(file)
}

const handleLocalFileInputChange = (e) => {
  const file = e?.target?.files?.[0] || null
  if (!file) return
  setLocalFile(file)
}

const setLocalFile = (file) => {
  const prev = fileUrl.value
  if (prev && typeof prev === 'string' && prev.startsWith('blob:')) {
    try {
      URL.revokeObjectURL(prev)
    } catch (e) {}
  }

  const name = String(file?.name || '').toLowerCase()
  
  fileObj.value = file
  // Determine file type
  if (name.endsWith('.pdf')) fileType.value = '.pdf'
  else if (name.endsWith('.docx') || name.endsWith('.doc')) fileType.value = '.docx'
  else if (name.endsWith('.pptx') || name.endsWith('.ppt')) fileType.value = '.pptx'
  else if (name.endsWith('.txt')) fileType.value = '.txt'
  else if (name.endsWith('.md')) fileType.value = '.md'
  else fileType.value = ''

  filePath.value = ''
  fileUrl.value = URL.createObjectURL(file) 
  
  // Reset state
  report.value = ''
  analysisData.value = null
  mindmapData.value = null
  fileContent.value = ''
  fileMd5.value = ''

  // Read text content for TXT/MD immediately
  if (fileType.value === '.txt' || fileType.value === '.md') {
      const reader = new FileReader()
      reader.onload = (e) => {
          fileContent.value = e.target.result
      }
      reader.readAsText(file)
  }

  Message.success(`已加载文件: ${file.name}`)
}

const handleUrlSubmit = () => {
  if (!fileUrlInput.value) return

  importingFile.value = true
  fetch(`${backendBaseUrl.value}/import_file_url`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url: fileUrlInput.value }),
  })
    .then(async (res) => {
      if (!res.ok) {
        const err = await res.json().catch(() => null)
        const msg = err?.error || (await res.text().catch(() => '')) || 'Import failed'
        throw new Error(msg)
      }
      return res.json()
    })
    .then((data) => {
      const prev = fileUrl.value
      if (prev && typeof prev === 'string' && prev.startsWith('blob:')) {
        try {
          URL.revokeObjectURL(prev)
        } catch (e) {}
      }

      fileUrl.value = data.file_url || fileUrlInput.value
      fileContent.value = data.file_content
      
      // Determine type
      const ext = data.file_type || ''
      fileType.value = ext
      
      fileObj.value = null
      report.value = ''
      analysisData.value = null
      mindmapData.value = null
      
      Message.success('File loaded successfully')
    })
    .catch((e) => {
      Message.error(e?.message || 'Import failed')
    })
    .finally(() => {
      importingFile.value = false
    })
}

const buildConfig = () => ({
  openai_api_key: configStore.openai_api_key,
  openai_base_url: configStore.openai_base_url,
  llm_model: configStore.llm_model,
  ocr_engine: configStore.ocr_engine, // Might be needed for PDF/PPT
  vl_model: configStore.vl_model,
  vl_base_url: configStore.vl_base_url,
  vl_api_key: configStore.vl_api_key,
  // Required fields for ConfigModel
  model_size: configStore.model_size || 'base',
  device: configStore.device || 'cpu',
  compute_type: configStore.compute_type || 'int8',
  capture_offset: Number(configStore.capture_offset) || 0,
  title_preference: titlePreference.value,
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

    fileMd5.value = payload?.asset?.md5 || v
    let pUrl = payload?.access?.primary_url || ''
    if (pUrl.startsWith('/')) {
        pUrl = `${backendBaseUrl.value}${pUrl}`
    }
    fileUrl.value = pUrl
    filePath.value = payload?.asset?.source_ref || ''
    fileType.value = inferFileType(payload?.asset?.display_name || payload?.asset?.source_ref || '', payload?.asset?.mime_type)

    const analysis = pick('ai_analysis')?.json || null
    const reportArtifact = pick('report_markdown')
    const reportText = reportArtifact?.text || reportArtifact?.json?.content || ''
    analysisData.value = analysis
    report.value = reportText

    const mm = pick('mindmap_g6')?.json
    mindmapData.value = mm || null
    
    if (analysis?.raw_transcript) {
         fileContent.value = analysis.raw_transcript
    }

    const lastChat = pick('chat_session')?.json
    if (lastChat && Array.isArray(lastChat.messages) && lastChat.messages.length) {
      chatMessages.value = lastChat.messages
    }

    // Add to History
    historyStore.addToHistory({
      md5: payload?.asset?.md5 || v,
      display_name: payload?.asset?.display_name,
      created_at: payload?.asset?.created_at,
      asset_type: payload?.asset?.asset_type,
      mime_type: payload?.asset?.mime_type || analysis?.mime_type,
      title: analysis?.title || payload?.asset?.display_name,
      content_json: analysis
    })

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
          if (data.message.includes('Loading file')) progressPercent.value = 10
          else if (data.message.includes('Extracting text')) progressPercent.value = 30
          else if (data.message.includes('Analyzing content')) progressPercent.value = 50
          else if (data.message.includes('Generating summary')) progressPercent.value = 75
          else if (data.message.includes('Finalizing')) progressPercent.value = 90
        } else if (data.status === 'success') {
          report.value = data.report
          analysisData.value = data.data
          
          if (data.video_md5) {
            fileMd5.value = data.video_md5
          }

          if (data.data.raw_transcript) {
             fileContent.value = data.data.raw_transcript
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

const handleSubmit = async () => {
  const hasUploadFile = !!fileObj.value
  const hasContent = !!fileContent.value
  const hasUrl = !!fileUrl.value

  if (!hasUploadFile && !hasContent && !hasUrl) {
    Message.warning('Please load a file first')
    return
  }
  
  if (!configStore.openai_api_key) {
    Message.warning('Please set API Key in Settings first')
    return
  }

  showTitleModal.value = true
}

const startAnalysis = async () => {
  showTitleModal.value = false
  const hasUploadFile = !!fileObj.value
  const hasUrl = !!fileUrl.value

  loading.value = true
  progressPercent.value = 0
  progressMsg.value = 'Analyzing...'
  report.value = ''
  analysisData.value = null
  
  const config = buildConfig()

  try {
      const formData = new FormData()
      formData.append('config', JSON.stringify(config))
      
      if (hasUploadFile) {
          formData.append('file', fileObj.value)
      } else {
          if (hasUrl) {
             formData.append('file_url', fileUrl.value)
          } else if (fileContent.value) {
            const blob = new Blob([fileContent.value || ''], { type: 'text/plain' })
            formData.append('file', blob, 'imported.txt')
          }
      }

      const response = await fetch(`${backendBaseUrl.value}/analyze_file`, {
        method: 'POST',
        body: formData,
      })
      
      await readSseResponse(response)

  } catch (error) {
    Message.error(error.message || 'Unknown error during analysis')
    progressMsg.value = 'Error: ' + (error.message || 'Unknown error')
  } finally {
    loading.value = false
  }
}

const handleGenerateMindmap = async () => {
  if (!fileContent.value) {
    Message.warning('请先加载文件')
    return
  }
  
  mindmapLoading.value = true
  activeRightTab.value = 'mindmap'
  mindmapData.value = null

  try {
      const config = buildConfig();

      const response = await fetch(`${backendBaseUrl.value}/generate_mindmap`, {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json'
          },
          body: JSON.stringify({
              transcript: fileContent.value,
              config: config,
              video_md5: fileMd5.value || ''
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
  if (!fileContent.value && !analysisData.value) {
    Message.warning('请先加载并分析文件')
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
        transcript: fileContent.value || '',
        summary: analysisData.value?.summary || '',
        config: buildConfig(),
        video_md5: fileMd5.value || '',
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
  padding: 24px 24px 24px 24px;
  border-right: 1px solid var(--card-border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: var(--surface-1);
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
  flex: 1;
  min-height: 0;
  overflow: hidden;
  position: relative;
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
  margin-bottom: 0;
  flex-shrink: 0;
}

.secondary-actions {
  display: flex;
  gap: 12px;
}

.secondary-actions .arco-btn {
  flex: 1;
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

.chat-message-list {
  padding-bottom: 40px;
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.detail-text-area .markdown-body {
  padding-bottom: 40px;
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

.summary-tags-bar {
  padding: 8px 20px;
  background: var(--surface-0);
  border-bottom: 1px solid var(--card-border);
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.tag-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 4px;
  background: #e0e0e0;
  color: #323232;
  font-size: 12px;
  font-weight: 700;
  border: 1px solid #323232;
}

/* Custom Scrollbar - Use global styles instead */

</style>
