<template>
  <div class="floating-toggle-wrapper">
    <label class="toggle" :class="{ checked: modelValue }">
      <input 
        type="checkbox" 
        class="input" 
        :checked="modelValue" 
        @change="handleChange" 
      />
      <!-- Unchecked State: Preview Icon (Eye) -->
      <div class="icon icon--preview">
        <svg 
          xmlns="http://www.w3.org/2000/svg" 
          viewBox="0 0 24 24" 
          fill="none" 
          stroke="currentColor" 
          stroke-width="2" 
          stroke-linecap="round" 
          stroke-linejoin="round"
          width="28" 
          height="28" 
        >
          <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"></path>
          <circle cx="12" cy="12" r="3"></circle>
        </svg>
      </div>
   
      <!-- Checked State: Edit Icon (Pen) -->
      <div class="icon icon--edit">
        <svg 
          xmlns="http://www.w3.org/2000/svg" 
          viewBox="0 0 24 24" 
          fill="none" 
          stroke="currentColor" 
          stroke-width="2" 
          stroke-linecap="round" 
          stroke-linejoin="round"
          width="24" 
          height="24" 
        >
          <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"></path>
          <path d="m15 5 4 4"></path>
        </svg>
      </div>
    </label>
  </div>
</template>

<script setup>
import { defineProps, defineEmits } from 'vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'change'])

const handleChange = (e) => {
  const val = e.target.checked
  emit('update:modelValue', val)
  emit('change', val)
}
</script>

<style scoped>
.floating-toggle-wrapper {
  position: absolute;
  top: 50%;
  right: 16px;
  transform: translateY(-50%);
  z-index: 100;
  /* Optional: Add a subtle drop shadow or background if needed to separate from content */
}

.toggle {
  background-color: var(--color-bg-2);
  width: 56px;
  height: 56px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  cursor: pointer;
  box-shadow: 0 0 50px 20px rgba(0, 0, 0, 0.1);
  line-height: 1;
  border: 1px solid var(--color-border-2);
  transition: all 0.3s ease;
}

.toggle:hover {
  box-shadow: 0 0 50px 20px rgba(var(--primary-6), 0.15);
  border-color: rgba(var(--primary-6), 0.5);
}

.input {
  display: none;
}

.icon {
  grid-column: 1 / 1;
  grid-row: 1 / 1;
  transition: transform 500ms;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-1);
}

.icon--preview {
  transition-delay: 200ms;
}

.icon--edit {
  transform: scale(0);
  color: rgb(var(--primary-6));
}

/* Checked State Logic */
.input:checked + .icon--preview {
  transform: rotate(360deg) scale(0);
}

.input:checked ~ .icon--edit {
  transition-delay: 200ms;
  transform: scale(1) rotate(360deg);
}
</style>
