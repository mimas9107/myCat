# PLAN-3c：人聲突顯自適應 VAD（VoiceVAD）

* **日期**：2026-08-21
* **狀態**：草案待審
* **前置**：TASK-3b 完成（WAV 注入式測試管線可複用）；MEMOIR 已固化門檻校準階梯；esp-miao v0.9.0 FFT VAD 對比分析已完成

## 1. 背景與動機

1. 生產門檻 `vad.threshold: 21000` 把「這台筆電的麥克風增益 × 圖書館環境」編碼進一個常數。換電腦/麥克風後兩種死法：靈敏度高 → 底噪永久誤觸發；遲鈍 → 大吼也不觸發（**靜默失敗**，使用者不知道有個數字要調）。
2. 使用者裁示三原則：
   * **保命符**：原始 RMS VAD 必須保留作為最基本防線；
   * **拓展人聲突顯機制**：朝人聲頻譜特徵方向建立魯棒性；
   * **選擇性取代高度**：門檻不必高，但要「更有選擇性地跨過」——底噪特徵值低、人聲特徵值飛高，如同一道人聲濾鏡。
3. esp-miao 對比分析結論：edge 端 2026-03-03 已實測驗證 300–3400Hz 帶內能量的判別比 ≈13 倍（同期全頻 RMS 僅 ≈4 倍），且開發筆記留有未完成待辦「加入自適應閾值機制」。本計畫即該待辦的 Python 域續工，未來可回饋 edge 端。

## 2. 三套既有實作對比（設計輸入）

| 維度 | myCat `EnergyVAD` | edge `vad.cpp`（FFT VAD） | edge 串流 VAD（MAE+ZCR） |
|------|------------------|--------------------------|--------------------------|
| 特徵域 | 時域全頻 RMS | 512點 FFT＋Hamming→帶內能量 | MAE＋過零率 |
| 判定 | 固定門檻 | 固定門檻 25000 | MAE<800 靜音；ZCR>0.10 判噪音 |
| 時間邏輯 | 無 | 無 | 靜音幀持續 3 幀才截斷 |
| 自適應 | 無 | EMA 有算但僅供顯示，未進決策 | 無 |

**移植資產**：Hamming 窗、300–3400Hz 邊界、`freq_min/freq_max` 命名、EMA 平滑係數（0.99/0.01）、串流 VAD 的幀持續概念。
**要避免的坑**：edge `fft_detect_` 只分析 buffer 前 512 點（多幀浪費）；EMA 未參與決策。myCat 版必須正確分幀、EMA 真正進閘門。

## 3. 核心設計：雙層閘門

```
chunk ──► Layer 0 保命符：EnergyVAD（原封不動，vad.threshold 絕對門檻）
     │
     └─► Layer 1 人聲濾鏡：VoiceVAD（新類）
           ├─ 分幀：30ms 幀（480 樣本）/ 10ms 步進，np.hamming(480)
           ├─ 特徵：np.fft.rfft → 300–3400Hz 帶內 RMS（Parseval，零新依賴）
           ├─ 自適應：帶內噪底 EMA（僅 score < k_off 的非語音幀更新，α=0.01）
           ├─ 分數：SNR = 帶內RMS / 帶內噪底
           └─ 狀態機：連續越線 ≥min_speech_ms 才觸發（k_on=3.0×噪底），
                      低於 k_off（1.5×噪底）≥release_ms 才釋放（滯回）

觸發 = L0 AND L1；VoiceVAD 任何例外 → 自動退回純 L0 行為（log 警告）
```

### 3.1 設計決策依據

* **k_on=3.0**：承襲 MEMOIR 7/22「底噪 3 倍」原則；edge 實測帶內判別比 13 倍，3 倍門檻兩側餘裕充足。
* **EMA 只吃非語音幀**：防止說話聲把噪底養肥（自適應 VAD 經典反饋污染死法）。
* **滯回雙門檻**：k_on 進/k_off 退，杜絕臨界抖動造成的 think 動畫閃爍。
* **持續性 ≥200ms**：敲擊瞬態（<100ms）直接陣亡；語音音節自然通過。
* **L0 降載是後話**：初期 L0 維持 21000（行為零變化），待 Phase 4 真機數據佐證後才評估下修至「絕對噪底安全線」（例如 2× 圖書館底噪 ≈13000），讓 L1 承擔選擇性。

### 3.2 Config 演進（向後相容）

```yaml
vad:
  threshold: 21000.0      # L0 保命符，語義不變
  voice:                  # 整段缺席 = 停用 L1，行為與現行完全一致
    enabled: true
    freq_min: 300         # 對齊 edge 命名
    freq_max: 3400
    snr_on: 3.0
    snr_off: 1.5
    min_speech_ms: 200
    release_ms: 300
    floor_alpha: 0.01
```

## 4. 測試矩陣

| 層級 | 輸入 | 預期 |
|------|------|------|
| 單元（合成訊號，確定性） | 440Hz 正弦 | 觸發 |
| 單元 | 白噪 | 不觸發 |
| 單元 | 低頻 rumble（<300Hz，模擬風切） | 不觸發 |
| 單元 | 短脈衝（<100ms） | 不觸發（持續性） |
| 單元 | EMA 污染防護：噪底後接語音 | 噪底不被養肥 |
| e2e（TASK-3b 管線延伸） | 既有 pos fixtures | 觸發（voice.enabled=true） |
| e2e | 既有 neg fixtures | 不觸發 |
| e2e | 新錄風扇/敲擊/遠講 wav | 不觸發 |
| 相容性 | 無 `voice:` 段的 config | 行為與現行逐 bit 一致 |

## 5. Fixtures 策略

* 既有 6 檔（pos×4/neg×2）不動，直接複用。
* **補錄三支**（需使用者配合，ESP32 INMP441 同規格）：風扇聲 3s、敲擊桌麥 3s、遠距離正常說話 3s。純拷貝零加工，沿用 TASK-3b 教訓。
* Phase 1 先用合成訊號與既有 fixtures 推進，補錄不阻塞前期開發。

## 6. 相位拆解

### Phase 1: VoiceVAD 核心類（`core/vad_filter.py`）
- [ ] `VoiceVAD` 類：分幀/Hamming/rfft/帶內 RMS/EMA/滯回狀態機
- [ ] `EnergyVAD` 原封不動；合成訊號單元自檢（上表前五列）
- [ ] 用既有 pos/neg fixtures 跑帶內統計，確認 ESP32 語料判別比成立
- [ ] `python3 -m py_compile` 通過

### Phase 2: Worker 整合與開關
- [ ] `voice_worker.py`：AND 閘 + `voice.enabled` flag + 例外退回 L0
- [ ] `config.yaml` / `tests/fixtures/config_test.yaml` 加 `voice:` 段
- [ ] 相容性測試：無 voice 段行為不變

### Phase 3: Fixtures 補錄與測試擴充
- [ ] 使用者補錄風扇/敲擊/遠講三支 wav
- [ ] `test_voice_pipeline_e2e.py` 擴充（上表 e2e 三列）
- [ ] 全套件 `--forked` 綠

### Phase 4: 真機 soak test 與 L0 下修評估
- [ ] 執行先前延後的生產端 soak test（劇本已備妥）
- [ ] 依實測數據評估 `vad.threshold` 21000 → 下修空間
- [ ] （選）ZCR 第三特徵評估：若帶通+持續性仍有漏網場景

### Phase 5: 文件與版號
- [ ] MEMOIR 記錄（含 edge 對比分析與移植決策）
- [ ] SPEC §2 VAD 段更新雙層架構；CHANGELOG 條目；`project_version` 遞增
- [ ] version-sync-check 通過
- [ ] （遠程）Python 原型驗證結論回饋 esp-miao edge 端 C 實作

## 7. 風險與緩解

| 風險 | 緩解 |
|------|------|
| EMA 被語音污染 | 僅 score<k_off 幀更新；單元測試專列一條 |
| ESP32 語料帶內判別比不如預期 | Phase 1 即驗證，不成立則先停在合成訊號層重新分析 |
| CPU 負擔 | rfft(480)×每 chunk 約 16 幀，量級微不足道；Phase 1 量測確認 |
| 行為回歸 | feature flag 預設關閉 + 相容性測試逐 bit 對照 |
| Qt 執行緒安全 | VoiceVAD 純運算無 UI 接觸，僅存於 worker thread |
