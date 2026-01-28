# High-Performance Video Summary (极致性能视频总结)

这是一个基于“内容驱动”逻辑的高性能视频总结工具。它通过直接提取音频流、优化 ASR 参数、AI 逻辑分段以及并行截图，实现了极快的处理速度。

## 核心优化点

1.  **音频提取 (0 编码耗时)**: 使用 FFmpeg `Stream Copy` 模式，直接抽取音频轨道，不经过编解码。
2.  **ASR 提速**:
    *   使用 `faster-whisper` + GPU 加速。
    *   开启 VAD (语音活动检测) 自动跳过静音。
    *   设置 `beam_size=1` (贪婪解码) 提升 2 倍速度。
3.  **流程优化**:
    *   **文本先行**: 先通过 ASR 和 LLM 确定关键分段。
    *   **按需截图**: 仅对 LLM 建议的关键时间点进行截图。
    *   **并行 IO**: 使用多线程并发进行视频抽帧和写入。

## 快速开始

### 1. 安装依赖

确保你的系统中已安装 [FFmpeg](https://ffmpeg.org/)。

然后安装 Python 依赖：

```bash
pip install -r requirements.txt
```

### 2. 配置环境

复制 `.env.example` 为 `.env` 并填写你的配置：

```bash
cp .env.example .env
```

编辑 `.env`：
*   `OPENAI_API_KEY`: 你的硅基流动 API Key。
*   `OPENAI_BASE_URL`: 硅基流动 API 基础路径 (默认为 `https://api.siliconflow.cn/v1`)。
*   `LLM_MODEL`: 使用的模型名称 (默认为 `deepseek-ai/DeepSeek-V3`)。
*   `VIDEO_PATH`: 待处理的视频路径 (默认 `input.mp4`)。

### 3. 运行

将你的视频文件命名为 `input.mp4` (或在 `.env` 中指定路径)，然后运行：

```bash
python fast_video_summary.py
```

### 4. 查看结果

处理完成后，结果将保存在 `fast_output` 目录下：
*   `final_report.md`: 最终的 Markdown 分析报告。
*   `images/`: 抽取的关键帧图片。

## 注意事项

*   **GPU 加速**: 默认配置使用 `cuda`。如果没有 NVIDIA GPU 或未配置好 CUDA 环境，脚本会自动回退到 `cpu` 模式 (速度会变慢)。
*   **模型大小**: 默认使用 `medium` 模型。如果显存不足，可以在 `.env` 中改为 `small`；如果追求更高精度，可以改为 `large-v3`。
