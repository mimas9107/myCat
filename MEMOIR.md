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
