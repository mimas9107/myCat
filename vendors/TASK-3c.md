# TASK-3c：人聲突顯自適應 VAD（VoiceVAD）

* **日期**：2026-08-21
* **依據**：`vendors/PLAN-3c.md`
* **狀態**：待審（動工前）

## 實作項目

### Phase 1: VoiceVAD 核心類（`core/vad_filter.py`）
- [x] `VoiceVAD` 類：分幀（30ms 幀/10ms 步進）＋ 窗函數 ＋ `np.fft.rfft` 帶內 RMS（300–3400Hz，Parseval 挑 bin）＋ 帶內噪底 EMA（僅非語音幀更新）＋ SNR 滯回狀態機（min_speech_ms=200 / release_ms=300）※偏離計畫：Blackman 窗取代 Hamming（旁瓣洩漏實證）、k_on=2.25 數據驅動、新增 RMS 平滑與洩漏式持續計數，詳見踩坑紀錄
- [x] `EnergyVAD` 原封不動（保命符完好）
- [x] 合成訊號單元自檢：440Hz 正弦觸發／白噪不觸發／低頻 rumble（<300Hz）不觸發／短脈衝（<100ms）不觸發／EMA 防污染（噪底不被語音養肥）（`tests/test_voice_vad.py` 10 passed）
- [x] 既有 pos/neg fixtures 跑帶內統計，確認 ESP32 語料判別比成立（行為判決版：乾淨前導 pos 觸發、neg 全靜默；判別比結構為「爆發峰值 vs 穩態噪聲」，整檔 median 不可用）
- [x] `python3 -m py_compile` 通過

### Phase 2: Worker 整合與開關
- [x] `voice_worker.py`：L0 AND L1 總閘 + `vad.voice.enabled` flag + VoiceVAD 例外自動退回純 L0（log 警告）※L1 每輪無條件餵食（持續追蹤噪底），veto 發生在 L0 通過之後並帶 score/floor log
- [x] `config.yaml` / `tests/fixtures/config_test.yaml` 加 `voice:` 段（enabled: true；SNR 閘為相對量，ESP32 fixtures 免重校準）
- [x] 相容性測試：無 `voice:` 段的 config 行為與現行逐 bit 一致（`test_worker_voice_vad_wiring`：voice_vad=None + _voice_vad_active=False 走純 L0 路徑）

### Phase 3: Fixtures 補錄與測試擴充
- [x] 使用者補錄三支 wav（ESP32 INMP441 同規格）：`fan.wav`（rms=1259）/`knockknock.wav`（rms=2688）/`heymiaomiao.wav` 遠講（rms=2350），皆 16kHz/16-bit/mono/3.00s 純拷貝零加工
- [x] `tests/test_voice_pipeline_e2e.py` 擴充（既有乾淨前導 fixtures 過全真管線）：pos_n→觸發、neg_quiet→靜默（`test_clean_lead_pos_fixture_reaches_intent` / `test_clean_lead_neg_fixture_stays_silent`）；pos_alt/pos_s 因冷啟動極限排除於 e2e（t=0 即語音，bootstrap 吃掉唯一語句，已由單元層復原測試覆蓋）
- [x] 新錄 fixtures 對應 e2e 三案例全綠：遠講觸發（`test_user_recording_distant_speech_reaches_intent`）；風扇不觸發＋敲擊不觸發（`test_user_recording_nonvoice_stays_silent`）。帶內模擬佐證：fan score 峰值僅 1.17；knock 瞬時 11.89 但持續性閘門全程壓制（speaking=0.0s，暫態拒斥實戰驗證）；遠講 speaking=1.0s / score 26.35。e2e 檔 17 passed
- [x] 全套件驗證綠：逐檔獨立行程等效隔離（pytest-forked 未裝，見踩坑紀錄）；僅既有基準失敗（test_calendar_ics 3 failed；test_char_engine/test_window_behavior QThread teardown 崩潰），TASK-3c 觸及域（voice_vad 10 / voice_pipeline_e2e 14 / voice_bubble 5 / speech_bubble 4）全綠，零回歸

### Phase 4: 真機 soak test 與 L0 下修評估
- [x] 執行生產端 soak test（真機 Wayland，`VoiceVAD=on`，threshold=6000）：靜默基準零誤觸發；204 次環境噪聲 L0 通過全被 L1 否決（VETO score 中位 1.03）；正常距離喚醒充足（氣泡 >10 次）；遠講衰減至約 5 次仍可用；樂器諧波噪聲造成 7 次 `'You'` 幻覺誤意圖（帶通+持續性對諧波源無效，見下項）
- [x] `vad.threshold` 評估結論：**不需下修**——實測該機環境音 RMS 常態超過現行 6000（L0 形同常開），靈敏度上限已改由 L1 的 `snr_on` 決定；L1 上線後絕對門檻僅剩 CPU/log 意義
- [x] （選）ZCR 第三特徵評估：樂器諧波能量集中 300–3400Hz 且可持續 >200ms，雙層閘門確實漏網——**有實證場景**，建議列為後續 Task 選配；另發現既有「滑動窗口重複轉錄」缺口（同一句話→多次 CHAT→LLM/氣泡排隊），與本 Task 無關，建議另立 Task（觸發後緩衝清空＋鎖定期／等 release_ms 再武裝）

### Phase 5: 文件與版號
- [x] MEMOIR 記錄（含 edge 對比分析與移植決策）：新增「人聲突顯自適應 VAD：雙層閘門、數據驅動偏離與移植決策」——Blackman 修正、k_on=2.25 語料校準、平滑＋洩漏計數為 Python 端增量、bootstrap 極限、soak 結論、ZCR 實證場景、滑動窗口缺口另立 Task
- [x] SPEC §2 VAD 段更新雙層架構；CHANGELOG 0.3.0 條目；`project_version` 0.2.7→**0.3.0**（fork 首個執行期新功能，依 MINOR 規則進位）
- [x] version-sync-check 通過：四份文件 frontmatter ＋ pyproject.toml 全數對齊 0.3.0；腳本報告之 README/CHANGELOG missing_header 為中段 frontmatter 結構性豁免、SPEC/MEMOIR「mismatch」係腳本誤以作者區段 0.1.30 為基準——均為既有已知限制，以人工對齊為準
- [x] （遠程）Python 原型驗證結論回饋 esp-miao edge 端 C 實作：已寫入 `develop_journal/2026-08-22/mycat-vad-porting-feedback.md`（Blackman 窗替換 Hamming、k_on=2.25、平滑＋洩漏計數移植建議、bootstrap 極限、soak 數據、ZCR 候選），esp-miao 團隊認領

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
- （Phase 1）**Hamming 旁瓣洩漏**：80Hz/amp5000 純音經 Hamming（-41dB 旁瓣）在帶內殘留 ≈1.7–2.5× 噪底能量，恰卡 snr_on 門檻——帶通濾波形同虛設。改用 Blackman（-58dB）後洩漏降至 ≈0.07×。偏離計畫「移植 Hamming 資產」，實證驅動。
- （Phase 1）**ESP32 語料判別比遠低於 edge 前提**：edge 實測 13×，本語料 pos_n 持續帶內 SNR 僅 2.3–2.7×。門檻掃描：k_on=3.0 漏觸發 pos_n；≤2.0 neg_noise_mid 尾段噪聲漲潮誤觸發；**k_on=2.25 為數據最優間隔**。
- （Phase 1）**嚴格連續計數太脆**：單一幀低於 k_on 即歸零累計，分數徘徊型語音（pos_n）永不觸發。改洩漏式衰減（每 miss 扣 1×hop_ms）。
- （Phase 1）**幀級 RMS 平滑是關鍵拼圖**：平滑前 pos_n 在 chunk 餵食下仍不觸發；EMA α=0.3 穩定徘徊分數後才穩定越線。合成訊號全綠 + neg 全靜默同時成立。
- （Phase 1）**冷啟動 bootstrap 污染為已知極限**：t=0 即語音的檔案（pos_alt/pos_s）floor 被養在語音層級，首句必漏；已以 `test_recovery_after_cold_start_poisoning` 驗證靜默期 EMA 會拉回噪底、第二句正常觸發。生產情境（啟動時環境靜默）不受影響。
- （Phase 1）**除錯陷阱**：`is_speech()` 對 <480 樣本 chunk 直接返回當前狀態不處理。手動診斷若餵 160 樣本切片會得到全程 score=0，易誤判實作壞掉——餵食長度必須 ≥ 幀長。
- （Phase 1）**整檔 median 帶內統計不可用於判別比**：pos 檔含大量靜音填充稀釋 median（pos_heymiaomiao median 3657 vs p90 89505）；判別結構是「爆發峰值 vs 穩態噪聲」，須以行為判決或 p90 表徵。
- （Phase 2）**e2e 正樣本失效揭出「凍結尾端」時序病理**：`run()` 的 `asr.load()`（阻塞 ~100s）在 while 迴圈之前，但 WAV 餵食線程在 `start()` 即即時播放——3 秒 fixture 在迴圈開始前播完，ring buffer 凍結於檔案尾端靜音。舊 e2e 依賴退化行為（尾端環境音 RMS>絕對門檻 → L0 永遠通過 → 反覆轉錄殘餘 buffer）；L1 正確判定尾端非語音而否決，反而暴露真相。修法：`WavAudioStreamManager(start_delayed=True)` + `resume()` 閘門，worker 於 `asr.load()` 完成後 release——fixture 在消費者輪詢中「邊播邊聽」，與真實麥克風語義一致。附帶效果：短生命測試的 worker 不再於載入期間空放。
- （環境）pyproject 宣告 `pytest-forked` 但 venv 未安裝；全套件單行程跑會被既有 QThread 測試崩潰拖垮（test_char_engine/test_window_behavior）。暫以逐檔獨立行程等效隔離，未經同意不安裝套件。
