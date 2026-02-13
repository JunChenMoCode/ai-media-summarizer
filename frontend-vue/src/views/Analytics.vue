<template>
  <div class="analytics-page">
    <div class="page-header">
      <div class="title">数据统计</div>
      <div class="subtitle">标签云分析</div>
    </div>
    
    <div class="chart-container">
      <div ref="chartRef" class="chart"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import * as echarts from 'echarts'
import 'echarts-wordcloud'
import { useConfigStore } from '../stores/config'
import { Message } from '@arco-design/web-vue'

const configStore = useConfigStore()
const backendBaseUrl = computed(() => (configStore.backend_base_url || '').replace(/\/+$/, ''))
const chartRef = ref(null)
let chartInstance = null

const fetchTags = async () => {
  try {
    const res = await fetch(`${backendBaseUrl.value}/analysis/tags`)
    if (!res.ok) throw new Error('Fetch tags failed')
    const data = await res.json()
    return data.tags || []
  } catch (e) {
    Message.error('获取标签数据失败')
    return []
  }
}

const initChart = async () => {
  if (!chartRef.value) return
  
  const tags = await fetchTags()
  if (!tags.length) {
    // Mock data for demo if empty
    // tags.push({ name: 'No Data', value: 100 })
  }

  chartInstance = echarts.init(chartRef.value)
  
  const option = {
    backgroundColor: '#000000',
    tooltip: {
      show: true
    },
    series: [{
      type: 'wordCloud',
      shape: 'square', // circle, cardioid, diamond, triangle-forward, triangle, star
      left: 'center',
      top: 'center',
      width: '100%',
      height: '100%',
      right: null,
      bottom: null,
      sizeRange: [12, 100], // Font size range
      rotationRange: [-90, 90], // Rotation range
      rotationStep: 90, // Random rotation 0, 90, -90
      gridSize: 8,
      drawOutOfBound: false,
      layoutAnimation: true,
      textStyle: {
        fontFamily: 'Impact, "Arial Black", sans-serif',
        fontWeight: 'bold',
        color: function () {
          // Palette: White, Grey, Beige/Orange
          const colors = [
            '#ffffff', '#ffffff', '#ffffff', // More white
            '#cccccc', '#999999', '#666666', // Greys
            '#e1c095', '#d8a47f', '#c48a69'  // Beige/Orange
          ]
          return colors[Math.floor(Math.random() * colors.length)]
        }
      },
      emphasis: {
        focus: 'self',
        textStyle: {
          shadowBlur: 10,
          shadowColor: '#333'
        }
      },
      data: tags
    }]
  }
  
  chartInstance.setOption(option)
}

const handleResize = () => {
  chartInstance?.resize()
}

onMounted(() => {
  initChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
})
</script>

<style scoped>
.analytics-page {
  padding: 24px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-1);
}

.page-header {
  margin-bottom: 24px;
}

.title {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-text-1);
  margin-bottom: 4px;
}

.subtitle {
  font-size: 14px;
  color: var(--color-text-3);
}

.chart-container {
  flex: 1;
  background: #000;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 10px rgba(0,0,0,0.1);
  min-height: 400px;
}

.chart {
  width: 100%;
  height: 100%;
}
</style>