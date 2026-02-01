<template>
  <div class="uv-checkbox-wrapper">
    <input 
      type="checkbox" 
      :id="id" 
      class="uv-checkbox" 
      :checked="modelValue"
      @change="$emit('update:modelValue', $event.target.checked)"
    />
    <label :for="id" class="uv-checkbox-label">
      <div class="uv-checkbox-icon">
        <svg viewBox="0 0 24 24" class="uv-checkmark">
          <path d="M4.1,12.7 9,17.6 20.3,6.3" fill="none"></path>
        </svg>
      </div>
      <span v-if="label || $slots.default" class="uv-checkbox-text">
        <slot>{{ label }}</slot>
      </span>
    </label>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  label: {
    type: String,
    default: ''
  },
  uid: {
    type: String,
    default: () => 'uv-checkbox-' + Math.random().toString(36).substr(2, 9)
  }
})

defineEmits(['update:modelValue'])

const id = computed(() => props.uid)
</script>

<style scoped>
.uv-checkbox-wrapper { 
  display: inline-block; 
} 

.uv-checkbox { 
  display: none; 
} 

.uv-checkbox-label { 
  display: flex; 
  align-items: center; 
  cursor: pointer; 
} 

.uv-checkbox-icon { 
  position: relative; 
  width: 2em; 
  height: 2em; 
  border: 2px solid #ccc; 
  border-radius: 30% 70% 70% 30% / 30% 30% 70% 70%; 
  transition: border-color 0.3s ease, border-radius 0.3s ease; 
} 

.uv-checkmark { 
  position: absolute; 
  top: 0.1em; 
  left: 0.1em; 
  width: 1.6em; 
  height: 1.6em; 
  fill: none; 
  stroke: #fff; 
  stroke-width: 2; 
  stroke-linecap: round; 
  stroke-linejoin: round; 
  stroke-dasharray: 24; 
  stroke-dashoffset: 24; 
  transition: stroke-dashoffset 0.5s cubic-bezier(0.45, 0.05, 0.55, 0.95); 
} 

.uv-checkbox-text { 
  margin-left: 0.5em; 
  transition: color 0.3s ease; 
} 

.uv-checkbox:checked + .uv-checkbox-label .uv-checkbox-icon { 
  border-color: #6c5ce7; 
  border-radius: 70% 30% 30% 70% / 70% 70% 30% 30%; 
  background-color: #6c5ce7; 
} 

.uv-checkbox:checked + .uv-checkbox-label .uv-checkmark { 
  stroke-dashoffset: 0; 
} 

.uv-checkbox:checked + .uv-checkbox-label .uv-checkbox-text { 
  color: #6c5ce7; 
} 
</style>