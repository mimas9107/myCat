---
name: "SPEC.md"
description: "myCat Voice Assistant Enhancement — Technical Specification"
created_date: "2026/07/10"
modified_date: "2026/07/27"
project_version: "0.2.1"
document_version: "1.0.0"
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
