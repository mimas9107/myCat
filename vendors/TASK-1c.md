# TASK-1c.md

## 總體目標
完成 myCat 語音核心的輸入裝置自動偵測/持久化設定，以及 ASR 暖啟動與記憶體管理機制。

---

## [TASK-force1] 輸入裝置偵測與使用者設定
- [x] `core/audio_stream.py` 新增 `list_devices()` 靜態方法
- [x] `core/audio_stream.py` 新增 `prefer_suitable_device()` 靜態方法
- [x] `config.yaml` 擴充 `audio.device_index` → `null` 表示自動偵測
- [x] `voice_assistant/device_store.py` 實作使用者設定持久化 (`voice_device.json`)
- [x] `voice_device_dialog.py` (新增) GUI 實作
- [x] `settings_ui.py` 整合音訊裝置下拉選單
- [x] `voice_worker.py` 加入 `update_device()` 熱重啟機制

---

## [TASK-force2] Ring Buffer & ASR 暖啟動
### A. Ring Buffer 重構
- [x] `audio_stream.py` 新增 `get_recent_chunk(duration_sec=0.1)`
- [x] `voice_worker.py` 改用 `get_recent_chunk()` (DRY 重構)

### B. ASR 暖啟動 & 記憶體管理
- [x] `core/asr_pipeline.py` 新增 `load()` / `unload()` 方法
- [x] `voice_worker.py` 在 `run()` 開頭呼叫 `self.asr.load()` (非 lazy-load)
- [x] `voice_worker.py` 新增狀態 `ASR_LOADING`、`ASR_READY`、`ASR_UNLOADED` 並整合 Signal
- [x] `config.yaml` 新增 `asr.drop_after_warmup_sec: 5.0`
- [x] `voice_worker.py` 新增 `_warmup_start_time` 與 drop 判斷邏輯
- [x] `voice_worker.py` 監聽 SLEEP intent → 呼叫 `self.asr.unload()`
- [x] VAD 觸發但 `self.asr.model is None` → 先 `self.asr.load()` 再 transcribe

---

## 驗收標準
- [x] 系統啟動能自動選擇合適輸入裝置。
- [x] 設定能持久化並透過 GUI 修正。
- [x] ASR 模型於啟動時即載入，不再 lazy-load。
- [x] 進入 SLEEP 狀態時成功釋放 ASR 模型記憶體。
- [x] 暖啟動後短期內辨識結果正確過濾。
- [x] 更新 `MEMOIR.md` 紀錄卡點與解法。
