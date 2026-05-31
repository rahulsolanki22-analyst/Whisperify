# 🎵 Whisperify

> A seamless, lightweight, and robust synced lyric overlay provider for **Spotify Web Player** and **YouTube Watch Pages**! Interfaced with an asynchronous FastAPI backend and a custom Manifest V3 Chrome Extension.

---

## 🚀 Key Features

* **Multi-Platform Integration**: Automatically detects and operates seamlessly on both `open.spotify.com` and `youtube.com/watch` pages.
* **Sleek UI Overlay Panel**: A premium, draggable, glassmorphic UI container designed to match native dark system color palettes.
* **100ms High-Precision Sync**: Actively monitors playback progress timers and updates scrolling lyric segment highlights in real-time.
* **Spotify React-DOM Latency Compensation**: Integrates a custom `350ms` time offset calculation to align visual changes perfectly with the audio buffer.
* **HTML5 Video Native Capture**: Zero-latency timeline syncing on YouTube by scraping playback timings directly from the browser's native `<video>` element.
* **Robust 3-Tier Fallback Backend**:
  1. Checks local SQLite cache for instant matching.
  2. Queries public synced lyrics databases (**LRCLIB API**) in real-time and caches them locally.
  3. *(Optional)* Audio Capture & AI Whisper/Groq API segment transcribing.

---

## 📂 Repository Structure

```
d:\Spotifind/
├── .gitignore          # Keeps build and DB files out of GitHub
├── README.md           # Project documentation homepage
├── backend/            # Python FastAPI service layer
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py
│       ├── main.py     # Application entry point & lifespan DB migrations
│       ├── database.py # Async SQLAlchemy & SQLite connection settings
│       ├── models.py   # CachedLyrics model schemas
│       ├── schemas.py  # Pydantic validation structures
│       ├── routes/
│       │   └── lyrics.py
│       └── services/
│           ├── lyrics_service.py # LRCLIB client & LRC time parser
│           └── ai_service.py     # OpenAI / Groq Whisper endpoints
└── extension/          # Manifest V3 Chrome Extension
    ├── manifest.json   # Chrome match-patterns & scopes
    ├── content.js      # DOM Scrapers, Observers, Sync timers & Drag listeners
    └── styles.css      # Floating glassmorphic stylesheet
```

---

## 🛠️ Installation & Setup

### Part 1: Start the Backend Server

The backend requires **Python 3.10+** and a running local environment.

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a Python virtual environment:
   ```bash
   # On Windows
   python -m venv venv
   .\venv\Scripts\Activate.ps1

   # On macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. *(Optional)* Set up your Whisper API credentials if enabling AI transcription fallbacks:
   ```bash
   # Windows PowerShell
   $env:OPENAI_API_KEY="your-key"
   $env:GROQ_API_KEY="your-key"

   # macOS/Linux Bash
   export OPENAI_API_KEY="your-key"
   export GROQ_API_KEY="your-key"
   ```
5. Start the development server:
   ```bash
   python -m app.main
   ```
   *The application will automatically perform SQLite database table migrations and start listening on `http://127.0.0.1:8080`.*

---

### Part 2: Load the Extension into Google Chrome

1. Open **Google Chrome**.
2. Navigate to your Extensions dashboard: `chrome://extensions/`.
3. In the top-right corner, toggle **Developer mode** to **ON**.
4. Click the **Load unpacked** button in the top-left corner.
5. In the file picker, select the **`extension/`** folder of this repository.
6. Open [open.spotify.com](https://open.spotify.com) or [youtube.com](https://youtube.com), play a track, click the **Whisperify** header bar to expand the overlay, and enjoy real-time synced lyrics!

---

## ☁️ Deployment

### 1. Deploying the Backend
* Push the repository to GitHub.
* Set up a **Web Service** on [Render](https://render.com/) or [Railway](https://railway.app/).
* Set the Build Command to `pip install -r backend/requirements.txt` and Start Command to `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
* Add your API Keys (like `OPENAI_API_KEY`) as cloud environment variables.

### 2. Updating the Extension API URL
Before sharing or uploading the extension, open `extension/content.js` and change `apiBaseUrl` from your localhost address to your public cloud endpoint:
```javascript
let apiBaseUrl = "https://your-app-name.onrender.com/api/v1";
```
