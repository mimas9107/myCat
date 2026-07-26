---
name: "STAGE-1c.md"
description: "TASK-1c 最終狀態 — main.py 入侵分析"
created_date: "2026/07/26"
modified_date: "2026/07/26"
project_version: "0.2.0"
document_version: "1.0.0"
agent_sign: ['human/mimas', 'opencode/current']
---

# STAGE-1c: main.py 入侵分析

## 目標

TASK-1c 完成後，`main.py` 對語音相關模組 (`voice_bridge.py`, `wayland_drag.py`,
`voice_device_dialog.py`, `voice_animation.py`, `bubble_popup.py`, `mock_voice.py`,
`speech_bubble.py`, `voice_char_pack.py`) 的依賴應降至最低。

## 最終侵入點統計

```
voice_bridge.py       10 行
wayland_drag.py        2 行
──────────────────────────
總計                  12 行
```

## 逐行明細

### `voice_bridge.py` — 10 行

| 行 | 位置 | 內容 | 原因 |
|----|------|------|------|
| 642 | `__init__` | `from mycat.voice_bridge import VoiceBridge` | 延遲匯入 |
| 643 | `__init__` | `self.voice_bridge = VoiceBridge(self)` | 初始化橋接器 |
| 653 | `closeEvent` | `self.voice_bridge.shutdown()` | 關閉時停止語音執行緒 |
| 831 | `pack_tick` | `self.voice_bridge.should_repaint()` | 動畫定時器觸發重繪 |
| 1705 | `paintEvent` | `not self.voice_bridge.overlay_replaces_face` | 判斷覆蓋層是否取代貓臉 |
| 1707 | `paintEvent` | `self.voice_bridge.apply_paint(...)` | 繪製語音覆蓋層 |
| 1711 | `paintEvent` | `not self.voice_bridge.overlay_replaces_face` | pupils 只在未取代時繪製 |
| 1723 | `refresh_shape_mask` | `self.voice_bridge.is_bubble_active` | 遮罩管線整合氣泡區域 |
| 1769 | `_set_composite_mask` | `self.voice_bridge.get_bubble_bounds(...)` | 遮罩管線整合氣泡區域 |
| 2408 | `main()` | `window.voice_bridge.set_llm_backend(...)` | 後初始化 LLM 接線 |

以上 10 行均為 Qt 事件管線（paint / close / timer）的固有耦合，
無法進一步消除。

### `wayland_drag.py` — 2 行

| 行 | 位置 | 內容 | 原因 |
|----|------|------|------|
| 647 | `__init__` | `from mycat.wayland_drag import attach_wayland_drag_handler` | 延遲匯入 |
| 648 | `__init__` | `self.wayland_drag_handler = attach_wayland_drag_handler(self)` | 初始化拖曳插件 |

非語音相關，但屬於同一批加入的插件式模組。

## 已消除的侵入（相較 TASK-1c 初期）

| 項目 | 原先 | 現在 | 減少 |
|------|------|------|------|
| `mock_voice` / `test_wav` 建構子參數 | 2 params + 2 轉送 | 0（改為 env var） | -4 行 |
| `set_sleep_callback` / `set_reminder_callback` | 2 行 | 0（auto-wire） | -2 行 |
| `_trigger_sleep_animation()` 方法 | 16 行 | 0（搬入 VoiceBridge） | -16 行 |
| `_on_voice_intent_detected()` 方法 | 3 行 | 0（dead code） | -3 行 |
| `settings_ui.py` 內聯 UI | ~20 行 | 2 行（VoiceDeviceRow） | ~-18 行 |

## 結論

`main.py` 與語音模組的耦合已降至理論下限：
Qt 事件管線（paint / close / timer）的固有侵入無法避免，
其餘所有邏輯與資料都已封裝至對應模組。
