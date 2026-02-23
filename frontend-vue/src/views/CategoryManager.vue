<template>
  <div class="category-manager-page">
    <div class="category-sidebar">
      <div class="sidebar-header">
        <div class="title">分类管理</div>
        <a-button type="text" size="small" @click="openCreateFolderModal">
          <template #icon><icon-plus /></template>
        </a-button>
      </div>
      <div class="folder-tree-container">
        <div 
          class="folder-item" 
          :class="{ active: selectedFolderId === 'all' }"
          @click="selectFolder('all')"
        >
          <icon-apps /> 全部资源
        </div>
        <div 
          class="folder-item" 
          :class="{ active: selectedFolderId === 'uncategorized', 'drag-over': dragOverId === 'uncategorized' }"
          @click="selectFolder('uncategorized')"
          @dragover="onDragOver"
          @dragenter.prevent="dragOverId = 'uncategorized'"
          @dragleave="onDragLeave('uncategorized', $event)"
          @drop="onDrop($event, 'uncategorized')"
        >
          <icon-question-circle /> 未分类
        </div>
        
        <a-tree
          :data="folderTreeData"
          block-node
          default-expand-all
          :selected-keys="selectedFolderId ? [selectedFolderId] : []"
          @select="onTreeSelect"
        >
          <template #switcher-icon="node, { isLeaf }">
            <icon-down v-if="!isLeaf" />
          </template>
          <template #title="node">
            <a-dropdown
              trigger="contextMenu"
              alignPoint
              @select="(v) => handleFolderContext(v, node)"
              :style="{ display: 'block' }"
            >
              <div 
                class="tree-node-title"
                :class="{ 'drag-over': dragOverId === node.id }"
                @dragover="onDragOver"
                @dragenter.prevent="dragOverId = node.id"
                @dragleave="onDragLeave(node.id, $event)"
                @drop.stop="onDrop($event, node.id)"
              >
                <div style="display: flex; align-items: center; gap: 6px;">
                  <icon-folder style="color: #ffb400; font-size: 16px;" />
                  <span>{{ node.name }}</span>
                </div>
              </div>
              <template #content>
                <a-doption value="edit">编辑</a-doption>
                <a-doption value="delete">删除</a-doption>
              </template>
            </a-dropdown>
          </template>
        </a-tree>
      </div>
    </div>

    <div class="category-content">
      <div class="content-header">
        <div class="header-title">{{ currentFolderName }}</div>
        <div class="header-actions">
           <a-select v-model="sortMode" class="sort-select">
             <a-option value="title_nat">标题（自然）</a-option>
             <a-option value="time_desc">时间（最新）</a-option>
             <a-option value="time_asc">时间（最旧）</a-option>
           </a-select>
           <a-button @click="refreshAssets">
             <template #icon><icon-refresh /></template>
             刷新
           </a-button>
        </div>
      </div>
      
      <div class="assets-grid" v-if="assets.length">
        <div
          v-for="item in sortedAssets"
          :key="item.md5"
          :id="'card-' + item.md5"
          class="card-sm"
          draggable="true"
          @dragstart="onDragStart(item, $event)"
          @click="openItem(item)"
        >
          <div class="card-content-wrapper">
            <!-- Move Button -->
            <a-dropdown @select="(fid) => moveAsset(item, fid)">
              <a-button type="text" class="move-btn" @click.stop>
                <template #icon><icon-folder /></template>
              </a-button>
              <template #content>
                <a-doption :value="'uncategorized'">未分类</a-doption>
                <a-doption v-for="f in flatFolders" :key="f.id" :value="f.id">{{ f.name }}</a-doption>
              </template>
            </a-dropdown>

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
            <div class="format-label" v-if="getFormatLabel(item)">
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
      <div v-else class="empty-state">
        <a-empty description="暂无资源" />
      </div>
    </div>

    <!-- Create/Edit Folder Modal -->
    <a-modal v-model:visible="folderModalVisible" :title="folderModalType === 'create' ? '新建分类' : '编辑分类'" @ok="handleFolderSubmit">
      <a-form :model="folderForm">
        <a-form-item field="name" label="名称">
          <a-input v-model="folderForm.name" placeholder="请输入分类名称" />
        </a-form-item>
        <a-form-item field="parent_id" label="父级分类">
           <a-tree-select 
             v-model="folderForm.parent_id" 
             :data="folderTreeData" 
             placeholder="无（作为根分类）"
             allow-clear
           />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { 
  IconPlus, IconApps, IconQuestionCircle, IconEdit, IconDelete, 
  IconRefresh, IconFile, IconPlayCircle, IconFolder, IconDown
} from '@arco-design/web-vue/es/icon'
import { useConfigStore } from '../stores/config'
import coverMD from '../assert/author_bg_card/MD.jpg'
import coverMP4 from '../assert/author_bg_card/MP4.jpg'
import coverPDF from '../assert/author_bg_card/PDF.jpg'
import coverTXT from '../assert/author_bg_card/TXT.jpg'

const router = useRouter()
const configStore = useConfigStore()
const backendBaseUrl = computed(() => (configStore.backend_base_url || '').replace(/\/+$/, ''))

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

const getItemTitle = (item) => decodeTitle(item?.content_json?.title || item?.display_name || item?.md5)

const folderTreeData = ref([])
const flatFolders = ref([])
const assets = ref([])
const sortMode = ref('title_nat')
const selectedFolderId = ref('all')
const folderModalVisible = ref(false)
const folderModalType = ref('create')
const folderForm = ref({ name: '', parent_id: null, id: null })
const dragOverId = ref(null)
const draggedItem = ref(null)

const collator = new Intl.Collator('zh-Hans-CN', { numeric: true, sensitivity: 'base' })
const sortedAssets = computed(() => {
  const list = Array.isArray(assets.value) ? [...assets.value] : []
  const mode = String(sortMode.value || 'title_nat')
  const getTitle = (it) => decodeTitle(it?.content_json?.title || it?.display_name || it?.md5 || '').trim()
  const getTime = (it) => {
    const v = it?.created_at
    if (!v) return 0
    if (typeof v === 'number') return v
    const t = Date.parse(v)
    return Number.isFinite(t) ? t : 0
  }

  list.sort((a, b) => {
    if (mode === 'time_desc') {
      return (getTime(b) - getTime(a)) || collator.compare(getTitle(a), getTitle(b))
    }
    if (mode === 'time_asc') {
      return (getTime(a) - getTime(b)) || collator.compare(getTitle(a), getTitle(b))
    }

    const ta = getTitle(a)
    const tb = getTitle(b)
    if (!ta && !tb) return (getTime(b) - getTime(a)) || collator.compare(String(a?.md5 || ''), String(b?.md5 || ''))
    if (!ta) return 1
    if (!tb) return -1
    const c = collator.compare(ta, tb)
    return c || (getTime(b) - getTime(a)) || collator.compare(String(a?.md5 || ''), String(b?.md5 || ''))
  })

  return list
})

const currentFolderName = computed(() => {
  if (selectedFolderId.value === 'all') return '全部资源'
  if (selectedFolderId.value === 'uncategorized') return '未分类'
  const folder = flatFolders.value.find(f => f.id === selectedFolderId.value)
  return folder ? folder.name : '未知分类'
})

const fetchFolders = async () => {
  try {
    const res = await fetch(`${backendBaseUrl.value}/folders`)
    if (!res.ok) throw new Error('Fetch folders failed')
    const data = await res.json()
    
    // Process tree data for a-tree (needs key/title)
    const process = (nodes) => {
      return nodes.map(n => ({
        key: n.id,
        title: n.name,
        name: n.name, // Keep original name property
        id: n.id,
        children: n.children ? process(n.children) : []
      }))
    }
    
    folderTreeData.value = process(data.folders || [])
    
    // Flatten for dropdown
    const flatten = (nodes) => {
      let res = []
      for (const n of nodes) {
        res.push({ id: n.id, name: n.name })
        if (n.children) res = res.concat(flatten(n.children))
      }
      return res
    }
    flatFolders.value = flatten(folderTreeData.value)
    
  } catch (e) {
    Message.error(e.message)
  }
}

const fetchAssets = async () => {
  try {
    let url = `${backendBaseUrl.value}/analysis/list?limit=100`
    if (selectedFolderId.value === 'uncategorized') {
      url += `&folder_id=uncategorized`
    } else if (selectedFolderId.value !== 'all') {
      url += `&folder_id=${selectedFolderId.value}`
    }
    
    const res = await fetch(url)
    if (!res.ok) throw new Error('Fetch assets failed')
    const data = await res.json()
    assets.value = data.items || []
  } catch (e) {
    Message.error(e.message)
  }
}

const refreshAssets = () => {
  fetchAssets()
}

const selectFolder = (id) => {
  selectedFolderId.value = id
  fetchAssets()
}

const onTreeSelect = (keys) => {
  if (keys.length) {
    selectFolder(keys[0])
  }
}

const openCreateFolderModal = () => {
  folderModalType.value = 'create'
  folderForm.value = { name: '', parent_id: null }
  folderModalVisible.value = true
}

const openEditFolderModal = (node) => {
  folderModalType.value = 'edit'
  folderForm.value = { name: node.name, parent_id: null, id: node.id } // Parent ID handling is tricky with tree select recursion, simplified for now
  folderModalVisible.value = true
}

const handleFolderContext = (action, node) => {
  const v = String(action || '').trim()
  if (!v) return
  if (v === 'edit') {
    openEditFolderModal(node)
    return
  }
  if (v === 'delete') {
    deleteFolder(node)
  }
}

const handleFolderSubmit = async () => {
  try {
    const isEdit = folderModalType.value === 'edit'
    const url = isEdit 
      ? `${backendBaseUrl.value}/folders/${folderForm.value.id}` 
      : `${backendBaseUrl.value}/folders`
    
    const method = isEdit ? 'PATCH' : 'POST'
    
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: folderForm.value.name,
        parent_id: folderForm.value.parent_id
      })
    })
    
    if (!res.ok) throw new Error('Operation failed')
    
    Message.success(isEdit ? '更新成功' : '创建成功')
    folderModalVisible.value = false
    fetchFolders()
  } catch (e) {
    Message.error(e.message)
  }
}

const deleteFolder = async (node) => {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除分类 "${node.name}" 吗？分类下的资源将变为未分类。`,
    onOk: async () => {
      try {
        const res = await fetch(`${backendBaseUrl.value}/folders/${node.id}`, { method: 'DELETE' })
        if (!res.ok) throw new Error('Delete failed')
        Message.success('删除成功')
        if (selectedFolderId.value === node.id) {
          selectedFolderId.value = 'all'
        }
        fetchFolders()
        fetchAssets() // Assets might have moved
      } catch (e) {
        Message.error(e.message)
      }
    }
  })
}

const openItem = (item) => {
  const md5 = String(item?.md5 || '').trim().toLowerCase()
  if (!md5) return

  if (!item.is_read) {
    item.is_read = true
    fetch(`${backendBaseUrl.value}/analysis/${encodeURIComponent(md5)}/read`, { method: 'POST' }).catch(() => {})
  }
  
  const at = String(item?.asset_type || '').trim().toLowerCase()
  if (at === 'document' || at === 'file') {
    router.push({ name: 'AiFileSummary', query: { md5 } })
  } else {
    router.push({ name: 'AiVideoSummary', query: { md5 } })
  }
}

const handleDelete = async (item) => {
  Modal.warning({
    title: '确认删除',
    content: '删除后无法恢复，是否继续？',
    hideCancel: false,
    onOk: async () => {
      try {
        const res = await fetch(`${backendBaseUrl.value}/analysis/${item.md5}`, {
          method: 'DELETE',
        })
        if (!res.ok) {
          const txt = await res.text()
          throw new Error(txt || '删除失败')
        }
        Message.success('已删除')
        fetchAssets()
      } catch (e) {
        Message.error(e.message || '删除失败')
      }
    }
  })
}

const getFormatLabel = (item) => {
  const dn = String(item?.display_name || '').trim()
  if (dn) {
    const clean = dn.split('?', 1)[0].split('#', 1)[0]
    const idx = clean.lastIndexOf('.')
    if (idx > -1 && idx < clean.length - 1) {
      const ext = clean.slice(idx + 1).toUpperCase()
      if (['PDF', 'DOC', 'DOCX', 'PPT', 'PPTX', 'TXT', 'MD', 'MP4', 'MP3', 'MOV', 'AVI', 'MKV', 'WAV', 'M4A'].includes(ext)) {
        return ext
      }
    }
  }

  const mt = String(item?.mime_type || '').toLowerCase()
  if (mt) {
    if (mt.includes('pdf')) return 'PDF'
    if (mt.includes('word') || mt.includes('document')) return 'DOCX'
    if (mt.includes('powerpoint') || mt.includes('presentation')) return 'PPTX'
    if (mt.includes('markdown')) return 'MD'
    if (mt.includes('text') || mt.includes('plain')) return 'TXT'
    if (mt.includes('octet-stream')) return 'FILE'
    const parts = mt.split('/')
    if (parts.length > 1) return parts[1].toUpperCase()
    return mt.toUpperCase()
  }

  const sr = String(item?.source_ref || '').trim()
  if (sr) {
    const clean = sr.split('?', 1)[0].split('#', 1)[0]
    const idx = clean.lastIndexOf('.')
    if (idx > -1 && idx < clean.length - 1) {
      return clean.slice(idx + 1).toUpperCase()
    }
  }

  // 3. 其次检查 asset_type
  const at = (item.asset_type || '').toUpperCase()
  if (at === 'VIDEO' || at === 'AUDIO' || at === 'UNKNOWN') return 'VIDEO'
  if (at === 'DOCUMENT' || at === 'FILE') return 'DOC'

  // 4. 内容特征检查
  // 如果有 segments，通常是音视频
  if (item.content_json?.segments?.length > 0) return 'VIDEO'

  // 5. 来源 URL 特征
  const sr2 = String(item.source_ref || '').toLowerCase()
  if (sr2.includes('bilibili')) return 'BILI'
  if (sr2.includes('youtube') || sr2.includes('youtu.be')) return 'YT'

  return at || 'FILE'
}

const getCoverUrl = (item) => {
  const cj = item.content_json
  if (cj && Array.isArray(cj.segments) && cj.segments.length > 0) {
    const seg = cj.segments[0]
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

const onDragOver = (event) => {
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'move'
  }
}

const onDragStart = (item, event) => {
  draggedItem.value = item
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', item.md5)
    // Optional: set custom drag image
  }
}

const onDragLeave = (folderId, event) => {
  const currentTarget = event.currentTarget
  const relatedTarget = event.relatedTarget
  // If moving to a child element, don't clear
  if (currentTarget && relatedTarget && currentTarget.contains(relatedTarget)) {
    return
  }
  if (dragOverId.value === folderId) {
    dragOverId.value = null
  }
}

const animateDrop = async (item, targetEl) => {
  const cardEl = document.getElementById(`card-${item.md5}`)
  if (!cardEl) return

  const rect = cardEl.getBoundingClientRect()
  const clone = cardEl.cloneNode(true)
  
  clone.style.position = 'fixed'
  clone.style.left = rect.left + 'px'
  clone.style.top = rect.top + 'px'
  clone.style.width = rect.width + 'px'
  clone.style.height = rect.height + 'px'
  clone.style.zIndex = '9999'
  clone.style.transition = 'all 0.5s cubic-bezier(0.25, 1, 0.5, 1)'
  clone.style.transformOrigin = 'center center'
  clone.style.pointerEvents = 'none' 
  clone.style.boxShadow = '0 10px 20px rgba(0,0,0,0.2)'
  
  // Clean up cloned ID to avoid duplicates
  clone.removeAttribute('id')
  
  document.body.appendChild(clone)
  
  // Calculate target center
  const targetRect = targetEl.getBoundingClientRect()
  const targetX = targetRect.left + targetRect.width / 2 - rect.width / 2
  const targetY = targetRect.top + targetRect.height / 2 - rect.height / 2
  
  // Force reflow
  clone.getBoundingClientRect()
  
  // Start animation
  clone.style.left = targetX + 'px'
  clone.style.top = targetY + 'px'
  clone.style.transform = 'scale(0.05)'
  clone.style.opacity = '0'
  
  // Wait for animation
  await new Promise(r => setTimeout(r, 500))
  
  if (clone.parentNode) {
    clone.parentNode.removeChild(clone)
  }
}

const onDrop = async (event, folderId) => {
  dragOverId.value = null
  
  // Prefer internal state
  let item = draggedItem.value
  
  // Fallback to dataTransfer if needed (e.g. if we support cross-window drag in future, but currently internal is safer)
  if (!item && event.dataTransfer) {
    const md5 = event.dataTransfer.getData('text/plain')
    if (md5) {
      item = assets.value.find(a => a.md5 === md5)
    }
  }

  if (item) {
    // Start animation without blocking too much, but wait a bit to ensure visual start
    if (event.currentTarget) {
       animateDrop(item, event.currentTarget)
    }
    // Small delay to let animation start before list refresh potentially removes the item
    await new Promise(r => setTimeout(r, 50))
    await moveAsset(item, folderId)
  }
  draggedItem.value = null
}

const moveAsset = async (asset, folderId) => {
  try {
    const fid = folderId === 'uncategorized' ? null : folderId
    const res = await fetch(`${backendBaseUrl.value}/assets/${asset.md5}/move`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder_id: fid })
    })
    if (!res.ok) throw new Error('Move failed')
    Message.success('移动成功')
    fetchAssets()
  } catch (e) {
    Message.error(e.message)
  }
}

const formatTime = (iso) => {
  if (!iso) return ''
  return new Date(iso).toLocaleString()
}

onMounted(() => {
  fetchFolders()
  fetchAssets()
})
</script>

<style scoped>
.category-manager-page {
  display: flex;
  height: 100%;
  background: var(--surface-1);
}

.category-sidebar {
  width: 260px;
  border-right: 1px solid var(--card-border);
  display: flex;
  flex-direction: column;
  background: var(--surface-0);
}

.sidebar-header {
  padding: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--card-border);
}

.title {
  font-weight: 600;
  font-size: 16px;
}

.folder-tree-container {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 8px;
}

.folder-item {
  padding: 8px 12px;
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  color: var(--text-main);
}

.folder-item:hover {
  background: var(--surface-2);
}

.folder-item.active {
  background: var(--primary-light);
  color: var(--primary-color);
}

.folder-item.drag-over,
.tree-node-title.drag-over {
  background: var(--primary-light);
  outline: 2px dashed var(--primary-color);
  color: var(--primary-color);
}

.tree-node-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  height: 100%;
}

.category-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 24px;
}

.content-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.sort-select {
  width: 160px;
}

.header-title {
  font-size: 20px;
  font-weight: 600;
}

.assets-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 24px;
  overflow-y: auto;
  overflow-x: hidden;
  padding-bottom: 20px;
  padding-right: 12px; /* Add space for scrollbar/card edge */
}

/* Neo Brutalism data card - Matches Video.vue */
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

.move-btn {
  position: absolute;
  top: 8px;
  right: 44px;
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

.card-sm:hover .delete-btn,
.card-sm:hover .move-btn {
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

.default-cover-img {
  object-position: 50% 35%;
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

.tags-container {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.tag-badge {
  font-size: 11px;
  background-color: #f2f3f5;
  color: #1d2129;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
  border: 1px solid #e5e6eb;
}

.info-meta {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Custom Scrollbar */
.folder-tree-container::-webkit-scrollbar,
.assets-grid::-webkit-scrollbar {
  width: 4px;
  height: 0;
}

.folder-tree-container::-webkit-scrollbar:horizontal,
.assets-grid::-webkit-scrollbar:horizontal {
  height: 0;
  display: none;
}

.folder-tree-container::-webkit-scrollbar-thumb,
.assets-grid::-webkit-scrollbar-thumb {
  background: var(--text-muted);
  border-radius: 2px;
  opacity: 0.5;
}

.folder-tree-container::-webkit-scrollbar-track,
.assets-grid::-webkit-scrollbar-track {
  background: transparent;
}

.folder-tree-container::-webkit-scrollbar-button,
.assets-grid::-webkit-scrollbar-button {
  display: none;
  width: 0;
  height: 0;
}

.folder-tree-container::-webkit-scrollbar-corner,
.assets-grid::-webkit-scrollbar-corner {
  display: none;
}

.folder-tree-container,
.assets-grid {
  scrollbar-width: thin;
  scrollbar-color: var(--text-muted) transparent;
}
</style>
