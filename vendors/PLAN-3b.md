# PLAN-3b：語音管線 WAV 注入式全真自動測試

* **日期**：2026-08-21
* **狀態**：草案待審
* **前置**：TASK-3a（所有權還原）已完成；氣泡邊界分析已固化

## 1. 背景與動機

1. `tests/test_vad.py`、`test_asr_chain.py`、`test_e2e_pipeline.py` 是手動硬體腳本（需要麥克風/Ollama），pytest 收集數為 0。
2. 全套件跑在無麥克風環境時，某些建主視窗的測試會觸發 TASK-1c 的 ASR 暖啟動 → PyAudio 開真裝置失敗 → **Fatal Abort 炸掉整個 pytest process**。
3. 使用者裁示：不做 mock 式測試，而是**真系統、假音源**——暖啟動、VAD、ASR 全部照實執行，只把麥克風換成預錄 WAV。

## 2. 核心設計：WavAudioStream 假音源注入

全系統唯一硬體耦合點是 `AudioStream.start()` 內的 pyaudio 區塊（`mycat/voice_assistant/core/audio_stream.py:36`）。下游主迴圈只依賴介面：`start()/stop()/get_buffered_audio()/device_index/ring_buffer`。

### 2.1 WavAudioStream（新增於自有模組 `core/audio_stream.py`）

* 與 `AudioStream` 同介面（鴨子型別，不強制繼承）。
* `start()`：讀取 WAV → 開一條 daemon thread → 按原 chunk 尺寸（100ms）、**即時節奏**把 int16 bytes 餵進與真裝置相同的 `_audio_callback` 路徑（連 np.frombuffer 轉換都照走）→ 檔案播完自動停止餵食。
* 即時節奏是刻意的：cooldown/warmup 邏輯吃牆鐘，3 秒音檔 = 3 秒測試，換取行為與線上完全一致。

### 2.2 開關：`MYCAT_AUDIO_WAV` 環境變數

* `VoiceWorker` 建 stream 處判斷：env 有值 → 建 `WavAudioStream(wav_path)`；否則照舊建 `AudioStream`。
* 與既有 `MYCAT_MOCK_VOICE` 同款模式；兩者互斥時 `MYCAT_MOCK_VOICE` 優先（mock 是更外層的替身）。
* `tests/conftest.py` 設 `os.environ.setdefault("MYCAT_AUDIO_WAV", <預設fixture>)`——全套件（含建主視窗的既有測試）從此不再碰 PyAudio，Abort 根修。

## 3. Fixtures 策略

來源：`~/project/inmp441_recorder/server/uploads/`（ESP32 INMP441 錄製，16kHz/mono/16bit/3s，與管線格式完全一致）。

* **語料性質（使用者裁示）**：全部為已停用的喚醒詞「heymiaomiao／嘿喵喵」訓練集，本任務**不測 wake word**，僅將其當作一般語音——VAD 偵測的音訊、後段 ASR 的輸入。使用者暫無其他話術錄音，未來補錄多樣化語句時再擴充 fixtures。
* 選取 **6-10 檔**複製進 `tests/fixtures/audio/`（總計 ~1MB，避免塞 ~500 檔/48MB 入 git）：
  * 正樣本 3-4 檔：`heymiaomiao/heymiaomiao.*`、`-s.*`、`-n.*` 各取代表
  * 負樣本 3-4 檔：`noise/`、`noise1/`、`noise3/` 各取代表
* **挑選必須行為驗證**：已發現整檔 RMS 正負樣本重疊（語音集中前段、平均被稀釋），候選檔一律用真 `EnergyVAD` 逐 chunk 跑過，按「VAD 是否如預期觸發/抑制」定去留，不以肉眼看平均能量。

## 4. 測試矩陣（新檔 `tests/test_voice_pipeline_e2e.py`）

| # | 測試 | 斷言 |
|---|------|------|
| 0 | Intent parser 單元測試（純正則，零硬體零音檔） | `SLEEP`（sleep/hide/shut down…）、`SET_REMINDER`（remind me X → message=X）、`CHAT` 後備、`NONE` 空值——四路全覆蓋。現行實作僅此三 intent；未來新增 intent 時此處擴充 |
| 0b | SLEEP → 動畫狀態機整合測試（免音檔，直呼 `handle_intent`） | offscreen 視窗：有 CharPack 素材 → `base_state="sleeping"` 或 `sleep_in` clip 啟動；無素材 → 優雅關窗不炸。這是語音互動最核心的可視效果路徑（使用者裁示的驗證重點），E2E 音檔版待補錄 "go to sleep" 後接上 | |
| 1 | 暖啟動 | 真 `VoiceWorker.run()`：`asr_status_signal` 到達 `ASR_READY`（whisper 真載入，session 級共用一次） |
| 2 | VAD 觸發 | 餵正樣本（嘿喵喵）：VAD 事件觸發、ASR 收到 buffer |
| 3 | VAD 抑制 | 餵負樣本（noise）：無 VAD 觸發、無 ASR 呼叫 |
| 4 | ASR 轉寫 | 轉寫非空且含寬鬆關鍵詞（"miao"/"meow"/"mao"/"喵" 任一；whisper 對 "heymiaomiao" 的拼寫有變異，禁精確匹配） |
| 5 | Intent + 氣泡（管線暢通） | 語料僅「嘿喵喵」，必落 `CHAT` 後備——驗 plumbing：轉寫送達 Ollama HTTP mock、mock 回應送達 `SpeechBubble.show()`。`SLEEP`/`SET_REMINDER` 的 E2E 路徑待使用者補錄對應語句後啟用（parser 層已由測試 0 覆蓋） |

* Wake word 不測——config `enabled: false` 且模型檔不存在，不覆蓋未使用的路徑。
* 真硬體冒煙（開真 stream 讀 frames）保留為 `@pytest.mark.hardware` opt-in，無裝置自動 `pytest.skip`。
* **升級路徑**：使用者補錄指令語句後擴充 fixtures——最低成本閉環：一個 3 秒說 "sleep" 的 wav 即可讓 `SLEEP` 全鏈（聲音→ASR→intent→動畫）E2E 通過；多樣化指令語句（開燈/天氣等）到位後，測試 5 升級為語意斷言。

## 5. 非目標

* 不刪三個手動腳本（校準工具：threshold 調校需人眼）。
* 不做 FrameSource 抽象層/工廠——一個 env 判斷夠用，等第二種音源需求出現再說。
* 不用 pytest-forked 掩蓋崩潰——conftest 注入即根修。

## 6. 風險與緩解

| 風險 | 緩解 |
|------|------|
| whisper 首次載入慢（CPU base model 數秒~十秒級） | session-scoped fixture 共用 worker；量測後若過慢可降 `model_size=tiny` 僅測試用 |
| fixture 行為驗證不過（正樣本 VAD 不觸發） | 擴大候選池逐檔掃描（205 正/280 負樣本充足）；必要時以 config threshold 校準紀錄（MEMOIR 既有）為線索 |
| ASR 斷言脆弱 | 寬鬆關鍵詞匹配 + 只斷言「非空」下限 |
| Ollama 邊界侵入 | mock 限縮在 intent parser 的 HTTP 層，不碰管線本體 |

## 7. 版號影響

程式碼+測試變更 → `project_version` PATCH 遞增（0.2.6 → 0.2.7），CHANGELOG 為單一事實來源。
