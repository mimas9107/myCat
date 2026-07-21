# 實作任務分配：myCat 語音動畫反應整合 (TASK-1b)

本文件將 `PLAN-1b.md` 的架構規劃拆解為具體可執行的 Agent Tasks。每個任務邊界明確，可依序獨立開發。

---

### [Task 1] 建立 VoiceAnimationController 骨架
* **目標**：新建 `mycat/voice_animation.py`，實作 `VoiceAnimationController` 類別的基本結構。
* **實作細項**：
  - [x] 建立 `mycat/voice_animation.py` 檔案
  - [x] 定義 `VoiceAnimationController(QObject)` 類別，接收 `window` 與 `voice_worker` 參數
  - [x] 在 `__init__` 中連接 `voice_worker.status_changed_signal` 與 `voice_worker.intent_detected_signal`
  - [x] 定義 overlay 狀態屬性：`_overlay_type`, `_overlay_start`, `_overlay_duration`, `has_active_overlay`
  - [x] 實作 `_on_status(status: str)` slot（暂時只 log）
  - [x] 實作 `_on_intent(intent: dict)` slot（暂時只 log）

### [Task 2] 實作程序化 Overlay 動畫
* **目標**：在 `VoiceAnimationController` 中實作各語音事件對應的程序化變形。
* **實作細項**：
  - [x] 實作 `_trigger_overlay(overlay_type, duration)` 方法：設定 overlay 狀態並 log
  - [x] 實作 `_overlay_params()` 方法：根據 overlay_type 與經過時間回傳 `(sx, sy, dx, dy, dim)` 元組
    - `"wake"`: `sy` 從 1.15 回彈至 1.0，`dy` 從 -15 回彈至 0（ease-out）
    - `"think"`: `sx=0.95, dx=+5`（靜態保持）
    - `"react"`: `dy` 從 -10 回彈至 0（彈跳）
  - [x] 實作 `apply_overlay(painter, x, y)` 方法：呼叫 `_overlay_params()`，用 `painter.save/translate/scale/restore` 套用變形
  - [x] 實作 overlay 過期自動清除（`has_active_overlay` 在超時後回傳 False）

### [Task 3] 串接 VoiceWorker Signal
* **目標**：讓 `_on_status` 與 `_on_intent` 根據訊號類型觸發對應 overlay。
* **實作細項**：
  - [x] `_on_status("WAKE_WORD_TRIGGERED")` → `_trigger_overlay("wake", 0.8)`
  - [x] `_on_status("TRANSCRIBING")` → `_trigger_overlay("think", 1.5)`
  - [x] `_on_status("LISTENING")` → 清除 overlay（設 `_overlay_type = None`）
  - [x] `_on_intent({"type": "CHAT"})` → `_trigger_overlay("react", 0.5)`
  - [x] `_on_intent({"type": "SET_REMINDER"})` → `_trigger_overlay("react", 0.5)`
  - [x] `_on_intent({"type": "SLEEP"})` → 不走 overlay，留给 main.py 處理（見 Task 5）

### [Task 4] main.py 掛鉤：啟動 Controller 與 render 掛鉤
* **目標**：在 `main.py` 中以最少改動串接 `VoiceAnimationController`。
* **實作細項**：
  - [x] 在 `PixelCatWindow.__init__` 的 voice_worker 啟動區塊後，import 並實例化 `VoiceAnimationController`
  - [x] 在 `_pack_tick()` 尾端加入：`elif getattr(self, "voice_anim", None) and self.voice_anim.has_active_overlay: self.update()`
  - [x] 在 `paintEvent()` 的 `drawPixmap(x, y, self.current_pixmap)` 後，呼叫 `self.voice_anim.apply_overlay(painter, x, y)`（若有 voice_anim）
  - [x] 確認改動行數不超過 10 行

### [Task 5] 修正 SLEEP Intent 行為
* **目標**：將 `_on_voice_intent_detected` 中的 `SLEEP` 行為從 `self.close()` 改為觸發 sleep 動畫。
* **實作細項**：
  - [x] 當 `char_pack is not None` 且具備 sleep 能力（`pack.sleep is not None` 或 `pack.sleep_in is not None`）時，觸發 sleep 動畫流程
  - [x] 否則（無 CharPack 或無 sleep 素材）維持原有的 `self.close()` 行為
  - [x] 以 `# 註解掉` 原始 `self.close()` 為主，新邏輯寫在下方

### [Task 6] 驗證與 Debug
* **目標**：確認所有語音事件能正確觸發貓咪動畫反應。
* **實作細項**：
  - [x] 確認語法檢查通過（`py_compile`）
  - [x] 確認 `_fsm_debug_tick` 的 log 中能看到 overlay 觸發訊息
  - [x] 確認 overlay 不干扰既有的 blink/eye-tracking 狀態機
  - [x] 確認 SLEEP intent 在有/無 CharPack 時的行為差異
