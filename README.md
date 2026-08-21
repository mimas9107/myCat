EN | [RU](https://github.com/yumiaura/myCat/blob/main/docs/README_RU.md) | [CN](https://github.com/yumiaura/myCat/blob/main/docs/README_CN.md) | [ID](https://github.com/yumiaura/myCat/blob/main/docs/README_ID.md) | [KO](https://github.com/yumiaura/myCat/blob/main/docs/README_KO.md)

## Desktop Cat: QT Overlay 🐱

[<img src="https://raw.githubusercontent.com/yumiaura/myCat/refs/heads/main/docs/cat.gif" width="164" alt="cat.gif"/>](https://github.com/yumiaura)

<p class="badges">
  <a href="https://github.com/yumiaura/myCat/releases/latest"><img src="https://img.shields.io/github/v/release/yumiaura/myCat?label=download&color=blue" alt="Latest release"></a>
  <img src="https://img.shields.io/pypi/pyversions/mycat?color=brightgreen" alt="Python Versions">
  <a href="https://pypi.org/project/mycat/"><img src="https://img.shields.io/pypi/v/mycat?color=brightgreen" alt="PyPI Version"></a>
  <a href="https://pypi.org/project/mycat/"><img src="https://img.shields.io/pepy/dt/mycat?label=pypi%20%7C%20downloads&color=brightgreen" alt="Pepy Total Downloads"/></a>
</p>

I made a cute little animated cat 🐈 for your desktop, with an interface in English, 中文, 한국어 and Русский.<br>
It's a lightweight Python + Qt app - no borders, and you can drag it around easily.<br>
Shows static first frame for 5 seconds, then plays GIF animation once, then loops back to static.<br>
Switch the interface language any time under **Settings → Language**.<br>
If you like it, maybe I'll share an [AnimeGirl](https://github.com/yumiaura/mycat/discussions/1) version next time~ 😉<br>

<img width="640" height="360" alt="image" src="https://github.com/user-attachments/assets/332494c9-8e39-4774-a85c-808839229106" />

### LLM Chat, Reminders, GitHub Integration & Tracking Activity

<img width="280" height="200" alt="image" src="https://github.com/user-attachments/assets/9554bd7d-f06b-4acb-abb1-9c525103ac42" />
<img width="280" height="200" alt="image" src="https://github.com/user-attachments/assets/022d5d14-fa75-4940-bbaa-ea6cd2a72a77" />
<br />
<img width="280" height="200" alt="image" src="https://github.com/user-attachments/assets/0a1d078e-77f4-4f16-a09f-a94c5deff086" />
<img width="280" height="200" alt="image" src="https://github.com/user-attachments/assets/d9f4cce9-bf3c-4d64-a28e-1cac7d050a8c" />

### 🎨 Create your own cat with AI

Turn a few photos into your own cat. Right-click → **Chars → Create custom with AI…**,
add 1–3 photos of the same person, **edit the prompt** (and a negative prompt for the
self-hosted backends) to shape the character, pick **txt2img** (from the prompt) or
**img2img** (from your photos), and generate with **OpenAI** or your own self-hosted
**Stable Diffusion (AUTOMATIC1111)** or
**ComfyUI** server — set its address in the dialog and pick the checkpoint from the live
model list. It's saved as an ordinary local char you can reuse or delete anytime; reference
photos are resized in memory and **never stored** by myCat. OpenAI needs your own API key
(one request per generation) and returns a transparent cat; the self-hosted backends run on
your own GPU.

<img width="270" alt="Create custom cat with AI — dialog" src="https://github.com/user-attachments/assets/f94c141f-d339-4827-a476-a5725e27c9be" />
<img width="220" alt="Generated cat" src="https://github.com/user-attachments/assets/1bec007a-eb5c-469a-a732-a1cd37c6cf27" />
<br />
<img width="270" alt="AI character — options" src="https://github.com/user-attachments/assets/6a67eb02-8ec0-4da9-a93c-0a16543f3679" />
<img width="270" alt="Generated cat on the desktop" src="https://github.com/user-attachments/assets/848ff041-55b0-417c-aaf7-2759cc6a6c9a" />

## 🚀 Quick start

Pick whichever is easiest - the cat runs on **Windows, macOS and Linux**.

### Option A - prebuilt binary (no Python needed)

Grab the build for your OS - each button downloads the **latest release**:

<p>
  <a href="https://github.com/yumiaura/myCat/releases/latest/download/mycat-windows-x64.exe"><img src="https://img.shields.io/badge/Download-Windows-0078D6?logo=data:image/svg%2Bxml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0id2hpdGUiPjxwYXRoIGQ9Ik0wIDMuNDQ5IDkuNzUgMi4xdjkuNDUxSDB6TTEwLjk0OSAxLjk0OSAyNCAwdjExLjRIMTAuOTQ5ek0wIDEyLjZoOS43NXY5LjQ1MUwwIDIwLjY5OXpNMTAuOTQ5IDEyLjZIMjRWMjRsLTEyLjktMS44MDF6Ii8%2BPC9zdmc%2B" alt="Download for Windows"></a>
  <br>
  <a href="https://github.com/yumiaura/myCat/releases/latest/download/mycat-macos-arm64.zip"><img src="https://img.shields.io/badge/Download-macOS%20Apple%20Silicon-000000?logo=apple&logoColor=white" alt="Download for macOS (Apple Silicon)"></a>
  <br>
  <a href="https://github.com/yumiaura/myCat/releases/latest/download/mycat-macos-x64.zip"><img src="https://img.shields.io/badge/Download-macOS%20Intel-555555?logo=apple&logoColor=white" alt="Download for macOS (Intel)"></a>
  <br>
  <a href="https://github.com/yumiaura/myCat/releases/latest/download/mycat-linux-amd64.deb"><img src="https://img.shields.io/badge/Download-Linux%20.deb-A81D33?logo=debian&logoColor=white" alt="Download Linux .deb"></a>
  <br>
  <a href="https://github.com/yumiaura/myCat/releases/latest/download/mycat-linux-x86_64.AppImage"><img src="https://img.shields.io/badge/Download-Linux%20AppImage-FCC624?logo=linux&logoColor=black" alt="Download Linux AppImage"></a>
</p>

Then run it:

- **Windows** - double-click the `.exe`.
- **macOS** - unzip and open `mycat.app` (first launch: right-click → **Open** to get past Gatekeeper).
- **Linux `.deb`** - `sudo apt install ./mycat-linux-amd64.deb`.
- **Linux AppImage** - `chmod +x mycat-linux-x86_64.AppImage && ./mycat-linux-x86_64.AppImage` (needs FUSE: `sudo apt install libfuse2`).

> Builds for every release live on the **[Releases](https://github.com/yumiaura/myCat/releases)** page.

### Option B - pip (Windows / macOS / Linux, Python ≥ 3.10)

```bash
pip install mycat
mycat
```

On **Linux** also install the Qt platform plugin once:

```bash
sudo apt install -y libxcb-cursor0
```

The activity diary can **count** key presses and clicks (never _which_ keys) -
it works out of the box on Windows, macOS and Linux/X11. Where global input
access isn't available (e.g. Wayland) it degrades to recording the cursor path.

Upgrade or remove later with `pip install -U mycat` / `pip uninstall mycat`.

### Option C - from source

```bash
git clone https://github.com/yumiaura/myCat
cd myCat
pip install .
mycat                 # or, without installing:  python3 mycat/main.py
```

## ✨ Features

- **Animated overlay** 🐱 - a frameless, always-on-top, draggable cat. Right-click for the menu (switch char, quit).
- **Reminder** 🛩️ - set a message and a time (one-shot or daily) and the cat flies a little banner plane across the top of your screen. Right-click → _Reminder…_ to set the message, direction, plane and color.
- **Chat (Ollama)** 💬 - talk to the cat through a **local [Ollama](https://ollama.com) model**, no account or API key needed (see below).
- **Create with AI** 🎨 - turn 1–3 photos into a custom chibi cat character with your own OpenAI key (right-click → _Chars → Create custom with AI…_). Reference photos are never stored; the result is an ordinary local char you can reuse or delete.
- **Multilingual interface** 🌐 — the whole UI is available in **English, 한국어 (Korean), Русский (Russian) and 简体中文 (Simplified Chinese)**. Right-click the cat (or the tray) → under **Settings…** → **Language** to switch at any time; the choice is remembered. Translations live in plain `mycat/locale/*.json` files, so adding a language is just dropping in a file.

## 💬 Chat with the cat (Ollama)

The cat can chat using a model served locally by [Ollama](https://ollama.com) - everything stays on your machine, no API key required.

1. Install [Ollama](https://ollama.com) and pull a model:
   ```bash
   ollama pull llama3.1
   ```
2. Launch **mycat**, then right-click the cat → **Ollama…**
3. Set the host/port (default `localhost:11434`), click **Load models**, pick one, hit **Test**, then **Save** and tick **LLM enabled**.
4. Right-click → **Chat** to start talking. 🐾

## 🎮 Usage & options

Run `mycat` (or `python3 mycat/main.py` from source) and customise it with command-line options.

**`--image, -i <path>`** 🖼️ - use a custom ZIP archive (containing one GIF) instead of the default cat:

```bash
mycat --image ~/my-custom-cat.zip
```

A char **ZIP** must contain exactly one `.gif`: its first frame is the static pose, then the GIF plays once and returns to that frame. Images larger than 300×500 are scaled down automatically.

**`--pos <x> <y>`** 📍 - start at a specific screen position (otherwise the cat appears bottom-right and remembers where you last dragged it):

```bash
mycat --pos 960 540        # center of a 1920x1080 screen
```

**`--wait <seconds>`** ⏱️ - how long to hold the static first frame before the animation plays.

**`--debug`** 🐞 - verbose per-frame logging.

### Controls

- **Left-drag** the cat to move it.
- **Right-click** the cat for the menu (Chars, Reminder…, Ollama…, Chat, Quit).
- **Quit** from the menu or with Ctrl+C in the terminal.

The cat remembers its position and selected char between sessions in `~/.config/mycat/config.ini`.

## 🎬 Make your own cat

A char is just an animated GIF in a `.zip` - from a quick doodle to a fully
interactive cat with cursor-tracking eyes, blinking, sleeping and click
reactions. Step-by-step guide (draw it, build the GIF, package, install & share):
**[docs/CHARS.md](docs/CHARS.md)**.

## 🐳 Docker

Run the cat in a container with GUI forwarding to your host's X server.

**Prerequisites:** Docker, and an X server on the host (Xorg on Linux, VcXsrv on Windows, XQuartz on macOS).

```bash
# Linux
xhost +local:docker
docker compose up --build

# Windows (VcXsrv running, network clients allowed)
docker compose -f docker-compose.windows.yml up

# macOS (XQuartz running, network clients allowed)
docker compose -f docker-compose.mac.yml up
```

## 🔧 Troubleshooting

**Cat appears in a black box / transparency doesn't work** 🫥

- On X11 transparency needs a compositor. mycat falls back to clipping the window to the cat's outline when none is running, so this is rare; if you still see a box, enable display compositing (XFCE: _Window Manager Tweaks → Compositor_) or run a compositor such as `picom`.

**Window doesn't stay on top / doesn't show in the taskbar** 📌

- Some window managers override "always on top" - restart the desktop session or check the WM settings.

**Custom char doesn't load** ❌

- The ZIP must contain exactly one valid `.gif`. Check the path and that the file isn't corrupted.

**Position not saving** 💾

- Make sure `~/.config/mycat/` exists and is writable; the config file is `~/.config/mycat/config.ini`.

**Windows / launch issues** 🪟

- Need Python ≥ 3.10 (`python --version`) for the pip install, or just use the prebuilt `.exe`.
- From the repo you can also launch with `run.bat` (Windows) or `run.sh` (Linux/macOS).
- Verify PySide6: `python -c "import PySide6; print('PySide6 OK')"`.

**Permission errors** 🔒

- On Linux prefer a user install over `sudo` (`pip install --user mycat`).

### 🤝 Getting help

- Search the [GitHub Issues](https://github.com/yumiaura/myCat/issues) for similar problems.
- Read [CONTRIBUTING.md](CONTRIBUTING.md) for development setup.
- Open a new issue with your OS, desktop environment, Python version and any terminal errors.

### License

[MIT License](LICENSE.txt)

Thank you for reading to the end! 😸🐾

<p class="badges">
  <a href="https://buymeacoffee.com/yumiaura"><img src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support-FFDD00?logo=buymeacoffee&logoColor=000" alt="Buy Me a Coffee"></a>
  <a href="https://www.patreon.com/yumiaura"><img src="https://img.shields.io/badge/Patreon-support-F96854?logo=patreon&logoColor=fff" alt="Patreon"></a>
</p>

---


name: 'README.md'
description: 'myCat Desktop Pet — QT Overlay'
created_date: '2026/05/01'
modified_date: '2026/08/21'
project_version: '0.2.6'
document_version: '1.0.1'
agent_sign: ['human/mimas', 'opencode/current']
---

# myCat Voice Assistant Fork

這個分支為 myCat 加入本機端語音助理功能。

---

## 🎙️ Voice Assistant (myCat + Voice)

![mycat2](./docs/mycat2.png) ![mycat2-2](./docs/mycat2-2.png)

> **🧪 實驗性功能：本機端語音助理**
> 我們為 myCat 打造了本機端語音助理：用語音 VAD 偵測喚醒貓咪，並用語音下達指令
> （透過 faster-whisper 轉寫）。多執行緒架構 (QThread 整合) 保證貓咪動畫在您說話時依然滑順不卡頓。
>
> 已實作 `cat2` 角色包的語音反應（需自備 Ollama + faster-whisper）：
>
> - 👂 **聆聽 (listen.png)** — VAD 觸發時覆蓋貓臉，顯示聆聽姿態
> - 🤔 **思考 (think.png)** — ASR 轉寫中，貓咪歪頭等待
> - 🥱 **打哈欠 (yawn.png)** — 語音靜默 30 秒後自動觸發（可設定、可關閉）
> - 💬 **氣泡回覆** — Ollama 回應以浮動氣泡顯示：X11/Sway 為獨立 xdg_popup 視窗；GNOME 等 Wayland 環境自動改用視窗內繪製，同樣不受平鋪管理限制
> - 😺 **表情疊圖修復** — 語音 overlay 活躍時自動隱藏靜態臉與瞳孔，不疊圖
> - 🎤 **輸入裝置自動偵測** — 啟動時自動選擇 PulseAudio/PipeWire，支援 GUI 手動切換
> - ⚡ **ASR 暖啟動** — 啟動時預載模型，SLEEP 時釋放記憶體
>
> **啟用方式**：
>
> ```bash
> pip install "mycat[voice]"     # 語音依賴：pyaudio + faster-whisper
> ollama pull llama3.1           # 對話模型（見上方 Chat 段落）
> ```
>
> 選項集中在 `mycat/voice_assistant/config.yaml`：`audio.device_index`（null=自動偵測）、
> `asr.model_size` / `asr.language`、`overlay.idle_yawn_after`（打哈欠閾值秒數，0 關閉）等。
>
> **實機畫面預覽：**
>
> ![ASR 轉寫中，貓咪歪頭等待](./docs/mycat2-think.png) ![Ollama 浮動氣泡回覆](./docs/mycat2-voice-interaction.png)
> ![靜默 30 秒打哈欠](./docs/mycat2-yawn.png) ![靜默入睡](./docs/mycat2-sleep.png)
> ![一般待機狀態](./docs/mycat2-general.png)
>
> 由左至右、由上至下：🤔 ASR 轉寫思考 → 💬 Ollama 氣泡回覆 → 🥱 靜默 30 秒打哈欠 → 😴 入睡 → 😺 一般待機。
