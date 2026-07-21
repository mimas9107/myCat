# 專案架構規劃：myCat 語音動畫反應整合 (PLAN-1b)

## 1. 架構總覽
本計畫旨在將 `VoiceWorker` 的語音事件 (`status_changed_signal` / `intent_detected_signal`) 與貓咪的 CharPack 狀態機連動，使貓咪能以**程序化視覺反應**回應語音互動。
採用「獨立 Controller」模式：新建 `mycat/voice_animation.py` 作為語音→動畫的橋接層，`main.py` 僅需最少的啟動與渲染掛鉤。

## 2. 設計原則
* **最小侵入 (Minimal Intrusion)**：`main.py` 的改動控制在 ~10 行以內（啟動 controller + paintEvent 掛鉤 + SLEEP intent 修正）。
* **零新素材依賴**：所有反應動畫透過 QPainter 程序化變形（scale/translate/dim）實現，不需要額外的 GIF 或 PNG。
* **與 CharPack 狀態機共存**：voice overlay 為「一次性覆蓋」，不修改 `base_state` 或 `active_clip`，不干扰既有的 blink/sleep/yawn 流程。
* **線程安全**：`VoiceWorker` 在 QThread 中 emit signal，Qt 的 auto-connection 確保 controller 的 slot 在 Main Thread 執行。

## 3. 目錄結構
```text
[myCat root]/
├── mycat/
│   ├── main.py                 # 改動：啟動 controller + paintEvent 掛鉤 + SLEEP 修正
│   ├── voice_animation.py      # 【新增】語音動畫 Controller
│   └── voice_assistant/        # 不動
│       ├── voice_worker.py
│       └── core/
```

## 4. VoiceAnimationController 設計

### 4.1 介面
```python
class VoiceAnimationController(QObject):
    def __init__(self, window: PixelCatWindow, voice_worker: VoiceWorker)
    def apply_overlay(self, painter: QPainter, x: int, y: int) -> None  # paintEvent 呼叫
    @property
    def has_active_overlay(self) -> bool  # _pack_tick 用來決定是否強制重繪
```

### 4.2 Signal → 動畫映射

| VoiceWorker 訊號 | overlay 類型 | 程序化變形 | 持續時間 |
|---|---|---|---|
| `WAKE_WORD_TRIGGERED` | `"wake"` | `sy=1.15, dy=-15` (彈跳膨脹) | 0.8s |
| `TRANSCRIBING` | `"think"` | `sx=0.95, dx=+5` (微微歪頭) | 1.5s |
| `LISTENING` | `None` (清除) | — | — |
| intent `SLEEP` | 設 `base_state="sleeping"` | 不走 overlay，直接操作狀態機 | — |
| intent `CHAT` | `"react"` | `dy=-10, sy=1.08` (小彈跳) | 0.5s |
| intent `SET_REMINDER` | `"react"` | 同 CHAT | 0.5s |

### 4.3 渲染機制
`apply_overlay()` 在 `paintEvent` 的 `drawPixmap` 前後呼叫：
```python
painter.save()
painter.translate(x + width/2, y + height)  # 底部中心锚点
painter.scale(overlay_sx, overlay_sy)
painter.translate(-(x + width/2), -(y + height))
painter.drawPixmap(x, y, window.current_pixmap)
painter.restore()
# overlay dim/tint 用 CompositionMode_SourceAtop 叠加
```

### 4.4 SLEEP Intent 修正
原 `_on_voice_intent_detected` 收到 `SLEEP` 時執行 `self.close()`。
修正為：若有 CharPack 且具 sleep 能力，觸發 sleep 動畫；否则維持 close()。
```python
if intent_type == "SLEEP":
    if self.char_pack is not None:
        # 觸發 sleep 動畫（sleep_in 或直接進 sleeping）
        ...
    else:
        self.close()
```

## 5. main.py 改動點

| 位置 | 改動 | 行數 |
|---|---|---|
| `__init__` voice_worker 啟動後 | `from mycat.voice_animation import VoiceAnimationController; self.voice_anim = VoiceAnimationController(self, self.voice_worker)` | 2 |
| `_pack_tick` 尾端 | `if self.voice_anim.has_active_overlay: self.update()` | 1 |
| `paintEvent` drawPixmap 前 | `if getattr(self, 'voice_anim', None): self.voice_anim.apply_overlay(painter, x, y)` | 1 |
| `_on_voice_intent_detected` SLEEP | 改為觸發 sleep 動畫而非 `self.close()` | ~5 |
| **合計** | | **~9 行** |

## 6. 不動的檔案
* `mycat/voice_assistant/voice_worker.py` — signal 定義不變
* `mycat/voice_assistant/core/*` — 全部不動
* `mycat/char_pack.py` — 狀態機不變
