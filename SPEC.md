---
name: "SPEC.md"
description: "myCat Voice Assistant Enhancement — Technical Specification"
created_date: "2026/07/10"
modified_date: "2026/08/21"
project_version: "0.2.7"
document_version: "1.1.0"
agent_sign: ['human/mimas', 'opencode/current']
---

# 專案技術規格書 (SPEC.md)

本文件定義 `myCat` 語音助理增強專案的技術規格與依賴。

## 1. 系統架構
* **基礎框架**：原專案使用 Python 3.10+ 與 PySide6 (Qt for Python)。
* **整合架構**：採用「混合式折衷方案」，將語音功能模組化存放於 `mycat/voice_assistant/`。
* **執行緒模型**：主執行緒負責 Qt UI；背景執行緒 (`VoiceWorker` 繼承 `QThread`) 負責音訊監聽與 AI 推理。跨執行緒通訊嚴格使用 Qt Signals 達成。

## 2. 語音技術棧 (Voice Tech Stack)
* **音訊擷取 (Audio Streaming)**
  * 套件：`PyAudio`
  * 規格：單聲道 (Mono), 16kHz 取樣率, 16-bit PCM。
  * 緩衝區：利用 `collections.deque` 實作 Ring Buffer，保留過去 2-3 秒的歷史音訊供喚醒後使用。
* **語音活動偵測 (VAD - Voice Activity Detection)**
  * 實作：基於 `numpy` 的輕量級 RMS/能量檢測 (Energy VAD)。
  * 目的：過濾靜音與背景底噪，避免過度消耗喚醒詞模型算力。
  * 門檻校準：`vad.threshold` 為設備×環境的校準參數，非普適常數。生產定案值 21000 (RMS)：環境底噪 6k–7k、風扇風切 9k–13k、敲擊瞬態 16k–19k；調校代理指標為 think 動畫誤觸發頻率（20k 頻繁誤觸、23k 大吼仍無反應）。詳見 MEMOIR「VAD 門檻環境階梯實測」。
* **喚醒詞偵測 (Wake Word Detection)**
  * 套件：`edge_impulse_linux` (Edge Impulse Python SDK)
  * 模型格式：`.eim`
  * 觸發條件：Confidence Score > 門檻值 (預設 0.8)。
* **語音辨識 (ASR - Automatic Speech Recognition)**
  * 套件：`faster-whisper`
  * 規格：預設使用 `base` 或 `tiny` 模型，支援 CPU `int8` 量化推理以降低資源消耗。

## 3. 意圖通訊協定 (Intent Protocol)
所有辨識出的文字都將被解析為以下格式的 JSON/Dictionary，再經由 Qt Signal 發送給 UI：
```python
{
    "type": "SET_REMINDER" | "CHAT" | "SLEEP" | ... ,
    "data": {
        # 依 type 不同的 payload
    }
}
```

## 附註 A：VAD 人聲頻段 300–3400Hz 的第一性原理

* **電信遺產**：ITU-T 電話語音通道（PSTN 類比線路、G.711 數位化，8kHz 取樣 Nyquist 上限 4kHz）——百年驗證的語音可懂度黃金頻段。
* **下界 300Hz，擋「能量大但無語音資訊」**：電源哼聲（50/60Hz 及諧波）、呼吸噴麥、風切 rumble 全落此域。本專案實測風扇風切主要能量即在 <300Hz，帶通後直接消失。
* **上界 3400Hz，可懂度承載上限**：元音身份由共振峰決定——F1（300–800Hz）、F2（800–2500Hz）、F3（2500–3500Hz）全在帶內；4kHz 以上主要是摩擦音氣聲（/s/、/f/），對活動偵測貢獻小且引入嘶嘶噪音。
* **基頻在帶外不影響 VAD**：成年男聲基頻僅 85–180Hz，低於下界；但諧波列自 360Hz 起密集入帶＋共振峰結構，帶內能量足以表徵「有人說話」。活動偵測不需基頻本身（那是音高偵測的需求）。
* **本專案實證**：esp-miao 2026-03-03 ESP32 實測，300–3400Hz 帶內能量判別比 ≈13 倍（同期全頻 RMS 僅 ≈4 倍）。
* **非教條**：邊界做成 `vad.voice.freq_min/freq_max` config 可調，遇高頻摩擦音豐富場景可上調至 4000。
