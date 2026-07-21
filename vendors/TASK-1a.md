# 實作任務分配：myCat 語音助理整合 (TASK-1a)

本文件將 `PLAN-1a.md` 的架構規劃拆解為具體可執行的 Agent Tasks。每個任務邊界明確，可依序獨立開發。

---

### [Task 1] 語音環境與設定基礎
* **目標**：建立 `voice_assistant/` 目錄結構，並完成 `config.yaml` 參數定義與載入機制。
* **實作細項**：
  - [x] 建立 `mycat/voice_assistant/` 與 `mycat/voice_assistant/core/` 目錄結構與 `__init__.py`
  - [x] 建立 `mycat/voice_assistant/config.yaml` 並定義 `sample_rate`, `chunk_duration_ms`, `vad_threshold`, `wake_word_threshold`, `model_path` 等參數
  - [x] 實作 `mycat/voice_assistant/config_loader.py` 模組以讀取與解析 YAML 設定檔

### [Task 2] 開發純邏輯層：`core/audio_stream.py`
* **目標**：利用 PyAudio 進行不斷線的背景收音，並維護環形緩衝區 (Ring Buffer)。
* **實作細項**：
  - [x] 使用 `threading` 與 `collections.deque` 處理音訊回調與緩衝
  - [x] 實作 `AudioStreamManager` 類別，提供 `start()`, `stop()`, 與 `get_buffered_audio()`
  - [x] 確保無任何 Qt 依賴與元件

### [Task 3] 開發純邏輯層：`core/vad_filter.py`
* **目標**：攔截無效雜訊，減少後端模型運算負擔。
* **實作細項**：
  - [x] 實作 `EnergyVAD` 類別，透過計算音訊 chunk 的 RMS 或能量判斷是否為語音
  - [x] 提供 `is_speech(audio_chunk)` 介面

### [Task 4] 開發純邏輯層：`core/wake_word.py`
* **目標**：喚醒詞偵測 (Edge Impulse)。
* **實作細項**：
  - [x] 封裝 Edge Impulse Python SDK / Runner 介面
  - [x] 實作 `WakeWordEngine` 類別，提供 `predict(audio_chunk)` 介面

### [Task 5] 開發純邏輯層：`core/asr_pipeline.py`
* **目標**：語音轉文字 (faster-whisper)。
* **實作細項**：
  - [x] 初始化 `WhisperModel`
  - [x] 實作 `ASRPipeline` 類別，提供 `transcribe(audio_np_array) -> str` 介面

### [Task 6] 開發純邏輯層：`core/intent_parser.py`
* **目標**：將轉錄出的純文字，轉換為系統可讀的抽象意圖。
* **實作細項**：
  - [x] 實作 `parse_text_to_intent(text: str) -> dict` 介面
  - [x] 定義基礎意圖：例如 `CHAT` (對話), `SET_REMINDER` (設定提醒) 等

### [Task 7] 開發中介橋接層：`voice_worker.py`
* **目標**：串接所有 `core/` 模組，建立語音主迴圈，並實作 Qt Signals。
* **實作細項**：
  - [x] 繼承 `PySide6.QtCore.QThread` 建立 `VoiceWorker` 類別
  - [x] 宣告 `status_changed_signal` 與 `intent_detected_signal`
  - [x] 在 `run()` 迴圈中協調 core 模組與 Signal 廣播

### [Task 8] UI 整合與最終串接：`mycat/main.py`
* **目標**：在貓咪主程式中啟動 `VoiceWorker` 並對接 UI。
* **實作細項**：
  - [x] 實例化 `VoiceWorker` 並啟動 thread
  - [x] 連接 `status_changed_signal` 並對應修改貓咪動畫
  - [x] 連接 `intent_detected_signal` 將意圖導向對應的系統功能 (Ollama 聊天或提醒)

