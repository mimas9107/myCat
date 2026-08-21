---
name: "MEMOIR.md"
description: "開發回憶錄與問題解法"
created_date: "2026/07/10"
modified_date: "2026/08/21"
project_version: "0.2.7"
document_version: "1.5.0"
agent_sign: ['human/mimas', 'opencode/current']
---

# 開發回憶錄與問題解法 (MEMOIR.md)

本文件用於記錄 `myCat` 語音增強專案在開發過程中遇到的重大決策、技術卡點與最終解決方案。

## 記錄清單

### [架構決策] 語音模組的放置位置與 UI 整合方式
* **日期**：開發初期 (計畫階段)
* **問題描述**：
  在規劃導入 `pyaudio`, `faster-whisper` 等高耗能語音套件時，面臨要將語音模組放在專案外 (`voice_assistant_node/`) 還是專案内 (`mycat/voice_assistant/`) 的架構抉擇。同時需解決語音處理的 `while` 迴圈會卡死 Qt 主執行緒的問題。
* **沙盤推演與考量**：
  * **方案 A (專案外)**：極致解耦，但面臨跨進程通訊 (IPC) 的複雜度，且極大增加打包 (`.exe`) 的難度。
  * **方案 B (專案內)**：打包簡單，但容易造成底層邏輯與 UI 耦合，且存在 Python GIL 潛在的微小卡頓風險。
* **最終解法 (折衷方案)**：
  1. 將語音套件放在 `mycat/voice_assistant/` 內，確保 PyInstaller 打包流程不受太大影響。
  2. 嚴格制定內部邊界：`core/` 目錄下絕對不允許出現 Qt 相關程式碼，保持純 Python 邏輯。
  3. 實作 `voice_worker.py` 作為中介層。該檔案繼承 `QThread`，將所有耗時語音操作封裝在背景執行緒中。
  4. 採用 **單向資料流**：背景執行緒將辨識出的「意圖 (Intent)」轉化為 Dictionary，並透過 Qt Signals (`intent_detected_signal`) 廣播給主 UI 執行。這完美避開了跨執行緒操作 UI 導致 Crash 的問題。

### [除錯與驗證] 未安裝 PyAudio 時的優雅降級與 CharPack 切換錯誤修正
* **日期**：實作完成後測試階段
* **問題描述**：
  1. 系統環境若未安裝 `pyaudio` 套件，`VoiceWorker` 啟動失敗。
  2. 使用者切換角色至互動式角色 (`cat` CharPack) 時，程式拋出 `AttributeError: 'NoneType' object has no attribute 'scaledSize'`。
* **解決方案**：
  1. **優雅降級 (Graceful Degrade)**：`PixelCatWindow` 在初始化 `VoiceWorker` 時加上 `try...except` 捕捉異常。若未安裝 `pyaudio` 或語音組件啟動失敗，僅印出警告 Log，貓咪主程式與原本的 Ollama/UI 功能依然順暢運作，不會造成崩潰。
  2. **CharPack 切換防禦**：修復 `main.py` 的 `_start_animation` 函數，補上 `if self.char_pack is not None or self.gif_movie is None: return` 防禦判斷，避免 CharPack 角色在沒有 `gif_movie` 物件時被誤觸發 scaledSize 導致報錯。

### [環境卡點] PyAudio 編譯失敗：缺少 portaudio.h
* **日期**：實作完成後安裝階段
* **問題描述**：
  執行 `pip3 install pyaudio` 時，編譯 C 擴充失敗，錯誤為 `fatal error: portaudio.h: 沒有此一檔案或目錄`。
* **根因**：
  `pyaudio` 是 PortAudio 的 Python binding，編譯時需要系統層級的 PortAudio 開發標頭檔 (`portaudio.h`)，但 Debian/Ubuntu 預設未安裝。
* **解法**：
  ```bash
  sudo apt install portaudio19-dev
  pip3 install pyaudio
  ```
* **架構影響**：
  這也再次驗證了將 `pyaudio` 放在 `pyproject.toml` 的 `[project.optional-dependencies] voice` 而非核心 `dependencies` 的正確性 — 避免一般使用者 `pip install mycat` 時因缺少系統開發套件而安裝失敗。

### [架構決策] 語音事件驅動貓咪動畫反應 (Voice Animation Overlay)
* **日期**：2026-07-21
* **問題描述**：
  `VoiceWorker` 已透過 Qt Signals 廣播 `status_changed_signal` 與 `intent_detected_signal`，但 `main.py` 的 handler 只做 log 或開啟 UI 視窗，完全沒有驅動貓咪的 CharPack 狀態機動畫。需要讓語音事件能觸發貓咪的視覺反應。
* **沙盤推演與考量**：
  * **方案 A (直接改 main.py)**：在 `_on_voice_status_changed` 與 `_on_voice_intent_detected` 中直接操作狀態機。改動分散且侵入性高。
  * **方案 B (獨立 Controller 模式)**：新建 `voice_animation.py`，controller 自行連接 voice_worker 的 signals，透過 QPainter 程序化變形（scale/translate）在 paintEvent 中疊加 overlay。main.py 只需 ~10 行掛鉤。
* **最終解法 (方案 B)**：
  1. 新建 `mycat/voice_animation.py`，實作 `VoiceAnimationController(QObject)`。
  2. Controller 在 `__init__` 中連接 `voice_worker.status_changed_signal` 與 `intent_detected_signal`。
  3. 收到信號後設定 overlay 狀態（type + duration），在 `apply_overlay()` 中用 `painter.save/translate/scale/restore` 做程序化變形。
  4. main.py 改動：(a) 實例化 controller (2行)、(b) `_pack_tick` 中 overlay 活躍時強制重繪 (1行)、(c) `paintEvent` 中呼叫 `apply_overlay` (1行)。
  5. SLEEP intent 從 `self.close()` 改為觸發 sleep 動畫（有素材時）或維持 close（無素材時）。
* **技術卡點**：
  * **QTimer 在 QThread 中的可靠性**：MockVoiceWorker 初版用 `QTimer` 物件在 QThread 中排程，信號未能穩定觸發。改用 `QTimer.singleShot` 遞迴排程後解決。
  * **SLEEP intent 的副作用**：Mock 測試時 SLEEP → close()、CHAT → 開聊天視窗、SET_REMINDER → 開提醒視窗，會干扰動畫測試。最終 mock 循環只保留 status 事件。

### [環境卡點] cat.zip 角色包缺少互動素材
* **日期**：2026-07-21
* **問題描述**：
  `cat.zip` 只包含 `static.png`、`blink.png`、`eye_left.png`、`eye_right.png`，完全沒有 `yawn.gif`、`sleep.png`、`sleep_in.gif`、`idle*.gif`、`click*.gif` 等素材。導致 CharPack 狀態機中 yawn、sleep、idle-random、click 反應全部因 `pack.xxx is None` 而跳過。
* **影響**：
  狀態機實際上只剩 `open↔blink` 切換與眼球追蹤。debug log 中所有 `pack.yawn=False`、`pack.sleep=False` 等條件檢查直接顯示素材缺失。
* **解法**：
  建立 debug logging 系統（`_fsm_debug_tick`）每3秒輸出完整條件檢查，確認是素材問題而非邏輯 bug。後續可透過更換有完整素材的角色包或 ComfyUI 生成管線來補齊。

### [架構決策] Wayland 原生視窗拖曳機制 (Wayland Drag Plugin)
* **日期**：2026-07-22
* **問題描述**：
  在 Wayland (Sway/wlroots 與 GNOME Wayland) 環境下，小貓出現在螢幕中央且無法用滑鼠拖曳移動。
* **根因分析**：
  1. **`self.move(x, y)` 限制**：Wayland (XDG-Shell) 協定為保護系統隱私與視窗管理，嚴格禁止 Client 端應用程式自主設定全域螢幕座標（`self.move()` 在原生 Wayland 下被直接忽略）。
  2. **`event.globalPosition()` 失效**：Wayland 下 `globalPosition()` 無法取得全域座標，僅回傳視窗內部相對座標，導致傳統 X11 拖曳算術公式失效。
* **核心原則與插件化解法**：
  * **原則**：盡量不更動 `main.py` 主線邏輯，維持原作者與社群開發的乾淨上游合併。
  * **解法**：建立獨立插件 `mycat/wayland_drag.py`，實作 `WaylandDragHandler(QObject)`。
  * 透過 `QObject.installEventFilter` 掛鉤 `PixelCatWindow` 的 `MouseButtonPress` 事件。
  * 點擊時呼叫 Qt 6 原生介面 `self.windowHandle().startSystemMove()`，將拖曳動作委派給 Wayland Compositor (Sway / Mutter)。
  * 拖曳結束時 `MouseButtonRelease` 自動捕捉並呼叫 `_save_position()` 儲存位置。
  * `main.py` 僅需在 `PixelCatWindow.__init__` 增加 5 行插件掛鉤程式碼，完全保留 X11 與上游主線邏輯。

### [環境卡點] VAD 音訊擷取：裝置選擇與采樣率相容性
* **日期**：2026-07-22
* **問題描述**：
  執行 VAD standalone 測試腳本 (`tests/test_vad.py`) 時，PyAudio 在 PulseAudio/PipeWire 環境下遇到多重問題：
  1. **raw ALSA 裝置不支援 16kHz**：`hw:1,0` (HDA Intel PCH ALC3232 Analog) 僅支援 44100Hz，開啟 16kHz stream 會拋出 `[Errno -9997] Invalid sample rate`。
  2. **PipeWire 裝置 64ch 相容問題**：PyAudio 開啟 PipeWire 裝置時可能 hang 或 crash。
  3. **VAD threshold 估算錯誤**：預設 threshold 1,000,000 太低，底噪即觸發；或太高（若單位誤判）導致永遠不觸發。
* **根因分析**：
  * 系統同時有 ALSA (card 1) + PulseAudio + PipeWire。PyAudio 裝置清單中 `[3]` 是 raw ALSA，`[5]` 是 pipewire，`[6]` 是 pulse。
  * Raw ALSA 由硬體直接控制，不支援采樣率轉換。PulseAudio/PipeWire 作為 virtual audio server，能自動處理采樣率轉換。
  * Energy VAD 計算的是 `sum(sample²)/len`（均方能量），16-bit PCM 正常說話約 10⁷~10⁸ 量級，底噪約 3×10⁶~5×10⁶。
* **解法**：
  1. **裝置選擇**：自動優先選用 PulseAudio 或 PipeWire 裝置（非 raw ALSA），它們支援 16kHz 採樣率轉換。
  2. **Threshold 調整**：觀察底噪約 3-5M，建議 threshold 設為底噪 3 倍 → **15,000,000**。
  3. **Path C（繞過 Wake Word）**：暫時跳過喚醒詞偵測，VAD 觸發後直接進 ASR，用於開發階段快速迭代。
  4. **Debug 工具**：建立 `tests/test_vad.py` standalone 腳本，自動選裝置、打印 energy/RMS/avg，並建議 threshold。
* **架構影響**：
  * `config.yaml` 的 `vad.threshold` 從預設 1,000,000 → 15,000,000。
  * `voice_worker.py` 新增 `vad_energy_signal` 供 UI 顯示能量條（可選）。
  * `voice_worker.py` 的 `run()` loop 改為 VAD → ASR（跳過 Wake Word），待模型就緒後切回。
  * `vad_filter.py` 新增 `get_energy()` 方法供 debug/外部顯示使用。

### [架構決策] English-first ASR + RMS-based VAD threshold 校準
* **日期**：2026-07-22
* **問題描述**：
  1. VAD threshold 單位不明確：原始 `energy²` (均方能量) 數值巨大（~10⁶~10⁷），不直觀。
  2. faster-whisper `base` 模型未指定語言，環境噪音被誤判為 `nn`（挪威語）。
  3. ASR 未經端到端驗證，無法確認完整管線可用。
* **解法**：
  1. **RMS-based threshold**：`vad_filter.py` 改用 `sqrt(sum²/N)`（Root Mean Square），threshold 從 `15,000,000`（energy²）→ `20,000`（RMS）。觀察底噪 RMS ~12,000-14,000，speech 觸發 ~20,000-24,000。
  2. **English-first**：`config.yaml` 新增 `language: "en"`，`asr_pipeline.py` 傳入 `language=self.language`。whisper 強制英文辨識，跳過中文/其他語言。
  3. **Intent parser 英文化**：`intent_parser.py` 加入英文關鍵字（remind, sleep, hide, shutdown），中文關鍵字保留但降為次要。
  4. **端到端驗證**：建立 `tests/test_asr_chain.py`，用 ALSA 測試音效 (`/usr/share/sounds/alsa/Front_Center.wav`) 餵入 ASR，成功辨識為 "Front, center."，intent 正確解析為 `CHAT`。
* **驗證結果**：
  ```
  VAD:  RMS=20,462 > threshold=20,000 → TRIGGER ✅
  ASR:  Front_Center.wav → "Front, center." ✅
  Intent: "front, center." → CHAT → data: {'text': 'front, center.'} ✅
  ```
* **架構影響**：
  * `audio_stream.py` 新增 `device_index` 參數，`config.yaml` 新增 `audio.device_index: 6`（PulseAudio）。
  * `voice_worker.py` 全部 `print()` 改為 `logger.info()` 統一日誌格式。
  * VAD→ASR 管線已驗證可用（Path C 繞過 Wake Word），待喚醒詞模型就緒後切回。

### [架構決策] Wake Word 開關與 Voice→Ollama→Bubble 完整鏈路
* **日期**：2026-07-22
* **問題描述**：
  1. Wake Word 層在 Path C 模式下完全不使用，但 `WakeWordEngine` 仍被強制實例化、載入模型。
  2. CHAT intent 只開聊天視窗，沒有把 ASR 文字送進 Ollama。
  3. 想要「語音→Ollama→氣泡回應」的完整鏈路，但 SpeechBubble 作為獨立 QWidget 在 Wayland/Sway 下被 tiling 管理，無法定位在貓咪旁邊。
* **解法**：
  1. **Wake Word 開關**：`config.yaml` 新增 `wake_word.enabled: false`，`voice_worker.py` 在 `__init__` 中判斷後才決定是否實例化 `WakeWordEngine`。`enabled=false` 時 `self.wake_word = None`，不載入模型。
  2. **CHAT→Ollama 鏈路**：`main.py` 的 `_on_voice_intent_detected` 改為：CHAT intent → `_voice_chat(user_text)` → background QThread 呼叫 `OllamaBackend.reply()` → `_show_voice_bubble()`。
  3. **QPainter 氣泡**：`speech_bubble.py` 從 QWidget 改為純 Python 類別，在 `paintEvent` 中用 QPainter 畫圓角矩形 + 尾巴三角形 + word-wrap 文字。沒有獨立視窗、沒有 timer thread 問題、Sway 正確 tiling。
  4. **think overlay 持續時間**：Ollama 呼叫期間 think overlay 設為 300s，回應到達後 clear + react bounce，避免「看起來卡死」。
  5. **MockVoiceWorker test-wav 模式**：`--test-wav FILE` 參數讓 MockVoiceWorker 載入 WAV → ASR → Intent → 走主程式真實管線（非平行測試腳本）。
* **踩坑紀錄**：
  * **Intent parser 子字串誤判**：`"rest" in "interesting"` 為 True，導致 "This is a very interesting video." 被誤判為 SLEEP → `self.close()` → 貓咪消失。修復：改用 `re.search(r'\b' + keyword + r'\b', text)` 做 word-boundary matching。
  * **QObject timer 跨執行緒**：SpeechBubble QWidget 的 `_hide_timer.start()` 從 worker thread 呼叫，觸發 `QObject::startTimer: Timers cannot be started from another thread`。修復：改為 paint-based 方案，用 `time.monotonic()` 檢查過期。
  * **Sway 視窗管理**：Wayland 下 QWidget 即使設 `FramelessWindowHint | WindowStaysOnTopHint | Tool`，Sway 仍把它當普通 window tiling。唯有畫在父視窗的 paintEvent 裡才能確保位置正確。
* **架構影響**：
  * `speech_bubble.py`：純 Python 類別（非 QWidget），`show(text, duration)` + `paint(painter, x, y, w, h)`。
  * `main.py`：`_voice_chat()` 方法（background QThread + Ollama）、`_show_voice_bubble()`、`_voice_chat_error()`。`paintEvent` 加入 `bubble.paint()` 調用。`_pack_tick` 加入 bubble 活躍時強制重繪。
  * `voice_animation.py`：新增 `set_overlay()` 與 `clear_overlay()` 公開 API。
  * `mock_voice.py`：`test_wav` 參數，`_run_test_wav()` 走真實 ASR→Intent 管線。

### [架構決策] VoiceBridge 統一整合層：減少 rebase 衝突
* **日期**：2026-07-23
* **問題描述**：
  重定基底 (rebase) origin/main 時，voice 功能在 `main.py` 散佈 6 處（init 22行、6 個 handler 80行、closeEvent、pack_tick、paintEvent、argparse），任何上游改動碰到鄰近行即觸發衝突。同時 `voice_animation.py` 直接存取 `window._pack_now()`（private method），上游 maintainability refactor 已改名過一次，未來再改即壞。
* **沙盤推演與考量**：
  * **方案 A (維持現狀)**：每次 rebase 手動解衝突。成本隨上游活躍度線性成長。
  * **方案 B (VoiceBridge 統一入口)**：新建 `voice_bridge.py` 封裝所有 voice 初始化、signal routing、Ollama chat、bubble/overlay paint。main.py 只留 delegation call。`voice_animation.py` 改用 `time_fn` callback 注入取代直接存取 window private API。
* **最終解法（方案 B）**：
  1. 新建 `mycat/voice_bridge.py`，`VoiceBridge(QObject)` 擁有 VoiceWorker、SpeechBubble、VoiceAnimationController。
  2. main.py 改動：`__init__` 5 行初始化、1 行 delegation intent、1 個 `_trigger_sleep_animation` callback、1 行 `closeEvent`、1 行 `pack_tick`、1 行 `paintEvent`。
  3. `voice_animation.py` 新增 `time_fn` callback 參數，不再直接訪問 `window._pack_now()`。無注入時 fallback 至舊路徑（deprecation path）。
  4. `voice_assistant` module-level import 改為 VoiceBridge 內 lazy import。
  5. 新增 `VOICE_BRIDGE_DEBUG=1` 環境變數開關，追蹤 callback 註冊與觸發路徑，3 個 clean commit 後關閉。
* **踩坑紀錄**：
  * **方法命名不一致**：rebase 衝突解決後，`_battery_low()` 應為 `battery_low()`、`_open_reminder_dialog` 應為 `open_reminder`（maintainability refactor 已改名）。冒煙測試即時捕捉修正。
* **驗證結果**：
  * Mock voice 3 分鐘冒煙測試：882 行 log，0 錯誤，110 次事件路由。
  * Real voice 2 分鐘冒煙測試：607 行 log，0 錯誤，13 次 VAD 觸發，7 次完整 Ollama→Bubble 鏈路。
* **架構影響**：
 * `voice_bridge.py`：新檔案，統一入口。擁有 worker/bubble/anim，暴露 `shutdown()`、`apply_paint()`、`should_repaint()`、`handle_intent()`、`set_llm_backend()`。
 * `main.py`：voice 相關從 ~120 行散佈降至 ~15 行 delegation。
 * `voice_animation.py`：`time_fn` callback 注入，`_pack_now()` decoupling。
 * 上游改動 `closeEvent`/`paintEvent`/`__init__` 時衝突機率大幅降低。

### [架構決策] VoiceCharPack：語音專屬靜態素材載入器
* **日期**：2026-07-23
* **問題描述**：
  `VoiceAnimationController` 的 `apply_overlay()` 使用程序化變形（scale/translate）模擬語音反應。但語音狀態（聽、思考、打哈欠）需要完全不同的角色表情，程序化變形從現有角色圖變不出全新的五官表情。
* **解法**：
  1. 新建 `mycat/voice_char_pack.py`，`VoiceCharPack` 類別從角色 ZIP/資料夾載入 `think.png`、`listen.png`、`yawn.png`。
  2. 自動讀取 `static.png` 取得原生尺寸，計算與 render 尺寸的比例後同步縮放語音素材。
  3. `VoiceBridge._init_animation()` 中建立 VoiceCharPack 並傳入 `VoiceAnimationController.set_voice_pack()`。
  4. `apply_overlay()` 優先檢查 VoiceCharPack 是否有對應 sprite，有則直接繪製 sprite（取代程序化變形），無則 fallback 至原有 scale/translate 邏輯。
* **架構影響**：
  * `voice_char_pack.py`：新檔案。
  * `voice_animation.py`：`set_voice_pack()`、`overlay_replaces_face` property（當 full-face sprite 活躍時跳過貓臉繪製）。
  * `main.py`：`overlay_replaces_face` 控制是否畫 `current_pixmap` 與瞳孔。
  * `cat2.zip`：加入 `think.png`、`listen.png`、`yawn.png`。

### [架構決策] BubblePopup：以 Qt.ToolTip 實現 Wayland 兼容浮動氣泡
* **日期**：2026-07-23
* **問題描述**：
  原本的 in-window SpeechBubble 在 Wayland (Sway) 浮動/無框模式下被 widget buffer 裁切，氣泡只能顯示下半 1/3。嘗試 resize widget 在 Wayland 上為非同步操作，compositor buffer 不會在當幀即時增長。獨立 QWidget（`FramelessWindowHint`）則被 Sway 平鋪管理為獨立 tile，違反氣泡位於貓旁的設計目標。
* **沙盤推演與考量**：
  * **方案 A (widget resize)**：`self.resize()` 在 Wayland 為 async，buffer 更新延後至少一幀。每次 resize 在 buffer 更新前繪製都會裁切。同時 resize 會觸發 layout 重算，造成貓咪位置跳動。
  * **方案 B (獨立 QWidget)**：`Qt.Window | Qt.FramelessWindowHint` 在 Sway 下被管理為獨立 tile，無法浮動。
  * **方案 C (Qt.ToolTip / xdg_popup)**：`Qt.ToolTip` 在 Wayland 使用 `xdg_popup` 協議。`xdg_popup` 是 transient 視窗，定位在父 surface（貓咪）附近，Sway 不會將其 tile 管理。不需要 widget resize。
* **最終解法（方案 C）**：
  1. 新建 `mycat/bubble_popup.py`，`BubblePopup(QWidget)` 使用 `Qt.ToolTip | Qt.FramelessWindowHint`。
  2. `WA_ShowWithoutActivating` + `WA_TranslucentBackground`，不搶焦點、背景透明。
  3. `show_bubble()` 計算氣泡位置（上方/下方自動選擇），`_position_near_cat()` 以 parent window 的 `mapToGlobal()` 計算螢幕座標。
  4. `paintEvent()` 自行繪製圓角矩形 + 尾巴 + 文字，尾巴方向根據氣泡位置（上/下）自動調整。
  5. 內部 `_hide_timer` 計時 8 秒後自動關閉。
  6. `voice_bridge.py`：SpeechBubble 改為 BubblePopup。`apply_paint()`/`should_repaint()`/`get_bubble_bounds()` 簡化。
  7. `main.py`：移除所有 widget 擴張程式碼（`_bubble_expanded`、`_original_size`、`_set_composite_mask`）。
* **踩坑紀錄**：
  * **QTimer 跨執行緒崩潰**：`_on_chat_done()` 經由 QThread signal 呼叫，lambda 中介導致 `_hide_timer.start()` 在 worker thread 執行。修復：直接 connect method（PySide6 AutoConnection 自動跨 thread queue）。
* **架構影響**：
  * `bubble_popup.py`：新檔案。
  * `voice_bridge.py`：SpeechBubble → BubblePopup。`_on_chat_done` 傳入貓咪座標。
  * `main.py`：大幅簡化 paintEvent，移除 resize/bubble_rect/mask 全部邏輯。
  * `speech_bubble.py`：不再被引用，保留為備用。

### [功能新增] Idle Yawn Timer：語音靜默觸發打哈欠
* **日期**：2026-07-23
* **問題描述**：
  語音長時間安靜時（無人說話），VoiceAnimationController 沒有任何反應，角色保持 idle 狀態。需要一種「等待中」的反應。
* **解法**：
  1. `VoiceAnimationController.__init__` 新增 `idle_yawn_after` 參數與 `QTimer`。
  2. `_reset_idle_timer()` 每次語音活動（任何 status/intent）時重設計時器。
  3. 計時逾時觸發 `_on_idle_yawn()` → `_trigger("yawn", 3.0)`。
  4. 可透過 `config.yaml` 的 `overlay.idle_yawn_after` 設定（預設 30s），設為 0 關閉。
* **架構影響**：
  * `voice_animation.py`：QTimer、`_reset_idle_timer`、`_on_idle_yawn`。
  * `voice_bridge.py`：讀取 config 傳入 `idle_yawn_after`。
  * `config.yaml`：`overlay.idle_yawn_after: 30`。

### [功能新增] 輸入裝置自動偵測與 ASR 暖啟動機制 (TASK-1c)
* **日期**：2026-07-26
* **問題描述**：
  1. `device_index` 為硬編碼，跨使用者/跨設備須手動修改 config。
  2. ASR 模型為 lazy-load，第一次辨識耗時 2-5 秒，使用者體驗差。
  3. 無 GUI 讓使用者選擇音訊裝置。
  4. 貓咪 sleep 時仍佔用 ASR 記憶體。
* **解法**：
  1. **輸入裝置偵測**：`audio_stream.py` 新增 `list_devices()` 列舉所有輸入裝置、`prefer_suitable_device()` 自動過濾 raw ALSA、優先 PulseAudio/PipeWire。
  2. **Auto-detect**：`config.yaml` 的 `audio.device_index` 改為 `null` 表示自動偵測。`AudioStreamManager.__init__` 收到 `None` 時呼叫 `prefer_suitable_device()`。
  3. **ASR Warm-load**：`asr_pipeline.py` 新增 `load()` / `unload()` 方法。`voice_worker.py` 在 `run()` 開頭呼叫 `self.asr.load()` 提前載入模型。
  4. **Drop Window**：`config.yaml` 新增 `asr.drop_after_warmup_sec: 5.0`。`voice_worker.py` 新增 `_warmup_start_time`，在暖啟動後 5 秒內的 ASR 結果會被跳過（log 並 continue）。
  5. **SLEEP → unload**：當 `intent.type == "SLEEP"` 時，`voice_worker.py` 呼叫 `self.asr.unload()` 釋放記憶體。下次 VAD 觸發時自動 reload。
  6. **Ring Buffer 重構**：`audio_stream.py` 新增 `get_recent_chunk(duration_sec)` 取代重複的 slice 邏輯。
* **驗證結果**：
  * `list_devices()` 可列出所有輸入裝置（index, name, channels, sample_rate）。
  * `prefer_suitable_device()` 在 Linux 上正確跳過 `hw:` 裝置、優先選 PulseAudio。
  * 啟動時 `voice_worker.py` log 顯示 `[ASRPipeline] Loading faster-whisper model...`。
  * SLEEP intent 觸發後 `self.model = None`，記憶體釋放。
* **待完成**：
  * GUI 持久化 (`voice_device.json`) 與 `settings_ui.py` 下拉選單。
  * `voice_bridge.py` 監聽 device 變更並熱重啟 worker。

### [重構] 降低 Voice 對 main.py / settings_ui.py 的入侵
* **日期**：2026/07/26
* **問題描述**：TASK-1c 實作時 Voice 相關程式碼直接散落在 `main.py`（~35行）與 `settings_ui.py`（~20行），耦合過高。
* **最終解法**：
  1. **VoiceDeviceRow 抽出自洽 widget**：將 `settings_ui.py` 中的 device selection 邏輯（QLabel + QPushButton + 對話框開啟 + update_device）封裝為獨立的 `VoiceDeviceRow(QtWidgets.QWidget)` 類別，放在 `voice_device_dialog.py` 中。`settings_ui.py` 僅需 2 行：`from mycat.voice_device_dialog import VoiceDeviceRow` 和 `layout.addWidget(VoiceDeviceRow(...))`。
  2. **VoiceBridge auto-wire callbacks**：將 `_trigger_sleep_animation` 搬入 `VoiceBridge._window_sleep_animation()`（透過 `self.window.*` 存取 window 內部），並在 `VoiceBridge.__init__` 自動接線。`main.py` 不再需要手動呼叫 `set_sleep_callback()` 和 `set_reminder_callback()`。
  3. **Dead code 清理**：刪除 `main.py` 中遺留的 `_on_voice_intent_detected`（VoiceBridge 已透過 signal/slot 內部處理 intents）。
   4. **封裝 private access**：新增 `VoiceBridge.is_bubble_active` property，`main.py` 不再直接存取 `_bubble`。
   5. **Wayland tray fallback**：在 `setup_tray` 中偵測 `WAYLAND_DISPLAY` 環境變數，自動跳過 system tray（Sway 不支援 tray 右鍵選單），讓右鍵選單正確顯示 Quit。
   6. **消除建構子污染**：`mock_voice` / `test_wav` 原是 `PixelCatWindow` 建構子參數，僅為轉送給 `VoiceBridge`。改由 `VoiceBridge._init_worker()` 直接讀取 `MYCAT_MOCK_VOICE` / `MYCAT_TEST_WAV` 環境變數。`main()` 在解析 CLI args 後設 env var，`PixelCatWindow` 不再需要知道這兩個參數。
* **結果**：`main.py` voice intrusion 從 ~35 行降至最終 12 行（含 2 行 wayland_drag），`settings_ui.py` intrusion 從 ~20 行降至 2 行。詳見 `vendors/STAGE-1c.md`。

### [Bugfix] VoiceDeviceDialog `Accepted` vs `accepted` 屬性錯誤
* **日期**：2026/07/27
* **問題描述**：
  右鍵選單 → Voice → Select Device 時拋出 `AttributeError: 'VoiceDeviceDialog' object has no attribute 'Accepted'`。PySide6 的 `QDialog.exec()` 回傳 `DialogCode` enum，`dialog.Accepted` 是在問「實例上有沒有叫 `Accepted` 的屬性？」——當然沒有，enum 要到類別上取 `QtWidgets.QDialog.DialogCode.Accepted`。
* **解法**：
  `voice_device_dialog.py:93` 改為 `dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted`。
* **Runtime 裝置切換流程驗證**：
  分析 `VoiceWorker.update_device()` → `AudioStreamManager.stop()` → 換 index → `start()` → `device_store.save_device_index()` 的完整流程，確認：
  1. **Dialog 只選取不設定**：`VoiceDeviceDialog.get_device()` 回傳 index，真正的設定在 `_open_dialog()` 呼叫 `update_device()` 完成。
  2. **下拉選了有觸發寫入**：OK 後呼叫 `update_device(selected)`，內部會 `device_store.save_device_index()` 存到 `~/.config/mycat/voice_device.json`。
  3. **Runtime 佔用不會衝突**：`stop()` 完整關閉舊串流 + `p.terminate()` 釋放 PyAudio 資源後才 `start()` 開新裝置。
  4. **背景 thread 安全**：`stop()`/`start()` 都是同步 blocking call，GIL 保護下不會同時讀寫 ring buffer。
  5. **小隱患**：`stop()` 不清 ring buffer，切換後 worker 可能先拿到舊裝置殘留音訊（~3 秒），下一次迴圈即被新資料覆蓋，實務影響極小。

### [Bugfix] GNOME Wayland 語音氣泡：從 xdg_popup / xdg_toplevel → in-window QPainter
* **日期**：2026-07-27
* **問題描述**：
  `BubblePopup`（獨立 QWidget 視窗）在 GNOME Wayland (mutter) 下無法正常顯示：
  1. **Qt.ToolTip (xdg_popup)**：Sway 正常，GNOME 不渲染（log 顯示 shown 但螢幕看不見）。
  2. **Qt.Window + parent**：`show()` 永久 hang（Wayland 協定 deadlock）。
  3. **Qt.Window + parent=None**：無 hang 有渲染，但 `move()` 被 mutter 忽略 → 氣泡永遠出現在螢幕正中央。
* **根因**：
  * `mapToGlobal()` 在 Wayland 回傳 (0,0)（安全限制，無法取得全域座標）。
  * `move()` 在 GNOME Wayland 對已 mapping 的 xdg_toplevel 無效（mutter 不允許 client 設定視窗位置）。
  * Qt.ToolTip (xdg_popup) 在 GNOME 可能有額外的 surface commit 約束未滿足。
* **沙盤推演與考量**：
  * **方案 A (繼續修正 ToolTip popup)**：嘗試找出 GNOME 上 xdg_popup 不渲染的根因。時間成本不可控。
  * **方案 B (QWindow.setPosition)**：透過 native handle 設定位置。Qt 文件已註明 `setPosition()` 在 Wayland 無效果。
  * **方案 C (resize + move 貓視窗)**：在貓視窗上方 expand 空間畫氣泡。`move()` 在 GNOME 被忽略 → 貓視窗向下長 → 貓與氣泡一起超出螢幕底部。
  * **方案 D (in-window 右上角，不 resize)**：氣泡畫在貓視窗內部右上角，完全不動視窗幾何。**可靠、簡單、無 side effect。**
* **最終解法（方案 D）**：
  1. `voice_bridge.py._init_bubble()` 偵測 GNOME Wayland（`XDG_CURRENT_DESKTOP=GNOME` + `WAYLAND_DISPLAY`），使用既有的 in-window `SpeechBubble` 類別。
  2. SpeechBubble 在 GNOME 模式下透過 `apply_paint()` 以 `pos=(window_width - bw - 8, 4)` 定位於視窗右上角。
  3. 非 GNOME 路徑完全不受影響，維持原有 `BubblePopup`（Qt.ToolTip / xdg_popup）。
  4. 氣泡過期時 `is_active` 自動變 False → `apply_paint` 不再繪製 → 自然消失（無需 restore）。
* **技術卡點**：
  * **SpeechBubble 的 paint() 原本只能以 cat sprite 座標定位**：需要支援手動座標。新增 `pos=(bx, by)` keyword-only 參數，非 None 時繞過 `cat_x/cat_y` 計算，直接使用指定座標。
  * **無法計算氣泡高度以決定位置**：新增 `bubble_size(text)` 公開方法，回傳 `(bw, bh)` 供外部計算定位。
  * **GNOME 路徑不需要 hide_bubble**：`BubblePopup` 有 `hide_bubble()` 用於強制隱藏，但 `SpeechBubble` 是純繪製類別，無視窗可隱藏。`is_active` property 已涵蓋 timeout 邏輯。
* **架構影響**：
  * `voice_bridge.py`：`_init_bubble()` 新增 GNOME 分流；`apply_paint()` 新增 GNOME 繪製路徑；`_on_chat_done()` 新增 GNOME 分支。
  * `speech_bubble.py`：`paint()` 新增 `pos` 參數；新增 `bubble_size()` 方法。
  * `bubble_popup.py`：不再被 GNOME 使用，保留作為非 GNOME 平台（Sway/X11）的氣泡方案。

### [架構決策] Wayland 公告氣泡統一修復（TASK-2a）
* **日期**：2026/08/20
* **問題描述**：
  Reminder 公告氣泡 (`BubbleWindow`) 使用 `mapToGlobal()` + `move()` 定位獨立 QWidget，在所有 Wayland compositor（GNOME / Sway / Hyprland / KDE）上 `mapToGlobal()` 回傳 `(0,0)`，氣泡固定出現在螢幕中央。本分支語音氣泡已有解法（`SpeechBubble` in-window QPainter），但僅限 GNOME。`_is_gnome_bubble` 判斷排除了 Sway 等其他 Wayland 環境。
* **沙盤推演與考量**：
  * **方案 A：直接改 `announcer.py`**：在 `launch_bubble()` 內加入 compositor 判斷。問題：污染主線模組，增加合併衝突風險。
  * **方案 B：Factory Pattern**：`announcer.py` 新增 `_bubble_factory` 屬性，由 `main.py` 注入。Announcer 完全不知道 Wayland 的存在。**採用。**
  * **方案 C：改 `BubbleWindow` 本身**：在 `BubbleWindow.__init__` 內判斷 Wayland 走 in-window。問題：`destroyed` signal 機制在 paint 模式下無法運作，且 `BubbleWindow` 會變得複雜。
* **最終解法**：
  1. `voice_bridge.py`：`_is_gnome_bubble` 重命名為 `_is_wayland_bubble`，判斷改為 `_is_wayland`（與 `wayland_drag.py` 策略一致）。`_gnome_*` 屬性/方法統一重命名為 `_wayland_*`。
  2. `voice_bridge.py`：新增 `show_announcement_bubble(text, duration, on_gone)` 方法，複用 `_wayland_bubble_show` 邏輯，回傳 `AnnouncementBubbleHandle`（QObject with `destroyed` signal）。
  3. `announcer.py`：`__init__` 新增 `_bubble_factory = None`；`launch_bubble()` 頂部加 factory 檢查（+6 行，0 刪改）。
  4. `main.py`：初始化時偵測 `_is_wayland`，注入 factory lambda 到 `announcer._bubble_factory`。
* **技術卡點**：
  * **Announcer 需要 `destroyed` signal**：`SpeechBubble` 非 QObject，無 signal。解法：`AnnouncementBubbleHandle`（輕量 QObject），QTimer 過期後呼叫 `on_gone` callback + `destroyed.emit()` + `deleteLater()`。
  * **語音氣泡和公告氣泡可能同時觸發**：`show_announcement_bubble()` 檢查 `_wayland_extra_h > 0` 先還原再顯示。
* **架構影響**：
  * `voice_bridge.py`：全域重命名 ~12 行 + 新增方法 ~30 行 + `AnnouncementBubbleHandle` 類別。
  * `announcer.py`：+1 屬性 +5 行 factory 檢查，零刪改。
   * `main.py`：+7 行 factory 注入。
   * `speech_bubble.py` / `bubble_popup.py`：不動。

### [已知問題] listen.png 聆聽 overlay 幾乎不可見（延後處理）
* **日期**：2026-08-21
* **問題描述**：
  使用者實際觀察：VAD 觸發後的 `listen.png` 聆聽姿態 overlay 幾乎從未出現在畫面上。推測原因為 VAD 觸發 → ASR 開始轉寫的時間窗極短，`listen` 狀態在極短時間內即被 `think` 狀態覆蓋，肉眼難以察覺。
* **影響評估**：
  低。不影響語音助理功能正確性（聆聽 → 思考 → 回覆流程正常），僅為視覺回饋幾乎無法感知，非致命問題。
* **處理狀態**：
  **延後修復**。未來若要修，方向：檢查 `voice_animation.py` 的 listen trigger 持續時間與 VAD → ASR 狀態流轉時序；可考慮為 listen 狀態加最短顯示時間 (min display duration)，並確認 `listen.png` 素材有被 `VoiceCharPack` 正確載入。

### [架構決策] 上游檔案所有權還原：SpeechBubble 搬遷 (TASK-3a)
* **日期**：2026-08-21
* **問題描述**：
  文件審閱發現本分支曾直接編輯上游檔案 `mycat/speech_bubble.py`（TASK-1b `ce975b6` 注入 `SpeechBubble`、TASK-1d `5207e47` 擴充），且 AI Agent 編輯時誤刪上游 ~43 行註解/docstring（`BubbleWindow` 錨定策略、成長方向圖解、X11 workaround 說明）。該檔案是主線 reminder/announcer 的活躍開發檔案，此入侵使未來 rebase 衝突面最大化，且曾導致另一台電腦上的開發 Agent 無法判斷「該改上游檔案還是自有實作」而卡關。
* **最終解法**：
  1. `SpeechBubble` 類別原封搬遷至自有新檔 `mycat/voice_bubble.py`（程式化 diff 驗證類別本體 IDENTICAL）。
  2. `voice_bridge.py` 兩處 import 改指向 `mycat.voice_bubble`。
  3. `speech_bubble.py` 以 `git restore --source=origin/main` 還原為上游原版，衝突面歸零。
  4. AGENTS.md §2 固化所有權規則：上游檔案唯讀；分支功能一律 subclass / vendor 組合；嚴禁順手清理上游註解。判定基準：`git ls-tree origin/main` 查得到即上游檔案。
* **教訓**：
  AI Agent 編輯共用/上游檔案時的「順手清理註解」是零收益、高衝突的破壞行為，必須在守則中明文禁止；所有權判定應機械化（ls-tree），不留判斷空間。

### [架構決策] 氣泡模組邊界分析：上游 speech_bubble.py 與語音分支氣泡域（TASK-3a 後盤點）
* **日期**：2026-08-21
* **三層邊界地圖**：
  * **Layer A（上游氣泡域，零反向依賴）**：`speech_bubble.py`（`BubbleWindow` + `bubble_mode_enabled`/`set_bubble_mode`）← `announcer.py`、`reminder.py`、`settings_ui.py`、`tests/test_speech_bubble.py`。
  * **Layer C（接縫＝組合根）**：`mycat/main.py` 在 Wayland 下把 `voice_bridge.show_announcement_bubble` 注入 `announcer._bubble_factory` 與 `reminder_controller._bubble_factory`。
  * **Layer B（本分支氣泡域，自有命名空間）**：`voice_bridge.py`（後端選擇器：Wayland → `voice_bubble.SpeechBubble` in-window 繪製；其他 → `bubble_popup.BubblePopup` xdg_popup；失敗 → None 優雅降級）＋ 公告氣泡統一入口 `show_announcement_bubble()`。
* **接縫機制：依賴反轉，不是 import**：
  TASK-3a 後 B→A 方向 import 歸零；A→B 方向從無 import——上游只認識「回傳帶 `destroyed` signal handle 的 callable」（`_bubble_factory`，預設 None 走原版行為）。合約面僅一個函式簽名寬；拔掉注入即 100% 還原上游行為。**掛勾式（hook）是合併與解問題的最優形態**——衝突面最小、語意可雙向共存，此結論經使用者認可，後續跨邊界整合一律優先採用 hook 注入而非直接編輯。
* **殘餘上游接觸面（純新增，非零但可控）**：
  | 檔案 | 增量 | 內容 | 風險 |
  |------|------|------|------|
  | `mycat/main.py` | +178 | VoiceBridge 初始化、factory 注入、repaint hook、shutdown | 低（組合根本就是 fork 必改之地） |
  | `mycat/announcer.py` | +7 | `_bubble_factory` 屬性 + 分支判斷 | 低（hook 式樣可回饋上游 PR） |
  | `mycat/reminder.py` | +9 | 同上 | 低 |
  與已修復的 speech_bubble 本質不同：**零刪除**，衝突解法恆為「兩邊都留」，不存在語意破壞。
* **airplane 模式與 Wayland 修正的互動查證**（使用者提問，已驗證無斷點）：
  兩處呼叫點的閘門順序皆為「config 檢查 → 才進 bubble 路徑」：`announcer.py:189` `launch_flyby()` 先問 `bubble_mode_enabled()`，OFF → 紙飛機 flyby，走不到 `launch_bubble()` 內的 factory；`reminder.py:226` 同樣先問 `bubble_mode_enabled()`，ON 才試 factory（factory 例外時 fallback 回 `BubbleWindow`）。我們的注入被上游 config 閘門完整罩住——飛機模式照飛、氣泡模式走 Wayland 修正，互不干擾。
* **測試覆蓋補全**：
  TASK-3a 盤點發現自有資產 `SpeechBubble` 無測試（上游僅測 `BubbleWindow`）。已新增 `tests/test_voice_bubble.py`（5 tests：尺寸換行與寬度上限、show/clear 生命週期、duration 到期自動隱藏、雙模式 paint 冒煙、`_wrap_text` 行寬約束），沿用上游 conftest 的 offscreen qapp 慣例。9 passed（新 5 + 上游 4）。
* **config 域分離備忘**：
  上游 `bubble_mode_enabled()` 只管 announcer/reminder 的 BubbleWindow；語音氣泡有獨立生命週期不受它管。目前合理；若未來期望「關閉氣泡模式」連語音氣泡一起關，需明確決策而非意外行為。
* **演進守則**：
  上游強化 `BubbleWindow` 時 announcer/reminder 免費受益，SpeechBubble/BubblePopup 各自演化（視覺分歧是所有權隔離的設計內成本，禁止跨邊界合併實作）；需要新氣泡能力只在 Layer B 加，不再進上游檔案。

### [架構決策] 語音管線 WAV 注入式全真自動測試（TASK-3b）
* **日期**：2026-08-21
* **問題描述**：
  語音管線（VAD/ASR/intent）過去只有手動硬體腳本可驗，無麥克風環境下全套件甚至會因建主視窗測試觸發 ASR 暖啟動開真音訊裝置而 Fatal Abort。需要一套「真系統、假音源」的自動測試：暖啟動/VAD/ASR 全真，僅麥克風以預錄 WAV 替代。
* **解法**：
  * **`WavAudioStreamManager`**（`core/audio_stream.py` 子類）：`_load_wav` 驗 16-bit/下混立體聲/`np.interp` 重採樣至 16kHz；daemon thread 以真實 chunk 節奏餵 `_audio_callback`——下游完全無感。`voice_worker.py` 以 `MYCAT_AUDIO_WAV` env 切換（`MYCAT_MOCK_VOICE` 優先權不變）。
  * **conftest 根修**：`setdefault("MYCAT_AUDIO_WAV", <預設fixture>)` 一處修正所有建主視窗測試的開麥克風路徑。
  * **fixtures = ESP32 INMP441 訓練語料純拷貝**（pos×4 / neg×2），零增益零加工；`tests/fixtures/config_test.yaml` 僅校準 `vad.threshold: 2000`（生產 21000 是桌面麥克風值）與 `drop_after_warmup_sec: 0`。
  * `tests/test_voice_pipeline_e2e.py` 11 tests：parser 四路單元 ×3、SLEEP→動畫狀態機整合 ×6（`VoiceBridge.__new__` 白箱 + FakeWindow）、全真 E2E ×2（正樣本→CHAT intent 信號、負樣本靜默）。
* **踩坑教訓**：
  * **整窗 RMS 稀釋**：`get_recent_chunk(0.1)` 的 `[-num_samples:]` 切片在 ring buffer 未滿時回傳整個緩衝 → 有效 VAD 視窗是整窗 RMS，短句被稀釋。對 fixture 加增益/拼接補洞全部失敗（削波或不穩定）；**自然原聲 + 校準門檻**才是正解，門檻本就是設備校準參數（與桌面麥克風校準同一性質）。
  * **全套件 Segfault ≠ 新 bug**：PyAudio Abort 根修後浮出 `test_window_behavior` 拖曳測試 segfault——跨測試 Qt offscreen 狀態污染，pyproject 註解早寫明需 `pytest-forked` 但未安裝。裝上後全套件穩定（281 passed / 3 failed 為既有 icalendar 缺模組）。
  * **信號接線**：`ASR_READY` 走 `asr_status_signal` 而非 `status_changed_signal`，E2E spy 接錯線造成假失敗。
* **升級路徑**：補錄一個 3 秒 "sleep" wav 即可讓 E2E 斷言 SLEEP 意圖直達動畫畫層，閉合最後一環；wake word 維持不測（config 已停用）。

### [校準紀錄] VAD 門檻環境階梯實測（生產值 21000 定案依據）
* **日期**：2026-08-21
* **前情**：延續 2026-07-22 兩則校準記錄（energy² 時代 15M → RMS 重構後 20,000），補上 20,000 → 21,000 的最終定案依據與完整環境噪聲階梯。
* **門檻演進與行為觀察**（使用者長期實測；觀察代理指標＝小貓 think 動畫誤觸發頻率）：
  | 門檻 | 行為觀察 | 判定 |
  |------|---------|------|
  | 20,000 | 小貓頻繁跳 think 動畫（底噪誤觸發） | 太低 |
  | **21,000** | think 動畫頻率恢復正常 | **定案** |
  | 23,000 | 幾乎要大吼才有反應，甚至到不了 LLM | 太高 |
* **環境噪聲階梯實測**（圖書館場景，RMS）：
  | 聲源 | RMS | 對 21000 餘裕 |
  |------|-----|--------------|
  | 環境底噪 | 6,000–7,000 | ~32% |
  | 電風扇風切（吹拂筆電） | 9,000–13,000 | 38–57% |
  | 手指敲擊麥克風旁 | 16,000–19,000 | 僅 10–19% |
* **結論與取捨**：
  * 21000 是「高特異性、低敏感度」的刻意選擇：寧可要求筆電前大聲說話，也不接受底噪/風切誤觸發。
  * 最脆弱邊界在敲擊層（19k vs 21k 僅 ~10% 餘裕）：重物撞桌/闔蓋可能越線，但下游有防線——VAD 只是閘門，誤觸發後 whisper 轉出垃圾、intent 歸 NONE，系統回 LISTENING。
  * 門檻是設備×環境的校準參數，非普適常數：TASK-3b 的 ESP32 INMP441 fixtures（buffered RMS pos 3477–7831）另配 2000 測試門檻，同一哲學。
  * 未來升級路徑（YAGNI 暫緩）：動態門檻 `threshold = k × rolling 環境RMS`，自動適應圖書館/咖啡廳。
* **診斷應用**：soak test 劇本的拍手/敲桌動作預期落 16k–19k，照此階梯**不會觸發**——log 靜默即驗證校準，非測試失敗。
