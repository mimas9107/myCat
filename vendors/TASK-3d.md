# TASK-3d：觸發後重複轉錄抑制（Retrigger Suppression）

* **日期**：2026-08-22
* **依據**：`vendors/PLAN-3d.md`
* **狀態**：待審（動工前）

## 實作項目

### Phase 1: core 緩衝清空 API
- [ ] `AudioStreamManager.clear_buffer()`：清空滑動緩衝，與 feed 線串併發安全；WAV 子類行為一致（繼承即可則明確驗證不需覆寫）
- [ ] 單元測試：clear 後 `get_buffered_audio()` 回空；feed 線串持續寫入期間 clear 不死鎖、不拋例外、清除後新資料持續累積
- [ ] `python3 -m py_compile` 通過

### Phase 2: worker re-arm 狀態機
- [ ] 意圖 emit 後呼叫 `clear_buffer()`
- [ ] re-arm 狀態機：lockout 到期（`vad.retrigger_lockout_ms`，預設 1500）AND（L1 released ≥ `voice.release_ms` OR 距觸發 ≥ `vad.rearm_max_wait_ms` 強制上限）；L1 缺席（純 L0 fallback）僅走 lockout 計時
- [ ] `config.yaml` / `tests/fixtures/config_test.yaml` 同步新鍵（省略＝預設值語義）
- [ ] `vad_cooldown` 變數正名（實際語義為 RMS 日誌節流），消除誤導——只改命名，不改行為
- [ ] worker 層測試（monkeypatch ASR 免模型載入）：lockout 期間輪詢不再觸發；L1 released 提前武裝；cap 到期強制武裝

### Phase 3: e2e 擴充與回歸
- [ ] 新 e2e 斷言計數：pos fixture 完整播放**恰 1 次** CHAT（現況會連發多次）
- [ ] 新 e2e：同 fixture 間隔 ~1s 播放兩次 → **恰 2 次** CHAT
- [ ] 純 L0 相容：移除 `voice:` 段後重複抑制仍生效（lockout 為無條件底線）
- [ ] 全套件逐檔獨立行程回歸零新增失敗（TASK-3c 觸及域基準：voice_vad 10 / voice_pipeline_e2e 17 / voice_bubble 5 / speech_bubble 4）

### Phase 4: 文件版號
- [ ] MEMOIR 記錄（診斷證據鏈→方案取捨→實作偏離若有）
- [ ] SPEC 更新觸發語義；CHANGELOG 條目；版號遞增＋四文件＋pyproject.toml 對齊（version-sync-checker，README/CHANGELOG 中段 frontmatter 豁免以人工對齊為準）
- [ ] （真機）soak 驗證：單句不連發、連續兩句各自觸發、快速連續指令不被 lockout 吃掉 ※使用者作業

## 驗收標準
- [ ] `EnergyVAD` / `VoiceVAD` 內部零變更
- [ ] 單句音源一次播放 → 恰一筆意圖（自動化斷言綠）
- [ ] 省略新 config 鍵 → 行為等於本 Task 預設值；移除 `voice:` 段 → 純 L0 ＋ lockout 仍防重複
- [ ] TASK-3c 既有 e2e 全數通過（零回歸）

## 實際改動量

| 檔案 | 新增 | 刪改 | 說明 |
|------|------|------|------|
| （完工後填寫） | | | |

## 踩坑紀錄
- （待累積）
