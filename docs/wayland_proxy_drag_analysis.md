# 技術分析：Wayland 下「代理拖曳」繞道方案

## 🎯 核心問題

> 能否用一個代理來假裝是使用者在拖曳視窗，達到程式化移動效果？

**短答案**：模擬使用者拖曳 ❌ 不可行，但 Compositor IPC 直接移動 ✅ 可行（特定 compositor 限定）。

---

## 四條技術路線分析

### 路線 A：ydotool + startSystemMove() 假拖曳

**構想**：用 `ydotool`（透過 `/dev/uinput` 注入核心層輸入事件）模擬滑鼠按下 → 觸發 `startSystemMove()` → `ydotool` 移動滑鼠 → 釋放

**為什麼不行**：

```
使用者按下滑鼠 ──→ compositor 收到 pointer grab
                      ↓
              startSystemMove() ──→ compositor 接管拖曳
                      ↓
              compositor 跟隨真實指標移動視窗
                      ↓
              使用者放開 ──→ 拖曳結束
```

問題在第一步：

1. **`startSystemMove()` 需要合法的 input serial**：Wayland compositor 驗證「這個 move 請求是否來自真實的使用者互動事件」。`ydotool` 注入的事件雖然在核心層是「真實的」，但 `startSystemMove()` 必須在 **Qt 的 `mousePressEvent` 處理鏈** 中被呼叫，時序耦合極緊。

2. **控制權問題**：一旦 `startSystemMove()` 成功，compositor **完全接管**指標。你的程式失去對視窗位置的控制——視窗跟著真實滑鼠游標走，而不是你想要的目標座標。

3. **使用者體驗災難**：使用者會看到滑鼠游標被「劫持」，貓黏著游標跑，直到模擬釋放。

> [!CAUTION]
> **結論：路線 A 不可行。** `ydotool` 能注入輸入事件，但無法控制 compositor 接管後的視窗目標位置。而且會搶走使用者的滑鼠控制權。

---

### 路線 B：Compositor IPC 直接移動 ⭐ 推薦

**構想**：不模擬拖曳，直接透過 compositor 的 IPC 通道命令它移動視窗。

#### Sway（我們主要的 Wayland 環境）

```bash
# 先設為 floating，再移動到絕對座標
swaymsg '[app_id="mycat"] floating enable'
swaymsg '[app_id="mycat"] move absolute position 500 300'
```

- ✅ 精確控制 X/Y 座標
- ✅ 不影響使用者滑鼠
- ✅ 可用 `i3ipc-python` 庫從 Python 直接呼叫
- ⚠️ 視窗必須處於 **floating** 模式（桌面寵物本來就是 floating）

#### Hyprland

```bash
# 移動當前活動視窗到精確座標
hyprctl dispatch moveactive exact 500 300

# 或移動特定視窗
hyprctl dispatch movewindowpixel exact 500 300,address:0x...
```

- ✅ 同樣精確
- ✅ 支援非活動視窗移動

#### GNOME Wayland（最困難）

GNOME 沒有原生 CLI 工具，需要：

1. 安裝 GNOME Shell Extension（如 `Window Calls` 或 `ws-dbus`）
2. Extension 內部透過 `MetaWindow.move_resize_frame()` 移動
3. 外部程式透過 DBus 呼叫 Extension

```bash
# 透過 Window Calls extension 的 DBus 介面
gdbus call --session \
  --dest org.gnome.Shell \
  --object-path /org/gnome/Shell/Extensions/WindowCalls \
  --method org.gnome.Shell.Extensions.WindowCalls.MoveResize \
  <window_id> 500 300 200 200
```

- ⚠️ 依賴使用者安裝 Extension
- ⚠️ Extension API 跨 GNOME 版本不穩定
- ❌ 我們已知 GNOME Wayland 問題最多（`mapToGlobal` = `(0,0)`）

#### KDE Plasma

```bash
# KWin 腳本 或 DBus
qdbus org.kde.KWin /KWin org.kde.KWin.setWindowGeometry <id> 500 300 200 200
```

> [!TIP]
> **結論：路線 B 是唯一務實的方案。** 但必須按 compositor 分策略實作。我們的 `_detect_compositor()` 已能偵測環境，可以直接復用。

---

### 路線 C：wlr-layer-shell 圖層方案

**構想**：不用 `xdg_toplevel`（普通視窗），改用 `wlr-layer-shell` 協定把貓渲染為螢幕覆蓋層。

```
wlr-layer-shell 允許：
✅ 指定精確的螢幕座標（margins + anchor）
✅ 不受 compositor 視窗管理限制
✅ 永遠浮在最上層（或最下層）
```

**問題**：

- ❌ 僅 wlroots 系 compositor 支援（Sway、Hyprland）；GNOME 不支援
- ❌ PySide6/Qt 沒有原生 `wlr-layer-shell` 支援，需要用 `python-wayland` 或 `gtk4-layer-shell`
- ❌ 會完全改變視窗性質（不再是普通視窗，無法被 Alt+Tab 切換）
- ❌ 架構改動太大

> [!WARNING]
> **結論：路線 C 理論上最精確，但改動量太大且跨平台覆蓋不足。** 可作為未來「桌面寵物 2.0」的研究方向，但不適合現階段整合。

---

### 路線 D：混合動畫方案（視窗內移動）

**構想**：不移動視窗，而是在一個**全螢幕透明視窗**內移動貓的繪製位置。

```
┌─ 全螢幕透明視窗 (固定位置) ─────────────────┐
│                                              │
│         🐱 ← 在 paintEvent 中改變繪製座標     │
│              (自由移動，無需移動視窗)          │
│                                              │
└──────────────────────────────────────────────┘
```

**優勢**：
- ✅ 完全跨平台，不依賴 compositor IPC
- ✅ QPainter 座標控制，毫秒級精度
- ✅ 與現有 `voice_animation.py` 架構相容

**問題**：
- ⚠️ 全螢幕透明視窗可能被 compositor 特殊處理
- ⚠️ 滑鼠事件穿透需要特殊處理（`Qt.WA_TransparentForMouseEvents`）
- ⚠️ 多螢幕場景需要額外處理
- ⚠️ Wayland 下透明全螢幕視窗的行為未必可靠

---

## 📊 路線對比

```
┌────────┬──────────┬──────────┬───────────┬──────────┬────────────┐
│ 路線   │ 可行性   │ 精確度   │ 跨平台    │ 改動量   │ 使用者體驗 │
├────────┼──────────┼──────────┼───────────┼──────────┼────────────┘
│ A 假拖曳│ ❌ 不可行 │ 無法控制 │ —         │ —        │ 災難       │
│ B IPC  │ ✅ 可行   │ 精確     │ 需分策略  │ 中       │ 流暢       │
│ C 圖層 │ 🟡 受限   │ 精確     │ 僅wlroots │ 大       │ 流暢       │
│ D 透明 │ 🟡 風險   │ 精確     │ 理論全平台│ 大       │ 流暢       │
└────────┴──────────┴──────────┴───────────┴──────────┴────────────┘
```

---

## 🏗️ 推薦整合方案：路線 B — Compositor IPC 策略模式

如果要在本分支實作，建議架構：

```mermaid
graph LR
    subgraph "CatMover (新模組)"
        DET["_detect_compositor()"] --> STRAT{策略選擇}
        STRAT -->|Sway| SWAY["SwayCatMover<br/>i3ipc-python"]
        STRAT -->|Hyprland| HYPR["HyprlandCatMover<br/>hyprctl subprocess"]
        STRAT -->|X11| X11["X11CatMover<br/>self.move(x, y)"]
        STRAT -->|GNOME| GNOME["GnomeCatMover<br/>DBus + Extension"]
        STRAT -->|fallback| FALL["StaticCatMover<br/>不移動，僅動畫"]
    end

    LLM["LLM Policy<br/>(現有 llm.py)"] -->|"MOVE_TO 500 300"| CatMover
    VOICE["VoiceBridge<br/>(現有)"] -->|"語音意圖"| LLM
```

### 與現有模組的對接

| 現有模組 | 角色 |
|---------|------|
| [`bubble_popup.py`](file:///home/mimas/project/REFERENCE/myCat/mycat/bubble_popup.py) `_detect_compositor()` | 直接復用，判斷走哪條策略 |
| [`wayland_drag.py`](file:///home/mimas/project/REFERENCE/myCat/mycat/wayland_drag.py) | 保留使用者手動拖曳功能，與自主移動共存 |
| [`voice_animation.py`](file:///home/mimas/project/REFERENCE/myCat/mycat/voice_animation.py) | 移動過程中疊加表情動畫 |
| [`llm.py`](file:///home/mimas/project/REFERENCE/myCat/mycat/llm.py) / [`llm_ollama.py`](file:///home/mimas/project/REFERENCE/myCat/mycat/llm_ollama.py) | LLM 生成移動指令 |
| [`core/intent_parser.py`](file:///home/mimas/project/REFERENCE/myCat/mycat/voice_assistant/core/intent_parser.py) | 擴展解析 `MOVE_TO` / `FOLLOW_MOUSE` 指令 |

### 關鍵前提

- **Sway 下貓視窗已經是 floating**（桌面寵物天然如此）→ `swaymsg move` 直接可用
- **我們的 `app_id`** 需要確認是否在 Sway 中可被 criteria 匹配
- **GNOME 降級**：在 GNOME Wayland 下放棄自主移動，保持現有靜態 + 語音互動

---

## 🔌 GNOME Wayland 專屬解決方案：myCatHelper 中轉設計

既然 GNOME 封鎖了外部直接移動視窗的管道，我們便需要像開發 `mpv_widget` 或其他媒體播放介面（註冊 MPRIS 協議）一樣，利用 **DBus** 作為與桌面環境通訊的雙向橋樑。

要讓 myCat 在 GNOME Wayland 下自主移動，最合規的設計就是透過一個 **GNOME Shell Extension (`myCatHelper`)** 來充當中轉代理。

### 1. 中轉架構設計

```
┌──────────────────────────────────────┐
│            myCat Python 核心         │
└──────────────────┬───────────────────┘
                   │ 透過 DBus 呼叫 (e.g., dbus-python)
                   ▼
┌──────────────────────────────────────┐
│  myCatHelper (GNOME Shell Extension) │ ◄── 運行在 GNOME Shell 進程內
└──────────────────┬───────────────────┘
                   │ 呼叫 Mutter 內部 JS API
                   ▼
┌──────────────────────────────────────┐
│  Mutter (GNOME Wayland Compositor)   │
└──────────────────────────────────────┘
```

### 2. 實作細節

1. **Extension 註冊服務**：
   在 Extension 啟動時（JavaScript/GJS），向 Session DBus 註冊一個專屬的接口（如 `org.gnome.Shell.Extensions.myCatHelper`），並暴露一個遠端方法：
   ```javascript
   // GJS 偽代碼：在 DBus 上暴露方法
   let myCatHelper = {
       MoveWindow: function(windowTitle, x, y) {
           let winActors = global.get_window_actors();
           for (let actor of winActors) {
               let win = actor.meta_window;
               if (win && win.get_title().includes(windowTitle)) {
                   win.move_resize_frame(true, x, y, win.get_width(), win.get_height());
                   return true;
               }
           }
           return false;
       }
   };
   ```

2. **Python 端調用**：
   當 `_detect_compositor()` 發現環境為 GNOME 且 Wayland 啟用時，改用 DBus 客戶端發送移動訊號：
   ```python
   # Python DBus 調用範例
   import dbus
   bus = dbus.SessionBus()
   obj = bus.get_object('org.gnome.Shell.Extensions.myCatHelper', '/org/gnome/Shell/Extensions/myCatHelper')
   helper = dbus.Interface(obj, 'org.gnome.Shell.Extensions.myCatHelper')
   helper.MoveWindow("myCat", 500, 300)
   ```

### 3. 部署策略選擇

* **A 方案：隨專案附帶專屬 Extension**
  將 `myCatHelper` 程式碼打包在專案中，在啟動偵測到 GNOME 時，提示並引導使用者安裝該 Extension。此方案整合度最高，使用者體驗最直覺。
* **B 方案：復用社群現成工具**
  要求使用者先從 GNOME 擴充套件商店安裝社群通用的 DBus 控制套件（如 `ws-dbus` 或 `Window Calls`），myCat 的 Python 程式碼直接去對接這些套件定義好的標準 DBus 介面。這樣能省去我們維護 GJS Extension 的成本。

---

## 📋 結論

> 「假裝使用者拖曳」這條路走不通——Wayland compositor 會完全接管指標控制，你無法指定目標座標。
>
> 但「不經過拖曳，直接命令 compositor 移動視窗」在不同環境下有各自合法的實現管道。這是一場與 Compositor 設計哲學的對話：
> - **Sway / Hyprland**：使用官方內建的 CLI / IPC Socket 通訊（極度友善）。
> - **KDE Plasma**：使用內建 KWin DBus 接口。
> - **GNOME Wayland**：必須透過 **Extension 註冊自訂 DBus 服務** 作為中轉，完成合法操控。
>
> 建議本專案採用 **Compositor IPC 策略模式**，在不同平台上加載對應的後端，而 GNOME 部分將此 `myCatHelper` 中轉機制列為中長期發展路線。

