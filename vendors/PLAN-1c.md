# PLAN-1c.md
## Background
### [] TASK-force1:
- 輸入（麥克風）裝置, 各使用者電腦都會不同, 作業系統、使用音訊架構都會影響我們程式的收音設備與 VAD activation機制.
- os 與 sound input device 對於 VAD 的比較 matrix
- 規劃需要的系統啟動時自動偵測輸入裝置選項, 持久化使用者設定輸入裝置選項, 供使用者設定的 GUI. 方便使用者在我們偵測失靈時可以手動調整.

### [] TASK-force2:
- voice目前架構下, 需要 ring buffer streaming機制嗎？是否會讓收音辨識上較穩定？
- voice目前架構下, 是否可以在系統啟動時, ASR(faster-whisper)先行暖啟動提前載入 model, 並且持續到貓咪睡著才有卸載機制, 貓咪有受到 VAD作用才會喚醒並暖啟動載入模型, 而喚醒後一小段時間內要有 drop機制, 可能要校調因應暖啟動模型的不穩定偵測的 drop機制.

---

# AI Agent 分析與實作計畫 (by AI Agent on 2026-07-26)

## 現狀摘要
- TASK-1a (語音核心) 與 TASK-1b (語音動畫) 均已 [x] 完成
- `AudioStreamManager` 使用 `device_index` 硬編碼 (`config.yaml` 預設 `6`)
- `VoiceWorker` 在 `run()` 內才 `start()` `AudioStreamManager`，ASR 模型也在第一次 `transcribe()` 時才 lazy-load
- 無裝置列舉、無 GUI 設定、無 ASR 暖啟動機制

---

## [TASK-force1] 輸入裝置偵測與使用者設定

**目標**：讓 myCat 啟動時自動偵測可用音訊裝置，提供持久化設定與 GUI 手動切換。

| # | 細項 | 說明 |
|---|------|------|
| [ ] | `core/audio_stream.py` 新增 `list_devices()` 靜態方法 | 封裝 PyAudio 列舉邏輯，回傳 `list[dict]` (index, name, channels, sample_rate) |
| [ ] | `core/audio_stream.py` 新增 `prefer_suitable_device()` 靜態方法 | 自動過濾：跳過 raw ALSA（不支援 16kHz）、優先 PulseAudio/PipeWire、回傳最佳或 None |
| [ ] | `config.yaml` 擴充 `audio.device_index` → `null` 表示自動偵測 | 向後相容，`null` 時 `AudioStreamManager.__init__` 呼叫 `prefer_suitable_device()` |
| [ ] | `config_loader.py` 或新增 `device_store.py` 實作使用者設定持久化 | 用 `paths.config_dir() / "voice_device.json"` 儲存使用者選擇的 device_index |
| [ ] | `settings_ui.py`（或 voice 專屬設定頁）新增音訊裝置下拉選單 | 透過 `list_devices()` 填入選項，使用者選取後寫入 `voice_device.json` |
| [ ] | `voice_bridge.py` 或 `voice_worker.py` 加入設定監聽與熱重啟機制 | 當 device 變更時，`stop()` 舊 worker → `start()` 新 worker 以新 device |

### OS 相容性 Matrix

| OS | 音訊架構 | 16kHz 支援 | 自動過濾策略 |
|----|---------|-----------|------------|
| Linux | PulseAudio / PipeWire | ✅ (自動轉換) | 優先選 pulse/pipewire |
| Linux | raw ALSA | ❌（硬體綁定） | 跳過 name 含 `hw:` |
| macOS | CoreAudio | ✅ | 全部皆可 |
| Windows | WASAPI / DirectSound | ✅ | 全部皆可 |

---

## [TASK-force2] Ring Buffer Streaming 分析 & ASR 暖啟動

### 目標 A — Ring Buffer 必要性分析

現有 `AudioStreamManager` 已使用 `collections.deque(maxlen=N)` 作為 ring buffer。經程式碼審查：
- `audio_callback` 每次收到 chunk 就 `append()` 到 ring buffer
- `get_buffered_audio()` 回傳全部 buffer 作為 `np.ndarray`
- `voice_worker.py` 每次 loop 取整段 buffer（含歷史）做 VAD 判斷

**結論**：現有 ring buffer 機制已經足夠。不需額外的 streaming 機制，因為：
1. PyAudio 的 callback mode 已是 non-blocking streaming
2. `deque` 的 `maxlen` 自然淘汰舊資料，無需手動管理
3. 暫無高頻率 real-time 需求（僅 VAD + 偶發 ASR）

| # | 細項 | 說明 |
|---|------|------|
| [ ] | `audio_stream.py` 新增 `get_recent_chunk(duration_sec=0.1)` | 取代 voice_worker 中重複的 `audio_buffer[-self.chunk_size:]` slice |
| [ ] | `voice_worker.py` 改用 `get_recent_chunk()` | DRY 重構，不改變行為 |

### 目標 B — ASR 暖啟動 (Warm-load)

現狀：`ASRPipeline._ensure_model()` 是 lazy-load，在第一次 `transcribe()` 時才載入 `WhisperModel`（耗時 ~2-5秒）。

需求：
- 系統啟動時（`VoiceWorker.__init__` 或 `run()` 開頭）提前載入 ASR 模型
- 貓咪睡著時卸載模型（free memory）
- 貓咪被 VAD 喚醒時重新載入
- 載入後短期內（drop window）的辨識結果要丟棄，因暖啟動初期不穩定

| # | 細項 | 說明 |
|---|------|------|
| [ ] | `core/asr_pipeline.py` 新增 `load()` / `unload()` 方法 | `load()` 顯式調用 `_ensure_model()`；`unload()` 設 `self.model = None; self._initialized = False` |
| [ ] | `voice_worker.py` 在 `run()` 開頭（`self.audio_stream.start()` 成功後）呼叫 `self.asr.load()` | 提前載入模型，非 lazy |
| [ ] | `voice_worker.py` 新增狀態 `ASR_LOADING`、`ASR_READY`、`ASR_UNLOADED` | 對應 `status_changed_signal` 發送 |
| [ ] | `config.yaml` 新增 `asr.drop_after_warmup_sec: 5.0` | 暖啟動 drop window（預設 5秒） |
| [ ] | `voice_worker.py` 新增 `_warmup_start_time` 與 drop 判斷 | `transcribe()` 前檢查：若 `time_since_warmup < drop_after_warmup_sec`，跳過本次辨識並 log |
| [ ] | `voice_worker.py` 監聽 SLEEP intent → 呼叫 `self.asr.unload()` | 貓咪入睡時卸載模型節省記憶體 |
| [ ] | VAD 觸發但 `self.asr.model is None` → 先 `self.asr.load()` 再 transcribe | 自動重新載入 |

### ASR 狀態機

```
啟動 → [ASR_LOADING] → ASR 載入完成 → [LISTENING + ASR_READY]
                                                      ↓
                        VAD 觸發→ 檢查 drop window → 在 window 內? → 跳過
                                                      ↓ 不在 window 內
                                                → [TRANSCRIBING] → ASR → [LISTENING]
                                                      ↓
                        SLEEP intent → [ASR_UNLOADED] → model unload
                                                      ↓
                        下次 VAD 觸發 → 自動 reload → [ASR_LOADING] → ...
```

---

## 檔案改動清單

| 檔案 | 改動範圍 |
|------|---------|
| `core/audio_stream.py` | 新增 `list_devices()`、`prefer_suitable_device()`、`get_recent_chunk()` |
| `core/asr_pipeline.py` | 新增 `load()`、`unload()` |
| `voice_assistant/voice_worker.py` | 暖啟動邏輯、device 動態切換、drop window、SLEEP unload |
| `voice_assistant/config.yaml` | `audio.device_index: null`（auto）、新增 `asr.drop_after_warmup_sec` |
| **新增** `mycat/voice_device_dialog.py` | 音訊裝置選擇 GUI 對話框 |
| `mycat/settings_ui.py` | 整合裝置選擇 dropdown |
| `mycat/voice_bridge.py` | 監聽 device 變更，觸發 worker restart |

---

## 建議執行順序

1. **force1-a**: `audio_stream.py` 新增 `list_devices()` + `prefer_suitable_device()` — 純邏輯，可獨立測試
2. **force1-b**: `config.yaml` 改 `device_index: null` + 持久化 `voice_device.json`
3. **force2-a**: `audio_stream.py` 新增 `get_recent_chunk()` → `voice_worker.py` DRY 重構
4. **force2-b**: `asr_pipeline.py` 新增 `load()`/`unload()` + `voice_worker.py` 暖啟動 loop
5. **force2-c**: drop window 機制 (`drop_after_warmup_sec`)
6. **force2-d**: SLEEP → unload + VAD → reload 鏈路 ; 此鍊路需加入訊息拋出、時間戳記 作為衡量動作邏輯的合理性.
7. **force1-c**: `voice_device_dialog.py` GUI + `settings_ui.py` 整合
8. 冒煙測試 + `MEMOIR.md` 更新
