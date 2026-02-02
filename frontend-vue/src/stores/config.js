import { defineStore } from 'pinia'

export const useConfigStore = defineStore('config', {
  state: () => ({
    backend_base_url: localStorage.getItem('backend_base_url') || 'http://localhost:18000',
    openai_api_key: localStorage.getItem('openai_api_key') || '',
    openai_base_url: localStorage.getItem('openai_base_url') || 'https://api.siliconflow.cn/v1',
    llm_model: localStorage.getItem('llm_model') || 'deepseek-ai/DeepSeek-V2.5',
    ocr_engine: localStorage.getItem('ocr_engine') || 'vl',
    vl_model: localStorage.getItem('vl_model') || 'Pro/Qwen/Qwen2-VL-7B-Instruct',
    vl_base_url: localStorage.getItem('vl_base_url') || 'https://api.siliconflow.cn/v1',
    vl_api_key: localStorage.getItem('vl_api_key') || '',
    model_size: localStorage.getItem('model_size') || 'medium',
    device: localStorage.getItem('device') || 'cuda',
    compute_type: localStorage.getItem('compute_type') || 'float16',
    capture_offset: parseFloat(localStorage.getItem('capture_offset')) || 5.0,
    theme: localStorage.getItem('theme') || 'light',
  }),
  actions: {
    updateConfig(newConfig) {
      Object.assign(this, newConfig)
      // 持久化到 localStorage
      for (const key in newConfig) {
        localStorage.setItem(key, newConfig[key])
      }
    },
    toggleTheme() {
      this.theme = this.theme === 'dark' ? 'light' : 'dark'
      localStorage.setItem('theme', this.theme)
    }
  }
})
