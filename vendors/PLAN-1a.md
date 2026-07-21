# 專案架構規劃：myCat 語音助理整合方案 (PLAN-1a)

## 1. 架構總覽
本計畫旨在將基於 Edge Impulse (喚醒詞) 與 faster-whisper (語音辨識) 的語音助理模組，優雅且無縫地整合進 `myCat` Qt 桌面應用中。
採用「混合式折衷方案」：將語音功能作為 `myCat` 的子模組 (`mycat/voice_assistant/`)，但在內部嚴格區分「純 Python 邏輯層 (Core)」與「Qt 中介橋接層 (Worker)」。

## 2. 目錄結構規劃
```text
[myCat root]/
├── mycat/
│   ├── main.py                 # 原有的貓咪主入口 (處理 UI 與 Signal 接收)
│   ├── ...
│   └── voice_assistant/        # 新增的語音模組目錄
│       ├── __init__.py
│       ├── config.yaml         # 語音相關參數設定檔
│       ├── core/               # 【純 Python 核心層】絕對不包含任何 Qt/GUI 程式碼
│       │   ├── __init__.py
│       │   ├── audio_stream.py # 負責 PyAudio 背景收音與環形緩衝區
│       │   ├── vad_filter.py   # 負責輕量級語音活動偵測 (VAD)
│       │   ├── wake_word.py    # 負責 Edge Impulse 模型推理
│       │   ├── asr_pipeline.py # 負責 faster-whisper 語音轉文字
│       │   └── intent_parser.py# 負責將文字轉化為抽象意圖 (Intent Dictionary)
│       │
│       └── voice_worker.py     # 【中介橋接層】繼承 QThread，負責協調 core，並發送 Qt Signal 給主程式
```

## 3. 核心設計原則
* **解耦與純粹性 (Decoupling)**：`core/` 目錄下的所有模組對 UI 一無所知，僅負責音訊處理、AI 推理與資料轉換。這使得 `core/` 具備極高的可移植性與可測試性。
* **執行緒安全 (Thread Safety)**：所有高密集運算 (如 Whisper 推理、PyAudio 阻塞讀取) 皆封裝在 `voice_worker.py` 的 QThread 中執行，確保貓咪 UI 動畫絕對不會因為語音運算而卡頓。
* **單向資料流 (Unidirectional Data Flow)**：`VoiceWorker` 透過 Qt Signals 廣播狀態變化與意圖，主程式 `main.py` 被動接收訊號並改變貓咪動畫或觸發對應功能 (如 Ollama 對話或提醒設定)。

## 4. 狀態與意圖通訊協定 (Communication Protocol)
`VoiceWorker` 將對外暴露兩種主要的 Qt Signals：

1. **`status_changed_signal(str)`**: 用於通知 UI 改變貓咪的動畫狀態。
   * `LISTENING`: 正在背景收音，無動作。
   * `WAKE_WORD_TRIGGERED`: 聽到喚醒詞，UI 應切換為驚訝或注意動畫。
   * `TRANSCRIBING`: 正在進行語音轉文字，UI 可顯示思考泡泡。

2. **`intent_detected_signal(dict)`**: 傳遞解析完成的使用者意圖。
   格式範例：
   ```json
   {
       "type": "SET_REMINDER",
       "data": { "time": "08:00", "message": "叫我起床" }
   }
   ```
   主程式接收到此訊號後，根據 `type` 執行對應的 UI 操作。
