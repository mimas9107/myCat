# PLAN-3d：觸發後重複轉錄抑制（Retrigger Suppression）

* **日期**：2026-08-22
* **狀態**：草案待審
* **前置**：TASK-3c 完成（VoiceVAD 雙層閘門上線，0.3.0）；真機 soak 發現本缺口並裁示另立計畫；MEMOIR 已記錄完整診斷

## 1. 背景與動機

1. **問題本質**：`voice_worker.py` 的滑動緩衝（~2s 窗、0.1s 輪詢）在**意圖發出後沒有任何抑制機制**——緩衝不清空、無鎖定期、不等語音結束。下一輪輪詢時 L0/L1 對同一句話的殘餘音訊照樣通過 → 再次轉錄 → 再次發意圖。
2. **soak 實證**（2026-08-22，2598 行 log 分析）：一句 "hello" 產生 `'hello'` / `'hello hello'` / `'hello hello hello'` 三筆轉錄 → 三次 CHAT → LLM 呼叫 ×3 → 氣泡逐個排隊。3 分鐘 session 累積 37 次意圖，其中大量為同句重複。幻覺詞 'You'（樂器諧波所致）也以連發形式出現。
3. **既有變數名誤導**：`vad_cooldown` 實際只節流 `[vad]` RMS 日誌（每 2s 一條），與觸發節流無關。本計畫順帶正名。
4. **影響範圍**：所有意圖類型（CHAT/SLEEP/REMINDER），CHAT 因 LLM 成本與氣泡排隊最痛。

## 2. 方案對比

| 方案 | 機制 | 優點 | 缺點 |
|------|------|------|------|
| A 固定鎖定 | 觸發後 flush 緩衝＋T 秒禁再觸發 | 簡單確定性、與 VAD 種類無關、純 L0 模式也受益 | 截斷快速連續指令；持續說話鎖定到期後仍會再觸 |
| B 等語音結束 | 觸發後等 L1 speaking→released ≥ release_ms 才重新武裝 | 自然會話語義；長句不被腰斬 | 純 L0 模式無 L1 可依；持續人聲/樂器環境有永久閉鎖風險 |
| C 下游去重 | bubble/LLM 層合併相似意圖 | 不碰 worker | 治標不治本；LLM 成本照付；排隊延遲照舊 |

**決策**：採 **A+B 混合**。A 保證下限（任何模式都防重複），B 在 L1 存在時把「何時可以聽下一句」交給真實語音狀態而非拍腦袋常數；C 不做。

## 3. 核心設計

```
意圖 emit 後：
  1. audio_stream.clear_buffer()        # 清滑動緩衝；轉錄期間新進 chunk 保留，
                                        # 屬於「下一句」的前文，不清
  2. 進入 re-arm 狀態機：
     re-arm 條件 = lockout 到期 AND（L1 released OR 強制）
       - L1 active：等 speaking→released ≥ voice.release_ms（沿用既有參數）
       - L1 缺席（純 L0 fallback）：僅 lockout 計時
       - 強制：距觸發 ≥ rearm_max_wait_ms 時無條件武裝（防持續聲源永久閉鎖）

config 新增（vad: 段內，皆可省略＝預設值）：
  vad:
    retrigger_lockout_ms: 1500   # 觸發後最短靜默期
    rearm_max_wait_ms: 10000     # 強制重新武裝上限
```

* `clear_buffer()` 為 `AudioStreamManager` 新方法（基底＋WAV 子類行為一致）；ring/deque 的清空需與 feed 線串競爭安全。
* Energy VAD（L0）與 VoiceVAD（L1）內部**原封不動**——本計畫只動 worker 觸發路徑與緩衝管理。
* `vad_cooldown` 正名為 `rms_log_interval` 語義（或直接內聯常數＋註解），消除誤導。

## 4. Phase 劃分

### Phase 1: core 緩衝清空 API
* `AudioStreamManager.clear_buffer()` ＋ WAV 子類覆寫一致性；feed 線串併發安全驗證。

### Phase 2: worker re-arm 狀態機
* 意圖後流程改裝（flush → lockout → 等 release/cap）；config 讀取與預設值；純 L0 相容路徑。

### Phase 3: 測試
* e2e 計數斷言：pos fixture 完整播放**恰 1 次** CHAT（現況會多次）；間隔 ~1s 重播兩次 → 恰 2 次；全套件零回歸。

### Phase 4: 文件版號
* SPEC/MEMOIR/CHANGELOG/README 同步；版號遞增（性質判定於結案時：行為修正偏 PATCH，若含語義新增則 MINOR）。

## 5. 風險與緩解

| 風險 | 緩解 |
|------|------|
| lockout 太長傷害快速連續指令體驗 | 預設 1500ms 保守值可調；B 路徑讓真實語音結束即提前武裝 |
| 持續樂器/人聲環境 B 路徑永不釋放 | rearm_max_wait_ms 強制武裝 |
| flush 與 feed 線串競爭丟音 | 清空點在同步轉錄之後；轉錄期間新資料保留；Phase 1 併發測試 |
| 純 L0 使用者（無 voice 段）行為回歸 | lockout 為無條件底線，相容測試涵蓋 |

## 6. 驗收標準（DoD 摘要）

1. 同一段喚醒音源播放一次 → 恰一筆意圖（自動化 e2e 斷言）。
2. 真機 soak：單句不再連發；連續兩句正常各自觸發。
3. TASK-3c 既有 17 支 e2e 全數通過（零回歸）。
