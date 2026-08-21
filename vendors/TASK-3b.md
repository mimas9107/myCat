# TASK-3b：語音管線 WAV 注入式全真自動測試

* **日期**：2026-08-21
* **依據**：`vendors/PLAN-3b.md`
* **狀態**：已完成（待使用者驗收）

## 實作項目

### Phase 1: WavAudioStream + 開關
- [x] `core/audio_stream.py` 新增 `WavAudioStreamManager`（命名對齊父類）：同介面、daemon thread 即時節奏餵 `_audio_callback`
- [x] `voice_worker.py` 建 stream 處加 `MYCAT_AUDIO_WAV` 判斷（`MYCAT_MOCK_VOICE` 優先）
- [x] `python3 -m py_compile` 通過

### Phase 2: conftest 根修
- [x] `tests/conftest.py` `setdefault("MYCAT_AUDIO_WAV", <預設fixture>)`
- [x] 全套件重跑：不再出現 PyAudio Fatal Abort（既有建主視窗測試全數改吃 WAV 音源）

### Phase 3: fixtures 挑選與行為驗證
- [x] 自 `~/project/inmp441_recorder/server/uploads/` 選候選（正 4 / 負 2）
- [x] 以真 `EnergyVAD` 逐 chunk 行為驗證，按結果定去留（禁用整檔 RMS 肉眼判斷）
- [x] 定稿複製至 `tests/fixtures/audio/`（純拷貝零處理）

### Phase 4: E2E 測試撰寫
- [x] Intent parser 單元測試：SLEEP / SET_REMINDER / CHAT 後備 / NONE 四路（純正則，零音檔）
- [x] SLEEP → 動畫狀態機整合測試：offscreen 直呼 `handle_intent("SLEEP")`，斷言 sleeping 狀態/clip（含無素材 fallback 關窗路徑）
- [x] `tests/test_voice_pipeline_e2e.py`：暖啟動 / VAD 觸發 / VAD 抑制 / ASR 寬鬆轉寫 / CHAT 後備管線暢通（於 worker 信號邊界斷言，免 HTTP mock）
- [ ] ~~session-scoped worker fixture~~ → 改為每 E2E 測試獨立 worker（whisper 載兩次共 ~10s，換取測試隔離與簡潔）
- [ ] ~~`@pytest.mark.hardware` 真硬體冒煙~~ → 不需要：conftest 預設即無硬體路徑，真硬體驗證保留給手動腳本
- [x] 全部通過；全套件綠（281 passed / 3 failed 為既有 icalendar 缺模組，與本任務無關）

### Phase 5: 文件與版號
- [x] MEMOIR 新增本任務記錄（含 fixture RMS 陷阱教訓）
- [x] CHANGELOG 條目；`project_version` 0.2.6 → 0.2.7；各文件 frontmatter 對齊
- [x] version-sync-check 通過（README/CHANGELOG missing_header 屬豁免正常）

## 驗收標準
- [x] 無麥克風環境全套件可跑完且不 Abort
- [x] 暖啟動/VAD/ASR 全為真實元件執行（僅音源與 Ollama HTTP 為替身）
- [x] 正樣本觸發、負樣本抑制，斷言穩定不 flaky
- [x] 手動腳本原樣保留

## 實際改動量

| 檔案 | 新增 | 刪改 | 說明 |
|------|------|------|------|
| `mycat/voice_assistant/core/audio_stream.py` | ~70 行 | 0 刪 | `WavAudioStreamManager` 子類（16-bit 驗證/下混/重採樣/即時節奏餵食） |
| `mycat/voice_assistant/voice_worker.py` | 6 行 | 0 刪 | `os` import + `MYCAT_AUDIO_WAV` 分支 |
| `tests/conftest.py` | 5 行 | 0 刪 | `setdefault("MYCAT_AUDIO_WAV", ...)` 根修 |
| `tests/fixtures/config_test.yaml` | 新檔 | — | 生產 config 同構，僅 `vad.threshold: 2000` / `drop_after_warmup_sec: 0` |
| `tests/fixtures/audio/*.wav` | 6 檔 | — | ESP32 訓練語料純拷貝（pos×4 / neg×2） |
| `tests/test_voice_pipeline_e2e.py` | 新檔 ~200 行 | — | 11 tests：parser×3 + 動畫×6 + E2E×2 |
| `vendors/PLAN-3b.md` / `TASK-3b.md` | 新檔 | — | 計畫與執行清單 |

## 踩坑紀錄
- **整窗 RMS 稀釋**：`get_recent_chunk(0.1)` 的 `[-num_samples:]` 切片在 ring buffer 未滿時回傳整個 3 秒緩衝 → 有效 VAD 視窗是整窗 RMS，單短句被稀釋。增益放大/拼接補洞等加工策略全部失敗（削波或不穩定），**純拷貝自然原聲 + 校準測試門檻**才是正解。
- **VAD threshold 是設備校準參數**：生產 21000 對應桌面麥克風增益；ESP32 INMP441 錄音安靜一個量級（buffered RMS pos 3477~7831 / neg ≤606）。測試 config 校準 2000（雙向邊際 1.74x/3.3x），與 MEMOIR 既有校準任務同一性質。
- **信號接錯線**：`ASR_READY` 走 `asr_status_signal` 而非 `status_changed_signal`，接錯導致暖啟動斷言假失敗。
- **全套件 Segfault 是跨測試 Qt 狀態污染**：`test_window_behavior` 拖曳測試單跑通過、全套件崩潰，pyproject 註解早已寫明需 `pytest-forked` 但套件未裝。安裝後全套件穩定完成。
- **`VoiceBridge.__new__` 白箱測試**：跳過 `__init__` 需手動補 `_sleep_callback`/`_reminder_callback`/`_llm_backend` 等 None 屬性，否則 `handle_intent` AttributeError。
