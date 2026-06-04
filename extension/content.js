/**
 * Whisperify - Spotify & YouTube Fallback Synced Lyric Provider
 * Content Script (Manifest V3) - Simplified Edition
 */

// Global State
let currentTrack = { title: "", artist: "" };
let isSearching = false;
let apiBaseUrl = "https://whisperify-2.onrender.com/api/v1";
let syncInterval = null;
let activeTimestamps = null;
let lastActiveIndex = -1;
let currentLyricsData = null;
let currentSelectedScript = "original";
let scrapedLyricsSent = false;

const isYouTube = window.location.hostname.includes("youtube.com");

// DOM References
let panelElement = null;

// Initialize on Script Load
initWhisperify();

/**
 * Main Initialization Coordinator
 */
function initWhisperify() {
  console.log("Whisperify: Loading Extension Content Script...");
  try {
    injectFloatingPanel();
    console.log("Whisperify: Floating panel successfully injected into DOM.");
  } catch (err) {
    console.error("Whisperify: Failed to inject floating panel:", err);
  }
  
  try {
    setupTrackObservers();
    console.log("Whisperify: Observers initialized successfully.");
  } catch (err) {
    console.error("Whisperify: Failed to initialize observers:", err);
  }
}

/**
 * Injects the Whisperify floating panel into the UI overlay
 */
function injectFloatingPanel() {
  if (document.getElementById("whisperify-overlay")) return;

  panelElement = document.createElement("div");
  panelElement.id = "whisperify-overlay";
  panelElement.className = "whisperify-panel collapsed"; // Start collapsed to be unobtrusive

  panelElement.innerHTML = `
    <div class="whisperify-header" id="whisperify-hdr">
      <div class="whisperify-title-container">
        <span class="whisperify-logo-dot"></span>
        <span class="whisperify-title">Whisperify</span>
      </div>
      <button class="whisperify-toggle-btn" aria-label="Toggle Panel">▼</button>
    </div>
    
    <div class="whisperify-body">
      <!-- State: Idle -->
      <div class="whisperify-state whisperify-state-idle active" id="state-idle">
        <div class="idle-icon">🎵</div>
        <p>Start playing a song to view synced lyrics.</p>
      </div>
      
      <!-- State: Searching -->
      <div class="whisperify-state whisperify-state-searching" id="state-searching">
        <div class="whisperify-spinner"></div>
        <div class="whisperify-searching-song" id="searching-track-title">Searching...</div>
        <p>Fetching lyrics from Whisperify fallback backend...</p>
      </div>
      
      <!-- State: Lyrics -->
      <div class="whisperify-state whisperify-state-lyrics" id="state-lyrics">
        <div class="whisperify-metadata-bar">
          <h3 class="whisperify-song-meta" id="lyrics-song-title">Song Title</h3>
          <p class="whisperify-artist-meta" id="lyrics-song-artist">Artist Name</p>
          <span class="whisperify-source-badge" id="lyrics-source">Source</span>
        </div>
        <div class="whisperify-lyrics-container" id="lyrics-text-block">
          <!-- Lyrics lines will insert here -->
        </div>
      </div>
      
      <!-- State: Error / Not Found -->
      <div class="whisperify-state whisperify-state-error" id="state-error">
        <div class="whisperify-error-icon">⚠️</div>
        <div class="whisperify-error-title">No Lyrics Found</div>
        <p class="whisperify-error-msg" id="error-message">Could not fetch lyrics for this song.</p>
        <button class="whisperify-retry-btn" id="whisperify-retry-trigger">Retry Search</button>
      </div>
    </div>
  `;

  document.body.appendChild(panelElement);

  // Initialize smooth drag movement
  makePanelDraggable();

  // Bind Retry Action
  const retryBtn = document.getElementById("whisperify-retry-trigger");
  retryBtn.addEventListener("click", (e) => {
    e.stopPropagation(); // Avoid triggering header click
    checkAndFetchLyrics(true); // Force search
  });
}

/**
 * Routes Now-Playing Element scraping based on platform
 */
function scrapeNowPlaying() {
  if (isYouTube) {
    return scrapeYouTubePlaying();
  } else {
    return scrapeSpotifyPlaying();
  }
}

/**
 * Scrapes Spotify Now-Playing Elements with robust selector chains.
 */
function scrapeSpotifyPlaying() {
  const titleSelectors = [
    "[data-testid='now-playing-widget'] [data-testid='context-item-link']",
    "[data-testid='nowplaying-track-link']",
    "a[data-testid='context-item-info-title']",
    "[data-testid='track-info-name'] a",
    ".now-playing-bar a[href*='/track/']"
  ];

  const artistSelectors = [
    "[data-testid='now-playing-widget'] [data-testid='context-item-info-subtitles'] a",
    "[data-testid='now-playing-widget'] [data-testid='context-item-info-artist']",
    "a[data-testid='context-item-info-artist']",
    "[data-testid='track-info-artists'] a",
    ".now-playing-bar a[href*='/artist/']"
  ];

  let title = "";
  let artist = "";

  for (const selector of titleSelectors) {
    const el = document.querySelector(selector);
    if (el && el.textContent.trim()) {
      title = el.textContent.trim();
      break;
    }
  }

  for (const selector of artistSelectors) {
    const el = document.querySelector(selector);
    if (el && el.textContent.trim()) {
      artist = el.textContent.trim();
      break;
    }
  }

  return { title, artist };
}

/**
 * Scrapes YouTube Watch-Page metadata elements
 */
function scrapeYouTubePlaying() {
  const titleSelectors = [
    "h1.ytd-watch-metadata yt-formatted-string",
    "h1.ytd-watch-metadata",
    "ytd-watch-metadata #title h1",
    "#container h1.title yt-formatted-string",
    "#container h1.title"
  ];

  const channelSelectors = [
    "ytd-channel-name a",
    "#upload-info #channel-name a",
    "#owner-name a"
  ];

  let rawTitle = "";
  let rawChannel = "";

  for (const s of titleSelectors) {
    const el = document.querySelector(s);
    if (el && el.textContent.trim()) {
      rawTitle = el.textContent.trim();
      break;
    }
  }

  for (const s of channelSelectors) {
    const el = document.querySelector(s);
    if (el && el.textContent.trim()) {
      rawChannel = el.textContent.trim();
      break;
    }
  }

  return cleanYouTubeTitle(rawTitle, rawChannel);
}

/**
 * Splits and cleans YouTube titles to extract Artist and Song
 */
function cleanYouTubeTitle(rawTitle, rawChannel) {
  if (!rawTitle) return { title: "", artist: "" };

  let clean = rawTitle
    .replace(/\((Official|Lyric|Audio|Music|Studio|Video|Live|HD|HQ)\s*(Video|Audio|Version|Film|Clip|Track)?\)/gi, "")
    .replace(/\[(Official|Lyric|Audio|Music|Studio|Video|Live|HD|HQ)\s*(Video|Audio|Version|Film|Clip|Track)?\]/gi, "")
    .replace(/\b(official video|official audio|music video|lyric video|lyrics|audio only|hd|hq|live version|4k)\b/gi, "")
    .replace(/\s+/g, " ")
    .trim();

  const splitters = [" - ", " – ", " — ", " | "];
  for (const splitter of splitters) {
    if (clean.includes(splitter)) {
      const parts = clean.split(splitter);
      const artist = parts[0].trim();
      let song = parts[1].trim();

      song = song.replace(/^['"]|['']$/g, "");
      return { title: song, artist: artist };
    }
  }

  const cleanArtist = rawChannel.replace(/\s*-\s*Topic$/i, "").trim();
  return { title: clean, artist: cleanArtist || "Unknown Artist" };
}

/**
 * Sets up MutationObserver and Polling checks for track changes
 */
function setupTrackObservers() {
  let debounceTimeout = null;

  const onMetadataMutated = () => {
    clearTimeout(debounceTimeout);
    debounceTimeout = setTimeout(() => {
      checkAndFetchLyrics();
    }, 400);
  };

  if (isYouTube) {
    window.addEventListener("yt-navigate-finish", () => {
      console.log("Whisperify: YouTube Navigation Event detected.");
      checkAndFetchLyrics();
    });
  } else {
    const mainObserver = new MutationObserver((mutations) => {
      const playerWidget = document.querySelector("[data-testid='now-playing-widget']");
      if (playerWidget) {
        onMetadataMutated();
      }
    });

    mainObserver.observe(document.body, {
      childList: true,
      subtree: true
    });
  }

  // Failsafe polling interval checks
  setInterval(() => {
    checkAndFetchLyrics();
  }, 2000);
}

/**
 * Scrapes lyrics dynamically from the Spotify page if the lyrics tab/modal is open
 */
function scrapeSpotifyLyrics() {
  if (isYouTube) return null;

  // Find lyric lines directly in the DOM
  const lineSelectors = [
    "[data-testid='lyrics-line']",
    ".lyrics-lyricsContent-lyric",
    "[class*='lyricsContent-lyric']"
  ];

  let found = [];
  for (const s of lineSelectors) {
    const elements = document.querySelectorAll(s);
    if (elements && elements.length > 0) {
      found = Array.from(elements)
        .map(el => el.textContent.trim())
        .filter(t => t.length > 0 && t !== "..." && !t.toLowerCase().startsWith("lyrics provider"));
      if (found.length > 0) {
        console.log(`Whisperify: Scraped ${found.length} lines directly using selector '${s}'`);
        break;
      }
    }
  }

  if (found.length > 0) {
    return found.join("\n");
  }
  
  // Fallback: search for any paragraph/div inside a generic lyrics wrapper if standard selectors failed
  const wrapper = document.querySelector("[class*='lyrics']");
  if (wrapper) {
    const paragraphs = wrapper.querySelectorAll("p, div");
    if (paragraphs && paragraphs.length > 0) {
      const text = Array.from(paragraphs)
        .map(el => el.textContent.trim())
        .filter(t => t.length > 0 && t.length < 200 && !t.toLowerCase().startsWith("lyrics provider"));
      if (text.length > 5) {
        console.log("Whisperify: Scraped lines using fallback wrapper paragraph match");
        return text.join("\n");
      }
    }
  }

  return null;
}

/**
 * Coordinates verifying track details and calling FastAPI backend
 */
async function checkAndFetchLyrics(force = false) {
  const currentScraped = scrapeNowPlaying();
  
  if (!currentScraped.title || !currentScraped.artist) {
    if (currentTrack.title !== "") {
      currentTrack = { title: "", artist: "" };
      setPanelState("idle");
      currentLyricsData = null;
      scrapedLyricsSent = false;
    }
    return;
  }

  const isNewSong = currentScraped.title !== currentTrack.title || currentScraped.artist !== currentTrack.artist;
  
  if (isNewSong || force) {
    currentTrack = currentScraped;
    currentLyricsData = null;
    scrapedLyricsSent = false;
    console.log(`Whisperify: Track Changed -> ${currentTrack.title} by ${currentTrack.artist}`);
    
    if (panelElement && panelElement.classList.contains("collapsed")) {
      panelElement.classList.remove("collapsed");
    }

    const scraped = scrapeSpotifyLyrics();
    if (scraped) {
      scrapedLyricsSent = true;
      await fetchLyricsFromBackend(currentTrack.title, currentTrack.artist, scraped);
    } else {
      await fetchLyricsFromBackend(currentTrack.title, currentTrack.artist);
    }
  } else {
    // If lyrics are not yet loaded and we haven't scraped for this track, try scraping now
    if (!currentLyricsData && !isSearching && !scrapedLyricsSent) {
      const scraped = scrapeSpotifyLyrics();
      if (scraped) {
        scrapedLyricsSent = true;
        console.log("Whisperify: Detected Spotify page lyrics. Uploading...");
        await fetchLyricsFromBackend(currentTrack.title, currentTrack.artist, scraped);
      }
    }
  }
}

/**
 * Communicates with async FastAPI backend via POST requests
 */
async function fetchLyricsFromBackend(title, artist, scrapedLyricsText = null) {
  if (isSearching) return;
  isSearching = true;

  setPanelState("searching");
  document.getElementById("searching-track-title").textContent = title;

  try {
    const response = await fetch(`${apiBaseUrl}/lyrics`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        artist: artist,
        song_title: title,
        scraped_lyrics_text: scrapedLyricsText
      })
    });

    if (response.ok) {
      const data = await response.json();
      displayLyrics(data);
    } else {
      showError("Lyrics not found in text databases.");
    }
  } catch (error) {
    console.error("Whisperify: Backend Connection Failure:", error);
    showError("Could not connect to Whisperify backend. Please ensure the server is running at http://localhost:8080.");
  } finally {
    isSearching = false;
  }
}

/**
 * Updates UI to present found lyrics and initialize playback sync
 */
function displayLyrics(data) {
  const hasLyrics = (data.timestamps && data.timestamps.length > 0) || (data.lyrics_text && data.lyrics_text.trim().length > 0);
  
  if (!hasLyrics) {
    currentLyricsData = null;
    showError("Lyrics not found in text databases.");
    return;
  }

  currentLyricsData = data;
  currentSelectedScript = "original";
  
  setPanelState("lyrics");
  
  if (syncInterval) {
    clearInterval(syncInterval);
    syncInterval = null;
  }
  
  document.getElementById("lyrics-song-title").textContent = data.song_title;
  document.getElementById("lyrics-song-artist").textContent = data.artist;
  
  const sourceBadge = document.getElementById("lyrics-source");
  sourceBadge.textContent = `${data.source}${data.is_cached ? " (cached)" : ""}`;

  // Handle Selector Bar Injection/Visibility
  const metadataBar = document.querySelector(".whisperify-metadata-bar");
  let selectorBar = document.getElementById("script-selector-bar");
  
  // Create selector bar if it doesn't exist
  if (!selectorBar) {
    selectorBar = document.createElement("div");
    selectorBar.id = "script-selector-bar";
    selectorBar.className = "whisperify-script-selector";
    metadataBar.appendChild(selectorBar);
  }
  
  // Check if we have transliteration/translation data available
  const hasTranslations = !!(data.romanized_text || data.translated_text);
  
  if (hasTranslations) {
    selectorBar.style.display = "flex";
    selectorBar.innerHTML = `
      <button class="whisperify-pill active" data-type="original">Original</button>
      ${data.romanized_text ? '<button class="whisperify-pill" data-type="roman">Hinglish</button>' : ''}
      ${data.translated_text ? '<button class="whisperify-pill" data-type="english">English</button>' : ''}
    `;
    
    // Attach event listeners to pills
    const pills = selectorBar.querySelectorAll(".whisperify-pill");
    pills.forEach(pill => {
      pill.addEventListener("click", (e) => {
        e.stopPropagation();
        const selectedType = pill.getAttribute("data-type");
        if (selectedType === currentSelectedScript) return;
        
        pills.forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        
        currentSelectedScript = selectedType;
        renderActiveLyrics(selectedType);
      });
    });
  } else {
    selectorBar.style.display = "none";
    selectorBar.innerHTML = "";
  }

  renderActiveLyrics("original");
}

function renderActiveLyrics(type) {
  if (!currentLyricsData) return;
  
  if (syncInterval) {
    clearInterval(syncInterval);
    syncInterval = null;
  }
  
  const textContainer = document.getElementById("lyrics-text-block");
  textContainer.innerHTML = ""; // Reset block
  
  let timestamps = null;
  let fallbackText = "";
  
  if (type === "roman") {
    timestamps = currentLyricsData.romanized_timestamps;
    fallbackText = currentLyricsData.romanized_text;
  } else if (type === "english") {
    timestamps = currentLyricsData.translated_timestamps;
    fallbackText = currentLyricsData.translated_text;
  } else {
    timestamps = currentLyricsData.timestamps;
    fallbackText = currentLyricsData.lyrics_text;
  }
  
  if (timestamps && timestamps.length > 0) {
    console.log(`Whisperify: Synced lyrics loaded (${type}: ${timestamps.length} lines). Starting sync loop.`);
    
    timestamps.forEach((line, index) => {
      const p = document.createElement("p");
      p.className = "lyric-line";
      p.setAttribute("data-time", line.time);
      p.setAttribute("data-index", index);
      p.textContent = line.text;
      textContainer.appendChild(p);
    });
    
    startLyricsSync(timestamps);
  } else if (fallbackText) {
    console.log(`Whisperify: Plain text lyrics loaded (${type}). Displaying static block.`);
    const p = document.createElement("p");
    p.style.whiteSpace = "pre-line";
    p.style.lineHeight = "1.8";
    p.style.fontSize = "15px";
    p.style.fontWeight = "600";
    p.textContent = fallbackText;
    textContainer.appendChild(p);
  } else {
    textContainer.textContent = "Empty lyrics response from source.";
  }
}

/**
 * Initializes the real-time time-sync highlight loop (100ms high-precision polling rate)
 */
function startLyricsSync(timestamps) {
  const LATENCY_COMPENSATION = 0.35; // Compensate for Spotify React DOM time render lags (350ms)
  activeTimestamps = timestamps;
  lastActiveIndex = -1;
  
  if (syncInterval) clearInterval(syncInterval);
  
  syncInterval = setInterval(() => {
    if (!activeTimestamps || activeTimestamps.length === 0) return;
    
    const currentTime = getPlaybackPosition();
    if (currentTime === null) return;
    
    const adjustedTime = currentTime + (isYouTube ? 0.0 : LATENCY_COMPENSATION);
    
    let activeIndex = -1;
    for (let i = 0; i < activeTimestamps.length; i++) {
      if (adjustedTime >= activeTimestamps[i].time) {
        activeIndex = i;
      } else {
        break;
      }
    }
    
    if (activeIndex !== -1 && activeIndex !== lastActiveIndex) {
      highlightLyricLine(activeIndex);
      lastActiveIndex = activeIndex;
    }
  }, 100);
}

/**
 * Highlights the target lyric line and smooth scrolls it into the center of the panel
 */
function highlightLyricLine(index) {
  const container = document.getElementById("lyrics-text-block");
  const lines = container.querySelectorAll(".lyric-line");
  
  lines.forEach((lineEl, i) => {
    if (i === index) {
      lineEl.classList.add("active");
      lineEl.scrollIntoView({
        behavior: "smooth",
        block: "center"
      });
    } else {
      lineEl.classList.remove("active");
    }
  });
}

/**
 * Gets the current playback progress (in seconds) from the platform's media player
 */
function getPlaybackPosition() {
  if (isYouTube) {
    const video = document.querySelector("video");
    return video ? video.currentTime : null;
  }

  const timeSelectors = [
    "[data-testid='playback-position']",
    ".playback-bar__progress-time",
    "div[class*='playback-bar'] div:first-child"
  ];
  
  for (const selector of timeSelectors) {
    const el = document.querySelector(selector);
    if (el && el.textContent.trim()) {
      return parseTimeStringToSeconds(el.textContent.trim());
    }
  }
  return null;
}

/**
 * Converts "MM:SS" or "HH:MM:SS" time strings into pure float seconds
 */
function parseTimeStringToSeconds(timeStr) {
  try {
    const parts = timeStr.split(":");
    if (parts.length === 2) {
      const minutes = parseInt(parts[0], 10);
      const seconds = parseFloat(parts[1]);
      return minutes * 60 + seconds;
    } else if (parts.length === 3) {
      const hours = parseInt(parts[0], 10);
      const minutes = parseInt(parts[1], 10);
      const seconds = parseFloat(parts[2]);
      return hours * 3600 + minutes * 60 + seconds;
    }
  } catch (err) {
    console.error("Whisperify: Error parsing playback position:", err);
  }
  return parseFloat(timeStr) || 0;
}

/**
 * Helper: switch panels states
 */
function setPanelState(stateName) {
  const states = ["idle", "searching", "lyrics", "error"];
  states.forEach(s => {
    const el = document.getElementById(`state-${s}`);
    if (el) {
      if (s === stateName) {
        el.classList.add("active");
      } else {
        el.classList.remove("active");
      }
    }
  });
}

/**
 * Formats time in float seconds to MM:SS string
 */
function formatTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

/**
 * Renders error status
 */
function showError(message) {
  if (syncInterval) {
    clearInterval(syncInterval);
    syncInterval = null;
  }
  
  setPanelState("error");
  const msgEl = document.getElementById("error-message");
  msgEl.textContent = message;
  
  const retryBtn = document.getElementById("whisperify-retry-trigger");
  retryBtn.textContent = "Retry Search";
  
  currentLyricsData = null;
}

/**
 * Premium Drag-and-Drop system with viewport clamping and click collision resolution
 */
function makePanelDraggable() {
  const header = document.getElementById("whisperify-hdr");
  if (!header || !panelElement) return;

  let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
  let isDragging = false;

  header.addEventListener("mousedown", dragMouseDown);

  function dragMouseDown(e) {
    if (e.target.closest(".whisperify-toggle-btn")) return;
    
    e.preventDefault();
    pos3 = e.clientX;
    pos4 = e.clientY;
    isDragging = false;
    
    document.onmouseup = closeDragElement;
    document.onmousemove = elementDrag;
  }

  function elementDrag(e) {
    e.preventDefault();
    
    const deltaX = Math.abs(pos3 - e.clientX);
    const deltaY = Math.abs(pos4 - e.clientY);
    
    if (deltaX > 4 || deltaY > 4) {
      isDragging = true;
    }

    pos1 = pos3 - e.clientX;
    pos2 = pos4 - e.clientY;
    pos3 = e.clientX;
    pos4 = e.clientY;

    let newTop = panelElement.offsetTop - pos2;
    let newLeft = panelElement.offsetLeft - pos1;

    const minLeft = 10;
    const maxLeft = window.innerWidth - panelElement.offsetWidth - 10;
    const minTop = 10;
    const maxTop = window.innerHeight - panelElement.offsetHeight - 10;

    if (newLeft < minLeft) newLeft = minLeft;
    if (newLeft > maxLeft) newLeft = maxLeft;
    if (newTop < minTop) newTop = minTop;
    if (newTop > maxTop) newTop = maxTop;

    panelElement.style.top = newTop + "px";
    panelElement.style.left = newLeft + "px";
    panelElement.style.right = "auto";
  }

  function closeDragElement(e) {
    document.onmouseup = null;
    document.onmousemove = null;
    
    if (!isDragging) {
      panelElement.classList.toggle("collapsed");
    }
  }
}
