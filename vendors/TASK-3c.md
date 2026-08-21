# TASK-3c：人聲突顯自適應 VAD（VoiceVAD）

* **日期**：2026-08-21
* **依據**：`vendors/PLAN-3c.md`
* **狀態**：待審（動工前）

## 實作項目

### Phase 1: VoiceVAD 核心類（`core/vad_filter.py`）
- [ ] `VoiceVAD` 類：分幀（30ms 幀/10ms 步進）＋ `np.hamming` ＋ `np.fft.rfft` 帶內 RMS（300–3400Hz，Parseval 挑 bin）＋ 帶內噪底 EMA（僅非語音幀更新）＋ SNR 滯回狀態機（k_on=3.0 / k_off=1.5、min_speech_ms=200 / release_ms=300）
- [ ] `EnergyVAD` 原封不動（保命符完好）
- [ ] 合成訊號單元自檢：440Hz 正弦觸發／白噪不觸發／低頻 rumble（<300Hz）不觸發／短脈衝（<100ms）不觸發／EMA 防污染（噪底不被語音養肥）
- [ ] 既有 pos/neg fixtures 跑帶內統計，確認 ESP32 語料判別比成立
- [ ] `python3 -m py_compile` 通過

### Phase 2: Worker 整合與開關
- [ ] `voice_worker.py`：L0 AND L1 總閘 + `vad.voice.enabled` flag + VoiceVAD 例外自動退回純 L0（log 警告）
- [ ] `config.yaml` / `tests/fixtures/config_test.yaml` 加 `voice:` 段
- [ ] 相容性測試：無 `voice:` 段的 config 行為與現行逐 bit 一致

### Phase 3: Fixtures 補錄與測試擴充
- [ ] 使用者補錄三支 wav（ESP32 INMP441 同規格）：風扇聲 3s／敲擊桌麥 3s／遠距離正常說話 3s，純拷貝零加工
- [ ] `tests/test_voice_pipeline_e2e.py` 擴充：新 fixtures 對應「風扇不觸發／敲擊不觸發／遠講觸發」
- [ ] 全套件 `--forked` 綠

### Phase 4: 真機 soak test 與 L0 下修評估
- [ ] 執行生產端 soak test（動作劇本已於對話備妥：測試一至四自我標記法）
- [ ] 依實測數據評估 `vad.threshold` 21000 下修空間（目標概念：≈2× 圖書館底噪）
- [ ] （選）ZCR 第三特徵評估：若帶通＋持續性仍有漏網場景

### Phase 5: 文件與版號
- [ ] MEMOIR 新增本任務記錄（含 edge 對比分析與移植決策）
- [ ] SPEC §2 VAD 段更新雙層架構；CHANGELOG 條目；`project_version` 遞增
- [ ] version-sync-check 通過
- [ ] （遠程）Python 原型驗證結論回饋 esp-miao edge 端 C 實作

## 驗收標準
- [ ] `EnergyVAD` 行為零變更
- [ ] 無 `voice:` 段 config 行為與現行完全一致
- [ ] 合成訊號＋fixtures 測試全綠：風扇/敲擊不觸發、正弦/語音觸發
- [ ] 全套件 `--forked` 綠

## 實際改動量

| 檔案 | 新增 | 刪改 | 說明 |
|------|------|------|------|
| （完工後填寫） | | | |

## 踩坑紀錄
- （完工後填寫）
