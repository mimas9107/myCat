# Voice Assistant 語音調校指南

> 本文件提供 `config.yaml` 語音參數的完整說明與情境調校建議。
> 所有參數位於 `mycat/voice_assistant/config.yaml`。

---

## 架構概覽

語音觸發採**雙層閘門**架構（TASK-3c），觸發條件 = **L0 AND L1**：

```
麥克風 → L0 (RMS 能量) → L1 (人聲頻譜) → ASR 轉寫 → 意圖解析
              ↑                                    ↑
         絕對門檻                             頻譜 SNR 判定
        (擋靜音)                          (擋非人聲噪音)
```

- **L0 保命層**：純能量檢測，低於門檻 = 靜音，直接略過。
- **L1 人聲層**：帶通 300–3400Hz 頻譜分析 + 自適應噪底 + SNR 遲滯，判定「是否為人聲」。
- **重複抑制**（TASK-3d）：意圖 emit 後清空 buffer + lockout + L1 release 等待，防範同一句重複觸發。

L1 啟用時，L0 在多數環境形同常開（環境音常超門檻），**真正的靈敏度由 L1 的 `snr_on` 決定**。

---

## 參數完整說明

### 音訊輸入

| 參數 | 預設值 | 說明 | 調校建議 |
|------|--------|------|----------|
| `audio.sample_rate` | 16000 | 取樣率(Hz)。Whisper 標準為 16kHz | 一般不動 |
| `audio.chunk_duration_ms` | 100 | 每次送 VAD 的音訊長度(ms) | 一般不動。降低→反應快但不穩定 |
| `audio.buffer_seconds` | 3 | ring buffer 保留歷史音訊秒數 | 一般不動。增大→更多歷史但記憶體↑ |
| `audio.device_index` | null | 音訊裝置索引。null = 自動偵測 | 自動偵測失敗時手動指定（可用 `list_devices()` 查看） |

### L0 保命層（Energy VAD）

| 參數 | 預設值 | 說明 | 提高效果 | 降低效果 |
|------|--------|------|----------|----------|
| `vad.threshold` | 21000 | RMS 絕對門檻。低於此值判定為靜音 | 誤觸↓ 靈敏↓ | 誤觸↑ 靈敏↑ |

**校準方法**：觀看 log 中 `[vad] RMS=xxxx` 數值，環境底噪的 RMS × 2~3 為安全門檻。以 think 動畫誤觸發頻率為最終調校指標。每台機器/麥克風不同，需個別校準。

> 注意：L1 啟用時 L0 在多數環境形同常開。門檻的主要作用是擋靜音與極低能量訊號，不需要精確校準。

### L1 人聲層（VoiceVAD）

| 參數 | 預設值 | 說明 | 提高效果 | 降低效果 |
|------|--------|------|----------|----------|
| `voice.enabled` | true | 開關。`false` 或整段刪除 = 純 L0 舊行為 | — | — |
| `voice.snr_on` | 2.25 | **觸發 SNR 門檻**。帶內能量÷噪底 ≥ 此值才判定人聲 | 遠講↓ 噪音↓ | 遠講↑ 噪音↑ |
| `voice.snr_off` | 1.5 | **釋放 SNR 門檻**。低於此值 + 持續 release_ms → 判定語音結束 | 釋放更快 | 釋放更慢 |
| `voice.min_speech_ms` | 200 | 最短語音持續時間(ms)。短於此不觸發 | 拒斥短促音↑ | 靈敏↑ |
| `voice.release_ms` | 300 | 語音結束判定等待(ms)。沉默持續此時間才釋放 | 斷句更寬容 | 斷句更嚴格 |
| `voice.freq_min` | 300 | 帶通下界(Hz)。300Hz 以下 = 哼聲/rumble | 擋更多低頻 | 放行更多低頻 |
| `voice.freq_max` | 3400 | 帶通上界(Hz)。3400Hz 以上 = 摩擦音/嘶聲 | 放行更多高頻 | 擋更多高頻 |
| `voice.floor_alpha` | 0.01 | 噪底 EMA 更新速率。越大→噪底跟隨環境越快 | 適應快但不穩 | 適應慢但穩定 |
| `voice.smooth_alpha` | 0.3 | Frame-level SNR 平滑。越大→分數越穩定 | SNR 穩定但延遲 | SNR 反應快但跳動 |

**`snr_on` 是最核心的旋鈕**：決定「多少 SNR 才算有人說話」。環境噪音多→調高(2.5~3.0)；需要遠距離喚醒→調低(1.8~2.0)。

**`snr_on` 與 `snr_off` 構成遲滯帶**：差距越大→狀態越穩定（不頻繁跳動）。一般保持 snr_off 比 snr_on 低 0.5~0.75。

### 重複抑制（Retrigger Suppression）

| 參數 | 預設值 | 說明 | 提高效果 | 降低效果 |
|------|--------|------|----------|----------|
| `retrigger_lockout_ms` | 1500 | 意圖 emit 後的冷卻鎖定(ms) | 鎖更久 | 解鎖更快 |
| `rearm_max_wait_ms` | 10000 | rearm 最長等待上限(ms)。cap 到期強制解除 | cap 更長 | cap 更短 |

**rearm 機制**：意圖 emit 後 (1) 清空 ring buffer；(2) 進入 lockout；(3) lockout 到期 AND（L1 released OR cap 到期）後才重新武裝。

`rearm_max_wait_ms` 一般不需改，除非 L1 在特定環境永不釋放（如持續有背景噪音讓 `speaking` 維持 True）→ 調低避免卡死。

### ASR 語音辨識

| 參數 | 預設值 | 說明 | 調校建議 |
|------|--------|------|----------|
| `asr.model_size` | base | Whisper 模型大小。tiny/base/small/medium/large | CPU 弱→tiny；需要中文→medium |
| `asr.language` | en | 指定語言。null = 自動偵測 | 主要用中文→設 "zh" 提升速度與準確度 |
| `asr.drop_after_warmup_sec` | 5.0 | 啟動後前 N 秒的 ASR 結果被丟棄 | 模型載入慢→調高；快速啟動→調低(2~3) |

### 疊圖與喚醒

| 參數 | 預設值 | 說明 | 調校建議 |
|------|--------|------|----------|
| `overlay.enabled` | true | 語音動畫疊圖開關 | — |
| `overlay.idle_yawn_after` | 30 | 靜默多久打哈欠(秒)。0 = 關閉 | 依個人喜好 |
| `wake_word.enabled` | false | 喚醒詞開關 | 需要語音喚醒→開啟 |
| `wake_word.threshold` | 0.8 | 喚醒詞信心門檻(0~1) | 誤觸多→調高(0.85~0.9)；反應差→調低(0.6~0.7) |

---

## 情境快速調校

### 噪音環境（風扇/冷氣/街道）

| 調什麼 | 怎麼調 | 原因 |
|--------|--------|------|
| `voice.snr_on` | 2.25 → 2.5~3.0 | 提高 SNR 門檻，只讓人聲通過 |
| `voice.freq_min` | 300 → 400~500 | 擋掉更多低頻 rumble（風扇/冷氣） |
| `voice.min_speech_ms` | 200 → 300 | 拒斥更短的噪音脈衝 |

### 遠距離喚醒（1m+）

| 調什麼 | 怎麼調 | 原因 |
|--------|--------|------|
| `voice.snr_on` | 2.25 → 1.8~2.0 | 降低門檻，接受較弱的人聲訊號 |
| `vad.threshold` | 21000 → 15000~18000 | 遠講能量低，L0 門檻也要配合降低 |
| `voice.release_ms` | 300 → 400~500 | 遠講尾音衰減慢，給予更多釋放時間 |

### 快速連續指令

| 調什麼 | 怎麼調 | 原因 |
|--------|--------|------|
| `voice.release_ms` | 300 → 150~200 | 更快判定語音結束，縮短指令間隔 |
| `retrigger_lockout_ms` | 1500 → 800~1000 | 更快解除冷卻，準備接收下一句 |

### 語速慢 / 長停頓

| 調什麼 | 怎麼調 | 原因 |
|--------|--------|------|
| `voice.release_ms` | 300 → 500~800 | 長停頓不被誤判為語音結束 |
| `retrigger_lockout_ms` | 1500 → 2000~3000 | 避免慢語速被切斷後立即重觸發 |

### 敲擊 / 鍵盤誤觸

| 調什麼 | 怎麼調 | 原因 |
|--------|--------|------|
| `voice.min_speech_ms` | 200 → 300~500 | 敲擊/鍵盤持續時間短，提高門檻拒斥 |
| `voice.snr_on` | 2.25 → 2.5 | 敲擊 SNR 通常不高，提高門檻過濾 |

### CPU 弱 / 筆電省電

| 調什麼 | 怎麼調 | 原因 |
|--------|--------|------|
| `asr.model_size` | base → tiny | 模型更小，推論更快（犧牲準確度） |
| `asr.language` | en → "zh" | 跳過語言偵測，減少計算 |

### 純中文環境

| 調什麼 | 怎麼調 | 原因 |
|--------|--------|------|
| `asr.language` | en → "zh" | 跳過語言偵測，提升速度與準確度 |
| `asr.model_size` | base → medium | 中文模型需要更大容量（如有足夠 RAM） |

---

## 除錯技巧

### 觀察 L0/L1 行為

啟動時加上 log 等級可看到即時 VAD 數據：

```bash
LOG_LEVEL=DEBUG python3 -m mycat.main
```

關鍵 log 訊息：
- `[vad] RMS=xxxx (threshold=xxxx)` — L0 能量值
- `[voice-vad] VETO score=x.xx floor=xxxx` — L1 拒絕（score < snr_on）
- `[vad] TRIGGER! RMS=xxxx` — L0 + L1 同時通過
- `[asr] transcribing x.xs audio...` — 進入 ASR 轉寫
- `[rearm] entered / armed again` — 重複抑制狀態

### 常見問題診斷

| 症狀 | 可能原因 | 調整方向 |
|------|----------|----------|
| think 動畫頻繁誤觸 | L0 門檻過低 或 L1 snr_on 過低 | `threshold`↑ 或 `snr_on`↑ |
| 大聲說話沒反應 | 門檻過高 或 snr_on 過高 | `threshold`↓ 或 `snr_on`↓ |
| 遠講不靈敏 | snr_on 過高 或 threshold 過高 | `snr_on`↓, `threshold`↓ |
| 同一句重複觸發 | rearm 未生效（應已修復） | 確認 `voice_worker.py` 有 `clear_buffer()` |
| ASR 結果為幻覺詞(如". . . .") | 靜音/噪音被送入 ASR | `snr_on`↑ 或 `min_speech_ms`↑ |
| L1 永不釋放（cap 才解除） | 背景噪音 SNR 持續偏高 | `snr_off`↓ 或 `floor_alpha`↑ |
