<template>
  <div class="dashboard-landing">
    <!-- Background Elements -->
    <div class="bg-orb orb-1"></div>
    <div class="bg-orb orb-2"></div>
    <div class="grid-overlay"></div>

    <!-- Hero Section -->
    <div class="hero-section">
      <div class="hero-content">
        <h1 class="hero-title">
          <span class="gradient-text">AI 智能总结</span>
          <br />
          <span class="subtitle-text">重塑知识获取方式</span>
        </h1>
        <p class="hero-desc">
          基于大语言模型的全能型分析平台，为您提供深度的音视频与文档理解能力。
          <br />一键提取核心观点，生成思维导图，让学习与办公更高效。
        </p>
      </div>
    </div>

    <!-- Features/Entry Section -->
    <div class="features-container">
      <!-- Video Summary Card -->
      <div class="feature-card-wrapper" @click="navigateTo('AiVideoSummary')">
        <div class="feature-card video-theme">
          <div class="card-inner">
            <div class="card-icon">
              <icon-video class="w-12 h-12" />
            </div>
            <h3 class="card-title">音视频总结</h3>
            <p class="card-desc">
              支持 YouTube、Bilibili 及本地音视频。
              智能生成时间轴、思维导图与详细摘要。
            </p>
            <div class="card-action">
              <span>立即体验</span>
              <icon-arrow-right class="arrow-icon" />
            </div>
          </div>
          <div class="card-glow"></div>
        </div>
      </div>

      <!-- Document Summary Card -->
      <div class="feature-card-wrapper" @click="navigateTo('AiFileSummary')">
        <div class="feature-card doc-theme">
          <div class="card-inner">
            <div class="card-icon">
              <icon-file-text :size="48" />
            </div>
            <h3 class="card-title">文档总结</h3>
            <p class="card-desc">
              支持 PDF、Word、PPT、Markdown 等多格式。
              深度解析文档内容，快速提炼关键信息。
            </p>
            <div class="card-action">
              <span>立即体验</span>
              <icon-arrow-right class="arrow-icon" />
            </div>
          </div>
          <div class="card-glow"></div>
        </div>
      </div>
    </div>

    <!-- Footer Decoration -->
    <div class="footer-decoration">
      <div class="tech-stack">
        <span>Powered by LLM</span>
        <span class="dot">·</span>
        <span>Whisper</span>
        <span class="dot">·</span>
        <span>FastAPI</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { 
  ListVideo as IconVideo, 
  FileText as IconFileText, 
  ArrowRight as IconArrowRight 
} from 'lucide-vue-next'

const router = useRouter()

const navigateTo = (routeName) => {
  router.push({ name: routeName })
}
</script>

<style scoped>
/* Global Layout */
.dashboard-landing {
  min-height: 100vh;
  width: 100%;
  background-color: #0f0b1e; /* Deep dark purple/black */
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  padding: 40px;
  box-sizing: border-box;
}

/* Background Effects */
.bg-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(100px);
  z-index: 0;
  opacity: 0.4;
  animation: floatOrb 10s infinite alternate ease-in-out;
}

.orb-1 {
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, #7000ff 0%, transparent 70%);
  top: -20%;
  left: -10%;
}

.orb-2 {
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, #ff0055 0%, transparent 70%);
  bottom: -10%;
  right: -5%;
  animation-delay: -5s;
}

.grid-overlay {
  position: absolute;
  inset: 0;
  background-image: 
    linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
  background-size: 50px 50px;
  z-index: 0;
  pointer-events: none;
  mask-image: radial-gradient(circle at center, black 40%, transparent 100%);
}

@keyframes floatOrb {
  0% { transform: translate(0, 0); }
  100% { transform: translate(30px, 50px); }
}

/* Hero Section */
.hero-section {
  position: relative;
  z-index: 2;
  text-align: center;
  margin-bottom: 60px;
  max-width: 800px;
}

.hero-title {
  font-size: 4rem;
  line-height: 1.1;
  font-weight: 800;
  margin-bottom: 24px;
  letter-spacing: -0.02em;
}

.gradient-text {
  background: linear-gradient(135deg, #fff 0%, #bca1ff 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  filter: drop-shadow(0 0 30px rgba(120, 0, 255, 0.3));
}

.subtitle-text {
  font-size: 2.5rem;
  color: rgba(255, 255, 255, 0.9);
  font-weight: 600;
}

.hero-desc {
  font-size: 1.125rem;
  color: rgba(255, 255, 255, 0.6);
  line-height: 1.6;
  max-width: 600px;
  margin: 0 auto;
}

/* Features Container */
.features-container {
  position: relative;
  z-index: 2;
  display: flex;
  gap: 40px;
  justify-content: center;
  flex-wrap: wrap;
  width: 100%;
  max-width: 1000px;
}

.feature-card-wrapper {
  flex: 1;
  min-width: 300px;
  height: 360px;
  perspective: 1000px;
  cursor: pointer;
}

.feature-card {
  width: 100%;
  height: 100%;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 24px;
  position: relative;
  transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  overflow: hidden;
  backdrop-filter: blur(10px);
  transform-style: preserve-3d;
}

.card-inner {
  padding: 40px;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  position: relative;
  z-index: 2;
  box-sizing: border-box;
}

/* Card Themes */
.video-theme:hover {
  background: linear-gradient(145deg, rgba(112, 0, 255, 0.15), rgba(0, 0, 0, 0.4));
  border-color: rgba(112, 0, 255, 0.5);
  box-shadow: 0 20px 50px rgba(112, 0, 255, 0.3);
  transform: translateY(-10px) rotateX(5deg);
}

.doc-theme:hover {
  background: linear-gradient(145deg, rgba(255, 0, 85, 0.15), rgba(0, 0, 0, 0.4));
  border-color: rgba(255, 0, 85, 0.5);
  box-shadow: 0 20px 50px rgba(255, 0, 85, 0.3);
  transform: translateY(-10px) rotateX(5deg);
}

.card-icon {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24px;
  transition: transform 0.4s ease;
}

.video-theme .card-icon {
  background: rgba(112, 0, 255, 0.2);
  color: #bca1ff;
  box-shadow: 0 0 20px rgba(112, 0, 255, 0.2);
}

.doc-theme .card-icon {
  background: rgba(255, 0, 85, 0.2);
  color: #ff8fa3;
  box-shadow: 0 0 20px rgba(255, 0, 85, 0.2);
}

.feature-card:hover .card-icon {
  transform: scale(1.1) translateZ(20px);
}

.card-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: #fff;
  margin: 0 0 12px 0;
  transition: transform 0.4s ease;
}

.card-desc {
  font-size: 0.95rem;
  color: rgba(255, 255, 255, 0.6);
  line-height: 1.5;
  margin: 0;
  flex-grow: 1;
}

.card-action {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 0.9rem;
  margin-top: 20px;
  opacity: 0.8;
  transition: all 0.3s ease;
}

.video-theme .card-action { color: #bca1ff; }
.doc-theme .card-action { color: #ff8fa3; }

.feature-card:hover .card-action {
  opacity: 1;
  transform: translateX(5px);
}

.arrow-icon {
  width: 16px;
  height: 16px;
}

/* Card Glow Effect */
.card-glow {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: radial-gradient(circle at 50% 0%, rgba(255, 255, 255, 0.1), transparent 70%);
  opacity: 0;
  transition: opacity 0.4s ease;
  z-index: 1;
  pointer-events: none;
}

.feature-card:hover .card-glow {
  opacity: 1;
}

/* Footer Decoration */
.footer-decoration {
  position: absolute;
  bottom: 20px;
  left: 0;
  right: 0;
  text-align: center;
  z-index: 2;
  opacity: 0.3;
}

.tech-stack {
  font-size: 0.8rem;
  color: #fff;
  letter-spacing: 2px;
  text-transform: uppercase;
}

.dot {
  margin: 0 8px;
  font-weight: bold;
}

/* Responsive */
@media (max-width: 768px) {
  .hero-title {
    font-size: 2.5rem;
  }
  
  .subtitle-text {
    font-size: 1.5rem;
  }

  .features-container {
    flex-direction: column;
    align-items: center;
  }

  .feature-card-wrapper {
    width: 100%;
    height: 300px;
  }
}
</style>