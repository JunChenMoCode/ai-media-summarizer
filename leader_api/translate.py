import os
import re

import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

from .models import TranscriptLine

_TRANSLATORS: dict[str, tuple] = {}


def _guess_translate_source_lang(lines: list[TranscriptLine]) -> str:
    """
    粗略判断字幕主要语言：
    - CJK 字符占比更高 -> 认为是中文 -> 翻译成英文
    - 否则认为是英文 -> 翻译成中文
    """
    texts = [getattr(line, "text", "") or "" for line in (lines or [])]
    if not texts:
        return "zh"
    cjk = 0
    latin = 0
    for t in texts[:200]:
        cjk += len(re.findall(r"[\u4e00-\u9fff]", t))
        latin += len(re.findall(r"[A-Za-z]", t))
    if cjk >= latin:
        return "zh"
    return "en"


def get_translator(device_pref: str, model_name: str):
    """
    获取（或创建）翻译模型缓存。

    关键点：
    - transformers 模型加载非常慢，必须缓存；
    - 如果设备偏好是 cuda 且可用，就放到 GPU 上跑。
    """
    global _TRANSLATORS
    use_cuda = device_pref == "cuda" and torch.cuda.is_available()
    device = "cuda" if use_cuda else "cpu"
    key = f"{model_name}:{device}"
    if key in _TRANSLATORS:
        return _TRANSLATORS[key]
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    model.to(device)
    model.eval()
    _TRANSLATORS[key] = (tokenizer, model, device)
    return _TRANSLATORS[key]


def translate_lines(lines: list[TranscriptLine], device_pref: str):
    """
    批量翻译字幕行。

    - 选择模型策略：
      - 英文 -> 中文：TRANSLATE_MODEL_EN_ZH（默认 Helsinki-NLP/opus-mt-en-zh）
      - 中文 -> 英文：TRANSLATE_MODEL_ZH_EN 或 TRANSLATE_MODEL（默认 Helsinki-NLP/opus-mt-zh-en）
    - 批量大小：TRANSLATE_BATCH_SIZE（默认 16）
    """
    source_lang = _guess_translate_source_lang(lines)
    if source_lang == "en":
        model_name = os.getenv("TRANSLATE_MODEL_EN_ZH", "Helsinki-NLP/opus-mt-en-zh")
    else:
        model_name = os.getenv("TRANSLATE_MODEL_ZH_EN", os.getenv("TRANSLATE_MODEL", "Helsinki-NLP/opus-mt-zh-en"))

    tokenizer, model, device = get_translator(device_pref, model_name)
    texts = [line.text for line in lines]
    batch_size = int(os.getenv("TRANSLATE_BATCH_SIZE", "16"))
    results = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        inputs = tokenizer(batch, return_tensors="pt", padding=True, truncation=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = model.generate(**inputs, max_new_tokens=256)
        decoded = tokenizer.batch_decode(outputs, skip_special_tokens=True)
        results.extend(decoded)

    return results

