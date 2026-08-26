# TASK-3d：觸發後重複轉錄抑制（Retrigger Suppression）

* **日期**：2026-08-22
* **依據**：`vendors/PLAN-3d.md`
* **狀態**：進行中（Phase 1-2 完成，Phase 3-4 待審）

## 實作項目

### Phase 1: core 緩衝清空 API
- [x] `AudioStreamManager.clear_buffer()`：清空滑動緩衝，與 feed 線串併發安全；WAV 子類行為一致（繼承即可則明確驗證不需覆寫）
- [x] 單元測試：clear 後 `get_buffered_audio()` 回空；feed 線串持續寫入期間 clear 不死鎖、不拋例外、清除後新資料持續累積
- [x] `python3 -m py_compile` 通過

### Phase 2: worker re-arm 狀態機
- [x] 意圖 emit 後呼叫 `clear_buffer()`
- [x] re-arm 狀態機：lockout 到期（`vad.retrigger_lockout_ms`，預設 1500）AND（L1 released ≥ `voice.release_ms` OR 距觸發 ≥ `vad.rearm_max_wait_ms` 強制上限）；L1 缺席（純 L0 fallback）僅走 lockout 計時
- [x] `config.yaml` / `tests/fixtures/config_test.yaml` 同步新鍵（省略＝預設值語義）
- [x] `vad_cooldown` 變數正名為 `rms_log_throttle`（實際語義為 RMS 日誌節流），消除誤導——只改命名，不改行為
- [x] worker 層測試（monkeypatch ASR 免模型載入）：lockout 期間輪詢不再觸發；L1 released 提前武裝；cap 到期強制武裝

### Phase 3: e2e 擴充與回歸
- [x] 新 e2e 斷言計數：pos fixture 完整播放**恰 1 次** CHAT（現況會連發多次）
- [x] 新 e2e：同 fixture 間隔 ~1s 播放兩次 → **恰 2 次** CHAT
- [x] 純 L0 相容：移除 `voice:` 段後重複抑制仍生效（lockout 為無條件底線）
- [x] 全套件逐檔獨立行程回歸零新增失敗（TASK-3c 觸及域基準：voice_vad 10 / voice_pipeline_e2e 20 / voice_bubble 5 / speech_bubble 4）

### Phase 4: 文件版號
- [x] MEMOIR 記錄（診斷證據鏈→方案取捨→實作偏離若有）
- [x] SPEC 更新觸發語義；CHANGELOG 條目；版號遞增＋四文件＋pyproject.toml 對齊（version-sync-checker，README/CHANGELOG 中段 frontmatter 豁免以人工對齊為準）
- [ ] （真機）soak 驗證：單句不連發、連續兩句各自觸發、快速連續指令不被 lockout 吃掉 ※使用者作業

## 驗收標準
- [x] `EnergyVAD` / `VoiceVAD` 內部零變更
- [x] 單句音源一次播放 → 恰一筆意圖（自動化斷言綠）
- [x] 省略新 config 鍵 → 行為等於本 Task 預設值；移除 `voice:` 段 → 純 L0 ＋ lockout 仍防重複
- [x] TASK-3c 既有 e2e 全數通過（零回歸）

## 實際改動量

| 檔案 | 新增 | 刪改 | 說明 |
|------|------|------|------|
| `mycat/voice_assistant/core/audio_stream.py` | +28 | -3 | `_buffer_lock` + `clear_buffer()` + 各方法加鎖 |
| `mycat/voice_assistant/voice_worker.py` | +48 | -8 | re-arm 狀態機（含 L1 期間餵食修正）+ `clear_buffer()` + `rms_log_throttle` |
| `mycat/voice_assistant/config.yaml` | +2 | 0 | `retrigger_lockout_ms` + `rearm_max_wait_ms` |
| `tests/fixtures/config_test.yaml` | +2 | 0 | 同上 |
| `tests/test_audio_stream_clear.py` | +97 | 0 | clear_buffer 單元測試（3 支 + WAV 繼承） |
| `tests/test_voice_pipeline_e2e.py` | +103 | 0 | 3 支 e2e（單句/雙句/純 L0） |
| `vendors/TASK-3d.md` | 全面更新 | | 進度追蹤 + 踩坑紀錄 |
| `SPEC.md` | +8 | 0 | 新增重複觸發抑制規格段 |
| `MEMOIR.md` | +15 | 0 | TASK-3d 記錄 |
| `CHANGELOG.md` | +8 | 0 | 0.3.1 條目（分支區域） |
| `README.md` | 0 | 0 | frontmatter 版號對齊 |
| `pyproject.toml` | 0 | 1 | version 0.3.0 → 0.3.1 |

## 踩坑紀錄
- `vad_cooldown` 原名只做 RMS 日誌節流（每 2s 一條 log），與觸發節流無關，正名為 `rms_log_throttle` 避免誤導
- feed 線串併發安全：`deque.clear()` 在 CPython GIL 下理論安全，但加 `threading.Lock` 更明確；`get_buffered_audio()` / `get_recent_chunk()` 需在 lock 內複製 deque 再 concatenation，避免 lock 持有時間過長
