<template>
  <div class="settings-page">
    <a-card :bordered="false" class="main-card settings-card">
      <div class="card-header-row">
        <span class="card-title">AI Model Configuration</span>
      </div>
      
      <a-form :model="form" layout="vertical" @submit="handleSave" class="settings-form">
        <div class="form-section">
          <div class="section-title">1. API Access</div>
          <a-grid :cols="24" :col-gap="24">
            <a-grid-item :span="24">
              <a-form-item field="openai_api_key" label="API KEY" required>
                <a-input-password 
                  v-model="form.openai_api_key" 
                  placeholder="sk-uovxekbxvyvmddkormbfavimspfvcwmbhnkopzdkppozdugf" 
                  class="custom-input"
                />
              </a-form-item>
            </a-grid-item>
            <a-grid-item :span="12">
              <a-form-item field="openai_base_url" label="BASE URL">
                <a-input 
                  v-model="form.openai_base_url" 
                  placeholder="https://api.siliconflow.cn/v1" 
                  class="custom-input"
                />
              </a-form-item>
            </a-grid-item>
            <a-grid-item :span="12">
              <a-form-item field="llm_model" label="LLM MODEL">
                <a-input 
                  v-model="form.llm_model" 
                  placeholder="zai-org/GLM-4.6" 
                  class="custom-input"
                />
              </a-form-item>
            </a-grid-item>
            <a-grid-item :span="24">
              <a-form-item field="backend_base_url" label="BACKEND URL">
                <a-input 
                  v-model="form.backend_base_url" 
                  placeholder="http://localhost:18000" 
                  class="custom-input"
                />
              </a-form-item>
            </a-grid-item>
          </a-grid>
        </div>

        <a-divider class="form-divider" />

        <div class="form-section">
          <div class="section-title">2. OCR Engine</div>
          <a-grid :cols="24" :col-gap="24">
            <a-grid-item :span="24">
              <a-form-item field="ocr_engine" label="OCR ENGINE">
                <a-select v-model="form.ocr_engine" class="custom-select">
                  <a-option value="vl">VL Model (Remote)</a-option>
                  <a-option value="tesseract">Tesseract (Local)</a-option>
                </a-select>
              </a-form-item>
            </a-grid-item>
          </a-grid>
        </div>

        <a-divider v-if="form.ocr_engine === 'vl'" class="form-divider" />

        <div v-if="form.ocr_engine === 'vl'" class="form-section">
          <div class="section-title">3. API Access (VL Model)</div>
          <a-grid :cols="24" :col-gap="24">
            <a-grid-item :span="24">
              <a-form-item field="vl_api_key" label="VL API KEY">
                <a-input-password 
                  v-model="form.vl_api_key" 
                  placeholder="Leave empty to use LLM API KEY" 
                  class="custom-input"
                />
              </a-form-item>
            </a-grid-item>
            <a-grid-item :span="12">
              <a-form-item field="vl_base_url" label="VL BASE URL">
                <a-input 
                  v-model="form.vl_base_url" 
                  placeholder="https://api.siliconflow.cn/v1" 
                  class="custom-input"
                />
              </a-form-item>
            </a-grid-item>
            <a-grid-item :span="12">
              <a-form-item field="vl_model" label="VL MODEL">
                <a-input 
                  v-model="form.vl_model" 
                  placeholder="Pro/Qwen/Qwen2-VL-7B-Instruct" 
                  class="custom-input"
                />
              </a-form-item>
            </a-grid-item>
          </a-grid>
        </div>

        <a-divider class="form-divider" />
        
        <div class="form-section">
          <div class="section-title">4. Processing Parameters</div>
          <a-grid :cols="24" :col-gap="24" :row-gap="16">
            <a-grid-item :span="12">
              <a-form-item field="model_size" label="WHISPER SIZE">
                <a-select v-model="form.model_size" class="custom-select">
                  <a-option value="small">small</a-option>
                  <a-option value="medium">medium</a-option>
                  <a-option value="large-v3">large-v3</a-option>
                </a-select>
              </a-form-item>
            </a-grid-item>
            <a-grid-item :span="12">
              <a-form-item field="capture_offset" label="CAPTURE OFFSET (S)">
                <a-input-number 
                  v-model="form.capture_offset" 
                  :min="0" 
                  :precision="1" 
                  class="custom-input"
                />
              </a-form-item>
            </a-grid-item>
            <a-grid-item :span="12">
              <a-form-item field="device" label="DEVICE">
                <a-select v-model="form.device" class="custom-select">
                  <a-option value="cuda">cuda (GPU)</a-option>
                  <a-option value="cpu">cpu (Slow)</a-option>
                </a-select>
              </a-form-item>
            </a-grid-item>
            <a-grid-item :span="12">
              <a-form-item field="compute_type" label="COMPUTE TYPE">
                <a-select v-model="form.compute_type" class="custom-select">
                  <a-option value="float16">float16</a-option>
                  <a-option value="int8">int8</a-option>
                </a-select>
              </a-form-item>
            </a-grid-item>
          </a-grid>
        </div>

        <div class="form-footer">
          <a-button type="primary" html-type="submit" size="large" class="save-btn">
            Save Configuration
          </a-button>
        </div>
      </a-form>
    </a-card>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
import { useConfigStore } from '../stores/config'
import { Message } from '@arco-design/web-vue'

const configStore = useConfigStore()

const form = reactive({
  backend_base_url: configStore.backend_base_url,
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

const handleSave = () => {
  configStore.updateConfig(form)
  Message.success({
    content: 'Configuration saved successfully',
    closable: true
  })
}
</script>

<style scoped>
.settings-page {
  max-width: 900px;
  margin: 0 auto;
  padding-bottom: 40px;
}

.main-card {
  background-color: var(--surface-0);
  border-radius: 32px;
  box-shadow: var(--shadow-1);
  overflow: hidden;
  padding: 40px;
}

.card-header-row {
  margin-bottom: 40px;
}

.card-title {
  font-size: 24px;
  font-weight: 800;
  color: var(--card-text);
}

.form-section {
  margin-bottom: 30px;
}

.section-title {
  font-size: 14px;
  font-weight: 800;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 24px;
}

:deep(.arco-form-item-label) {
  font-size: 13px;
  font-weight: 700;
  color: var(--card-text-muted);
  margin-bottom: 8px;
}

.custom-input :deep(.arco-input-wrapper),
.custom-select :deep(.arco-select-view-single),
.custom-input :deep(.arco-input-number) {
  background-color: var(--input-bg);
  border: 1px solid var(--input-border);
  border-radius: 16px;
  height: 48px;
  transition: all 0.2s;
}

.custom-input :deep(.arco-input-wrapper:hover),
.custom-select :deep(.arco-select-view-single:hover) {
  background-color: var(--input-hover-bg);
  border-color: var(--input-hover-border);
}

.custom-input :deep(.arco-input-wrapper.arco-input-focus),
.custom-select :deep(.arco-select-view-single.arco-select-view-focus) {
  background-color: var(--input-focus-bg);
  border-color: var(--primary-color);
  box-shadow: var(--input-focus-shadow);
}

.form-divider {
  margin: 40px 0;
  border-bottom-style: dashed;
}

.form-footer {
  margin-top: 50px;
}

.save-btn {
  height: 56px;
  padding: 0 40px;
  border-radius: 18px;
  font-size: 16px;
  font-weight: 800;
  background-color: var(--primary-color);
  border: none;
  width: 100%;
  box-shadow: var(--shadow-1);
}

.save-btn:hover {
  background-color: var(--primary-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-1);
}
</style>
