<template>
  <div ref="rootRef" :class="rootClass" @pointerdown="handlePointerDown">
    <canvas ref="canvasRef" class="apv-canvas"></canvas>
    <div v-if="props.variant === 'radial'" class="apv-inner">
      <div class="apv-semicircle">
        <div>
          <div>
            <div>
              <div>
                <div>
                  <div>
                    <div>
                      <div>
                        <div></div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-if="showHint && statusText" class="apv-hint">{{ statusText }}</div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps({
  mediaEl: { type: Object, default: null },
  active: { type: Boolean, default: true },
  barDensity: { type: Number, default: 12 },
  variant: { type: String, default: 'linear' },
  layout: { type: String, default: 'fill' },
  interactive: { type: Boolean, default: true },
  showHint: { type: Boolean, default: true },
})

const rootRef = ref(null)
const canvasRef = ref(null)

const rootClass = computed(() => [
  'apv-root',
  props.variant === 'radial' ? 'apv-root--radial' : '',
  props.layout === 'inline' ? 'apv-root--inline' : 'apv-root--fill',
  props.interactive ? '' : 'apv-root--passthrough',
])

const showHint = computed(() => props.showHint && props.interactive)

const mediaPaused = computed(() => {
  const el = props.mediaEl
  return el ? !!el.paused : true
})

let resizeObserver = null
let rafId = 0
let canvasCtx = null

let audioCtx = null
let analyser = null
let sourceNode = null
let freq = null
let timeData = null
let boundEl = null

let width = 0
let height = 0
let dpr = 1

const audioError = ref('')
const noSignal = ref(false)
let noSignalSince = 0

const statusText = computed(() => {
  if (!props.active) return ''
  if (audioError.value) return audioError.value
  if (!boundEl) return ''
  if (mediaPaused.value) return '点击播放以激活特效'
  if (noSignal.value) return '当前音源无法读取频谱（可能缺少 CORS），已启用模拟跳动'
  return ''
})

const clamp = (v, min, max) => Math.max(min, Math.min(max, v))

const rand = (min, max) => min + Math.random() * (max - min)

const ensureCanvas = () => {
  const canvas = canvasRef.value
  const root = rootRef.value
  if (!canvas || !root) return

  const rect = root.getBoundingClientRect()
  const nextW = Math.max(1, Math.floor(rect.width))
  const nextH = Math.max(1, Math.floor(rect.height))
  const nextDpr = clamp(window.devicePixelRatio || 1, 1, 2)

  if (nextW === width && nextH === height && nextDpr === dpr && canvasCtx) return

  width = nextW
  height = nextH
  dpr = nextDpr

  canvas.width = Math.floor(width * dpr)
  canvas.height = Math.floor(height * dpr)
  canvas.style.width = `${width}px`
  canvas.style.height = `${height}px`

  canvasCtx = canvas.getContext('2d', { alpha: true, desynchronized: true })
  if (canvasCtx) {
    canvasCtx.setTransform(dpr, 0, 0, dpr, 0, 0)
  }

  initParticles()
}

const initParticles = () => {}

const teardownAudioGraph = () => {
  if (boundEl) {
    boundEl.removeEventListener('play', handleMediaPlay)
    boundEl.removeEventListener('pause', handleMediaPause)
    boundEl.removeEventListener('ended', handleMediaPause)
  }
  boundEl = null

  try {
    if (sourceNode) sourceNode.disconnect()
  } catch (e) {}
  try {
    if (analyser) analyser.disconnect()
  } catch (e) {}

  sourceNode = null
  analyser = null
  freq = null
  timeData = null
  audioError.value = ''
  noSignal.value = false
  noSignalSince = 0

  try {
    if (audioCtx) audioCtx.close()
  } catch (e) {}
  audioCtx = null
}

const ensureAudioGraph = async () => {
  const el = props.mediaEl
  if (!el) return
  if (audioCtx && analyser && sourceNode) return

  const Ctx = window.AudioContext || window.webkitAudioContext
  if (!Ctx) return

  try {
    const ctx = new Ctx()
    const a = ctx.createAnalyser()
    a.fftSize = 2048
    a.smoothingTimeConstant = 0.78

    const src = ctx.createMediaElementSource(el)
    src.connect(a)
    src.connect(ctx.destination)

    audioCtx = ctx
    analyser = a
    sourceNode = src
    freq = new Uint8Array(a.frequencyBinCount)
    timeData = new Uint8Array(a.fftSize)
    audioError.value = ''
    initParticles()

    if (audioCtx.state === 'suspended') {
      try {
        await audioCtx.resume()
      } catch (e) {}
    }
  } catch (e) {
    const msg = String(e?.message || e || '')
    if (msg) {
      audioError.value = msg.includes('cross') || msg.includes('CORS') ? '音频源跨域受限，无法读取频谱' : msg
    } else {
      audioError.value = '音频可视化初始化失败'
    }
    teardownAudioGraph()
  }
}

const handlePointerDown = async () => {
  if (!props.interactive) return
  if (!props.active) return
  await ensureAudioGraph()
  try {
    if (audioCtx && audioCtx.state === 'suspended') await audioCtx.resume()
  } catch (e) {}
}

const unlock = async () => {
  if (!props.active) return
  await ensureAudioGraph()
  try {
    if (audioCtx && audioCtx.state === 'suspended') await audioCtx.resume()
  } catch (e) {}
}

const handleMediaPlay = async () => {
  if (!props.active) return
  await ensureAudioGraph()
  try {
    if (audioCtx && audioCtx.state === 'suspended') await audioCtx.resume()
  } catch (e) {}
}

const handleMediaPause = async () => {
  try {
    if (audioCtx && audioCtx.state === 'running') await audioCtx.suspend()
  } catch (e) {}
}

const attachToMediaEl = (el) => {
  if (!el) return
  if (boundEl === el) return
  teardownAudioGraph()
  boundEl = el
  boundEl.addEventListener('play', handleMediaPlay, { passive: true })
  boundEl.addEventListener('pause', handleMediaPause, { passive: true })
  boundEl.addEventListener('ended', handleMediaPause, { passive: true })
  if (props.active && !boundEl.paused) {
    handleMediaPlay()
  }
}

let energySmoothed = 0

const computeEnergy = () => {
  const el = boundEl
  if (!el) return 0
  if (!analyser || !freq || !timeData || !audioCtx || audioCtx.state !== 'running') return 0

  analyser.getByteFrequencyData(freq)
  analyser.getByteTimeDomainData(timeData)

  let maxBin = 0
  for (let i = 0; i < 96 && i < freq.length; i++) {
    if (freq[i] > maxBin) maxBin = freq[i]
  }

  const now = performance.now()
  if (!el.paused && maxBin === 0) {
    if (!noSignalSince) noSignalSince = now
    if (now - noSignalSince > 900) noSignal.value = true
  } else {
    noSignalSince = 0
    noSignal.value = false
  }

  if (noSignal.value) return 0

  let sumSq = 0
  for (let i = 0; i < timeData.length; i++) {
    const v = (timeData[i] - 128) / 128
    sumSq += v * v
  }
  const rms = Math.sqrt(sumSq / timeData.length)

  let low = 0
  let mid = 0
  let lowN = 0
  let midN = 0
  for (let i = 2; i < freq.length && i < 36; i++) {
    low += freq[i]
    lowN++
  }
  for (let i = 36; i < freq.length && i < 120; i++) {
    mid += freq[i]
    midN++
  }
  const lowE = lowN ? (low / lowN) / 255 : 0
  const midE = midN ? (mid / midN) / 255 : 0

  return clamp(rms * 1.4 + lowE * 0.9 + midE * 0.35, 0, 1)
}

const drawFrame = () => {
  if (!props.active) {
    rafId = requestAnimationFrame(drawFrame)
    return
  }

  ensureCanvas()
  const ctx = canvasCtx
  if (!ctx) {
    rafId = requestAnimationFrame(drawFrame)
    return
  }

  const rawEnergy = computeEnergy()
  if (noSignal.value && boundEl && !boundEl.paused) {
    const t = performance.now() / 1000
    const synth = 0.22 + 0.18 * Math.sin(t * 2.0) + 0.10 * Math.sin(t * 6.3)
    energySmoothed = energySmoothed * 0.90 + clamp(synth, 0, 1) * 0.10
  } else {
    energySmoothed = energySmoothed * 0.86 + rawEnergy * 0.14
  }
  const energy = clamp(energySmoothed, 0, 1)

  ctx.globalCompositeOperation = 'source-over'
  ctx.clearRect(0, 0, width, height)

  if (props.variant === 'radial') {
    const cx = width * 0.5
    const cy = height * 0.5
    const minSide = Math.min(width, height)
    const innerR = minSide * 0.22
    const maxDelta = minSide * 0.16

    const barCount = clamp(Math.floor(minSide / Math.max(6, props.barDensity)), 72, 192)
    const lineW = clamp((minSide / barCount) * 0.9, 1.5, 5.5)

    ctx.lineCap = 'round'
    ctx.lineWidth = lineW
    ctx.globalCompositeOperation = 'lighter'

    const ring = ctx.createRadialGradient(cx, cy, innerR * 0.45, cx, cy, innerR + maxDelta * 1.05)
    ring.addColorStop(0, 'rgba(76, 29, 149, 0.06)')
    ring.addColorStop(0.6, 'rgba(124, 58, 237, 0.10)')
    ring.addColorStop(1, 'rgba(236, 72, 153, 0.06)')
    ctx.fillStyle = ring
    ctx.beginPath()
    ctx.arc(cx, cy, innerR + maxDelta * 1.05, 0, Math.PI * 2)
    ctx.fill()

    for (let i = 0; i < barCount; i++) {
      const t = barCount <= 1 ? 0 : i / barCount
      const ang = t * Math.PI * 2 - Math.PI * 0.5

      const bin = freq ? Math.floor(t * Math.min(freq.length - 1, 240)) : 0
      const ampRaw = !noSignal.value && freq ? (freq[clamp(bin, 0, freq.length - 1)] / 255) : clamp(energy * (0.45 + 0.55 * Math.sin((i * 0.18) + performance.now() / 190)), 0, 1)
      const amp = clamp(Math.pow(ampRaw, 1.45) * (0.35 + energy * 0.95), 0, 1)

      const r0 = innerR
      const r1 = innerR + amp * maxDelta

      const x0 = cx + Math.cos(ang) * r0
      const y0 = cy + Math.sin(ang) * r0
      const x1 = cx + Math.cos(ang) * r1
      const y1 = cy + Math.sin(ang) * r1

      const hue = 265 + 20 * Math.sin(ang * 2)
      ctx.strokeStyle = `hsla(${hue}, 88%, 64%, ${0.14 + amp * 0.42})`
      ctx.beginPath()
      ctx.moveTo(x0, y0)
      ctx.lineTo(x1, y1)
      ctx.stroke()

      if (amp > 0.58) {
        ctx.lineWidth = lineW * 2.2
        ctx.strokeStyle = `rgba(236, 72, 153, ${0.05 + amp * 0.12})`
        ctx.beginPath()
        ctx.moveTo(x0, y0)
        ctx.lineTo(x1, y1)
        ctx.stroke()
        ctx.lineWidth = lineW
      }
    }
  } else {
    const baseY = height * 0.60
    const maxH = height * 0.42
    const barCount = clamp(Math.floor(width / Math.max(8, props.barDensity)), 52, 140)
    const barW = width / barCount
    const lineW = clamp(barW * 0.52, 2, 8)

    ctx.lineCap = 'round'
    ctx.lineWidth = lineW
    ctx.globalCompositeOperation = 'lighter'

    const g = ctx.createLinearGradient(0, baseY - maxH, 0, baseY)
    g.addColorStop(0, 'rgba(168, 85, 247, 0.70)')
    g.addColorStop(0.55, 'rgba(124, 58, 237, 0.56)')
    g.addColorStop(1, 'rgba(76, 29, 149, 0.30)')

    const gl = ctx.createLinearGradient(0, baseY - maxH, 0, baseY)
    gl.addColorStop(0, 'rgba(236, 72, 153, 0.18)')
    gl.addColorStop(1, 'rgba(124, 58, 237, 0.10)')

    for (let i = 0; i < barCount; i++) {
      const t = barCount <= 1 ? 0 : i / (barCount - 1)
      const bin = freq ? Math.floor(t * Math.min(freq.length - 1, 220)) : 0
      const ampRaw = !noSignal.value && freq ? (freq[clamp(bin, 0, freq.length - 1)] / 255) : clamp(energy * (0.45 + 0.55 * Math.sin((i * 0.22) + performance.now() / 170)), 0, 1)
      const amp = clamp(Math.pow(ampRaw, 1.55) * (0.40 + energy * 0.95), 0, 1)

      const h = amp * maxH
      const x = i * barW + barW * 0.5
      const y0 = baseY
      const y1 = baseY - h

      ctx.strokeStyle = g
      ctx.beginPath()
      ctx.moveTo(x, y0)
      ctx.lineTo(x, y1)
      ctx.stroke()

      if (amp > 0.55) {
        ctx.strokeStyle = gl
        ctx.lineWidth = lineW * 2.2
        ctx.beginPath()
        ctx.moveTo(x, y0)
        ctx.lineTo(x, y1)
        ctx.stroke()
        ctx.lineWidth = lineW
      }
    }
  }

  ctx.globalCompositeOperation = 'source-over'
  rafId = requestAnimationFrame(drawFrame)
}

watch(
  () => props.mediaEl,
  (el) => {
    if (el) attachToMediaEl(el)
  },
  { immediate: true },
)

watch(
  () => props.active,
  (v) => {
    if (!v) {
      teardownAudioGraph()
      return
    }
    if (props.mediaEl) attachToMediaEl(props.mediaEl)
  },
)

onMounted(() => {
  ensureCanvas()
  const root = rootRef.value
  if (root && 'ResizeObserver' in window) {
    resizeObserver = new ResizeObserver(() => ensureCanvas())
    resizeObserver.observe(root)
  }
  rafId = requestAnimationFrame(drawFrame)
})

onUnmounted(() => {
  if (resizeObserver) {
    try {
      resizeObserver.disconnect()
    } catch (e) {}
  }
  resizeObserver = null
  if (rafId) cancelAnimationFrame(rafId)
  rafId = 0
  teardownAudioGraph()
})

defineExpose({ unlock })
</script>

<style scoped>
.apv-root {
  border-radius: var(--border-radius-large);
  overflow: hidden;
  user-select: none;
}

.apv-root--fill {
  position: absolute;
  inset: 0;
}

.apv-root--inline {
  position: relative;
  width: 100%;
  height: 100%;
}

.apv-root--passthrough {
  pointer-events: none;
}

.apv-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
}

.apv-inner {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 40%;
  height: 40%;
  border-radius: var(--border-radius-circle);
  overflow: hidden;
  z-index: 1;
  pointer-events: none;
}

.apv-semicircle,
.apv-semicircle div {
  width: 100%;
  height: 100%;
  animation: 6s apv-rotate141 infinite linear;
  background-repeat: no-repeat;
  border-radius: 50%;
  position: relative;
  overflow: hidden;
}

.apv-semicircle div {
  position: absolute;
  top: 5%;
  left: 5%;
  width: 90%;
  height: 90%;
}

.apv-semicircle:before,
.apv-semicircle div:before {
  content: '';
  width: 100%;
  height: 50%;
  display: block;
  background: radial-gradient(
    transparent,
    transparent 65%,
    color-mix(in srgb, var(--color-text-1) 32%, transparent) 65%,
    color-mix(in srgb, var(--color-text-1) 32%, transparent)
  );
  background-size: 100% 200%;
}

.apv-root--radial .apv-inner {
  filter: blur(0.2px);
  opacity: 0.95;
}

@keyframes apv-rotate141 {
  to {
    transform: rotate(360deg);
  }
}

.apv-hint {
  position: absolute;
  left: 16px;
  top: 16px;
  z-index: 2;
  padding: 8px 10px;
  border-radius: var(--border-radius-large);
  background: var(--color-bg-5);
  background: color-mix(in srgb, var(--color-bg-5) 62%, transparent);
  color: var(--color-text-1);
  border: 1px solid var(--color-border-2);
  font-size: 12px;
  letter-spacing: 0.2px;
  backdrop-filter: blur(8px);
}
</style>
