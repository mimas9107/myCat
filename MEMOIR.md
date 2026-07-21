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


