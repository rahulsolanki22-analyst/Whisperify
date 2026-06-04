/**
 * Whisperify Background Service Worker (Manifest V3)
 * Manages global lyric synchronization state and coordinates messages between player tabs and displays.
 */

// Global state cache
let syncState = {
  currentTrack: { title: "", artist: "" },
  lyricsData: null,
  currentTime: 0,
  isYouTube: false,
  scriptType: "original",
  collapsed: true,
  position: { top: "80px", left: "auto", right: "24px" }
};

// Listen for messages from content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "UPDATE_PLAYBACK") {
    syncState.currentTrack = { title: message.title, artist: message.artist };
    syncState.currentTime = message.currentTime;
    syncState.isYouTube = message.isYouTube;
    
    // Broadcast playback update to all tabs (except the sender)
    broadcastMessage({
      type: "SYNC_PLAYBACK",
      currentTime: message.currentTime,
      isYouTube: message.isYouTube,
      title: message.title,
      artist: message.artist
    }, sender.tab.id);
  } 
  
  else if (message.type === "UPDATE_LYRICS") {
    syncState.lyricsData = message.lyricsData;
    // Reset script selection for new songs
    syncState.scriptType = "original";
    
    // Broadcast lyrics update to all tabs
    broadcastMessage({
      type: "SYNC_LYRICS",
      lyricsData: message.lyricsData
    });
  } 
  
  else if (message.type === "CHANGE_SCRIPT") {
    syncState.scriptType = message.scriptType;
    broadcastMessage({
      type: "SYNC_SCRIPT",
      scriptType: message.scriptType
    });
  } 
  
  else if (message.type === "TOGGLE_PANEL") {
    syncState.collapsed = message.collapsed;
    broadcastMessage({
      type: "SYNC_COLLAPSE",
      collapsed: message.collapsed
    });
  } 
  
  else if (message.type === "MOVE_PANEL") {
    syncState.position = { top: message.top, left: message.left, right: "auto" };
    broadcastMessage({
      type: "SYNC_POSITION",
      position: syncState.position
    });
  } 
  
  else if (message.type === "GET_SYNC_STATE") {
    sendResponse(syncState);
  }
  
  return true; // Keep message channel open for async sendResponse
});

/**
 * Broadcasts a message to all tabs except the excluded tab
 */
function broadcastMessage(payload, excludeTabId = null) {
  chrome.tabs.query({}, (tabs) => {
    tabs.forEach((tab) => {
      if (tab.id === excludeTabId) return;
      
      chrome.tabs.sendMessage(tab.id, payload, (response) => {
        // Ignore errors from tabs that don't have our content script loaded
        if (chrome.runtime.lastError) {
          return;
        }
      });
    });
  });
}
