import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useHistoryStore = defineStore('history', () => {
  const history = ref([])
  const MAX_HISTORY = 50

  // Initialize from localStorage
  const stored = localStorage.getItem('view_history')
  if (stored) {
    try {
      history.value = JSON.parse(stored)
    } catch (e) {
      console.error('Failed to parse history', e)
    }
  }

  // Persist to localStorage whenever history changes
  watch(history, (newVal) => {
    localStorage.setItem('view_history', JSON.stringify(newVal))
  }, { deep: true })

  const addToHistory = (item) => {
    if (!item || !item.md5) return

    // Remove existing entry for same md5 to move it to top
    const index = history.value.findIndex(h => h.md5 === item.md5)
    if (index > -1) {
      history.value.splice(index, 1)
    }

    // Add to beginning
    const historyItem = {
      md5: item.md5,
      title: item.content_json?.title || item.display_name || item.md5,
      summary: item.content_json?.summary,
      cover_url: item.content_json?.cover_url || item.cover_url, // Handle different structures
      asset_type: item.asset_type,
      tags: item.content_json?.tags || [],
      timestamp: Date.now(),
      // Store minimal needed data
      content_json: item.content_json, 
      display_name: item.display_name,
      created_at: item.created_at
    }

    history.value.unshift(historyItem)

    // Trim to max size
    if (history.value.length > MAX_HISTORY) {
      history.value = history.value.slice(0, MAX_HISTORY)
    }
  }

  const clearHistory = () => {
    history.value = []
  }

  const removeFromHistory = (md5) => {
    const index = history.value.findIndex(h => h.md5 === md5)
    if (index > -1) {
      history.value.splice(index, 1)
    }
  }

  return {
    history,
    addToHistory,
    clearHistory,
    removeFromHistory
  }
})
