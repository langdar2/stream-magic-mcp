const API_BASE = "/api";
let availableTools = [];
let currentServerLocation = localStorage.getItem("lastDlnaServer") || null;
let currentPathStack = [];
let playbackQueue = [];
let currentQueueIndex = -1;
let isAutoPlaying = false;
let searchState = { isSearching: false, query: "" };

document.addEventListener("DOMContentLoaded", () => {
    fetchTools();

    // Check local storage for host
    const cachedHost = localStorage.getItem("STREAMMAGIC_HOST");
    if (cachedHost) {
        log(`Using cached host: ${cachedHost}`);
        document.getElementById("status-indicator").classList.remove("offline");
        document.getElementById("status-indicator").classList.add("online");
        document.getElementById("status-indicator").textContent = `Connected (${cachedHost})`;

        // Initial fetch of state
        executeTool("get_now_playing", { host: cachedHost });
        executeTool("get_state", { host: cachedHost });
        startPolling(cachedHost);
    } else {
        log("No host configured. Please scan for devices.");
        document.getElementById("status-indicator").textContent = "Not Configured";
    }

    // Auto-reconnect to DLNA if possible
    if (currentServerLocation) {
        log(`Restoring DLNA session: ${currentServerLocation}`);
        browseServer(currentServerLocation, "0");
    }
});

async function fetchTools() {
    const headActions = document.getElementById("header-actions");
    try {
        const response = await fetch(`${API_BASE}/tools`);
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Server returned ${response.status}: ${errorText}`);
        }

        const tools = await response.json();
        if (!Array.isArray(tools)) {
            if (tools.detail) throw new Error(tools.detail);
            throw new Error(`Invalid response format: ${JSON.stringify(tools)}`);
        }

        availableTools = tools;
        headActions.innerHTML = "";

        // Relocate Discovery Buttons
        if (tools.find(t => t.name === "discover_devices")) {
            const scanBtn = document.createElement("button");
            scanBtn.className = "btn-secondary small";
            scanBtn.innerText = "🔍 Discovery";
            scanBtn.onclick = () => executeDiscovery();

            const manualBtn = document.createElement("button");
            manualBtn.className = "btn-secondary small";
            manualBtn.innerText = "⚙️ Setup";
            manualBtn.onclick = () => showManualConfig();

            headActions.appendChild(scanBtn);
            headActions.appendChild(manualBtn);
        }

        log(`API loaded with ${tools.length} capabilities.`);
    } catch (e) {
        log(`Error fetching tools: ${e.message}`);
    }
}

async function executeDiscovery() {
    log("Scanning for devices (3s timeout)...");
    try {
        const response = await fetch(`${API_BASE}/execute`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tool_name: "discover_devices", arguments: { timeout: 3 } })
        });
        const result = await response.json();

        if (result.status === "error") {
            log(`Scan failed: ${result.output}`);
        } else {
            // Parse JSON output
            try {
                const devices = JSON.parse(result.output);
                log(`Found ${devices.length} devices.`);
                if (devices.length > 0) {
                    showDeviceSelection(devices);
                } else {
                    log("No devices found.");
                }
            } catch (e) {
                log(`Error parsing scan result: ${e.message}`);
                log(`Raw output: ${result.output}`);
            }
        }
    } catch (e) {
        log(`Scan request failed: ${e.message}`);
    }
}

function showDeviceSelection(devices) {
    const listHtml = devices.map(d =>
        `<div class="device-item" onclick="selectDevice('${d.host}')" style="padding:10px; border:1px solid #333; margin:5px; cursor:pointer; border-radius:4px;">
            <strong>${d.name || 'Device'}</strong> (${d.model})<br>
            <small>${d.host}</small>
         </div>`
    ).join("");

    document.getElementById("modal-title").innerText = "Select Device";
    document.getElementById("form-fields").innerHTML = listHtml;
    // Hide actions since clicking item selects
    document.querySelector(".form-actions").style.display = "none";
    document.getElementById("tool-modal").classList.remove("hidden");
}

function selectDevice(host) {
    localStorage.setItem("STREAMMAGIC_HOST", host);
    log(`Selected host: ${host}`);
    document.getElementById("status-indicator").textContent = `Connected (${host})`;
    document.getElementById("status-indicator").classList.remove("offline");
    document.getElementById("status-indicator").classList.add("online");
    closeModal();
    // Refresh state
    executeTool("get_now_playing", { host: host });
    executeTool("get_state", { host: host });
    startPolling(host);
}

function showManualConfig() {
    const cached = localStorage.getItem("STREAMMAGIC_HOST") || "";
    const html = `
        <div class="form-group">
            <label>Device IP Address</label>
            <input type="text" name="host" value="${cached}" placeholder="192.168.1.xxx" required>
            <p style="font-size:0.8rem; color:#888; margin-top:5px;">Enter the local IP address of your Cambridge Audio device.</p>
        </div>
    `;

    document.getElementById("modal-title").innerText = "Manual Configuration";
    document.getElementById("form-fields").innerHTML = html;

    // Show actions, but hijack the submit
    const actions = document.querySelector(".form-actions");
    actions.style.display = "flex";

    // Remove old listeners by cloning
    const oldForm = document.getElementById("tool-form");
    const newForm = oldForm.cloneNode(true);
    oldForm.parentNode.replaceChild(newForm, oldForm);

    newForm.onsubmit = (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const host = formData.get("host");
        if (host) {
            selectDevice(host);
        }
    };

    document.getElementById("tool-modal").classList.remove("hidden");
}

async function executeTool(name, args, isBackground = false) {
    if (!isBackground) log(`> Executing ${name}...`);
    try {
        const response = await fetch(`${API_BASE}/execute`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tool_name: name, arguments: args })
        });

        const result = await response.json();

        if (result.status === "error") {
            if (!isBackground) log(`Error: ${result.output}`);
        } else {
            if (!isBackground) log(`Success:\n${result.output}`);

            // Update UI based on tool
            if (name === "get_now_playing") {
                updateNowPlaying(result.output);
            } else if (name === "get_state") {
                updateState(result.output);
            }
        }
    } catch (e) {
        if (!isBackground) log(`Request failed: ${e.message}`);
    }
}

// Polling
let pollInterval = null;

function startPolling(host) {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(() => {
        // Poll for state and now playing
        executeTool("get_state", { host: host }, true);
        executeTool("get_now_playing", { host: host }, true);
    }, 5000); // Poll every 5 seconds
}

// UI Helpers
function log(msg) {
    console.log(`[${new Date().toLocaleTimeString()}] ${msg}`);
}

// Queue Logic
function updateNowPlaying(jsonString) {
    try {
        log(`Raw NowPlaying: ${jsonString}`); // Debug log
        const data = JSON.parse(jsonString);
        const titleEl = document.getElementById("np-title");
        const artistEl = document.getElementById("np-artist");
        const albumEl = document.getElementById("np-album");
        const artImg = document.getElementById("np-art");
        const placeholder = document.getElementById("np-placeholder");
        const badgesEl = document.getElementById("np-badges");

        if (data.metadata && data.metadata.title) {
            const m = data.metadata;
            titleEl.innerText = m.title || "Unknown Title";
            artistEl.innerText = m.artist || "";
            albumEl.innerText = m.album || "";

            // Cover Art
            if (m.art_url) {
                artImg.src = m.art_url;
                artImg.style.display = "block";
                placeholder.style.display = "none";
            } else {
                artImg.style.display = "none";
                placeholder.style.display = "block";
            }

            // Badges
            badgesEl.innerHTML = "";
            const addBadge = (text) => {
                if (!text) return;
                const span = document.createElement("span");
                span.className = "badge";
                span.innerText = text;
                badgesEl.appendChild(span);
            };

            addBadge(m.codec);
            addBadge(m.sample_rate ? `${m.sample_rate / 1000}kHz` : null);
            addBadge(m.bitrate ? `${m.bitrate}kbps` : null);
            addBadge(m.lossless ? "Lossless" : null);
            addBadge(m.mqa);
            addBadge(m.source);

        } else {
            // Idle state - Check for queue
            if (playbackQueue.length > 0 && currentQueueIndex < playbackQueue.length - 1 && !isAutoPlaying) {
                log("Track finished. Advancing queue...");
                playNextInQueue();
            } else {
                titleEl.innerText = "Ready to Play";
                artistEl.innerText = "Select a source to begin";
                albumEl.innerText = "";
                artImg.style.display = "none";
                placeholder.style.display = "block";
                badgesEl.innerHTML = "";
            }
        }
    } catch (e) {
        log(`Error updating UI: ${e.message}`);
    }
}

async function playNextInQueue() {
    if (currentQueueIndex < playbackQueue.length - 1) {
        isAutoPlaying = true;
        currentQueueIndex++;
        const nextTrack = playbackQueue[currentQueueIndex];
        await playDlnaItem(nextTrack.url, nextTrack.title, nextTrack.metadata, true);
        setTimeout(() => { isAutoPlaying = false; }, 2000); // Debounce
    } else {
        log("End of queue reached.");
        playbackQueue = [];
        currentQueueIndex = -1;
    }
}

function updateState(jsonString) {
    try {
        const data = JSON.parse(jsonString);

        // Update Volume
        if (data.volume_percent !== undefined) {
            const slider = document.getElementById("volume-slider");
            const display = document.getElementById("volume-display");

            // Only update if not currently being dragged (simple check: document.activeElement)
            if (document.activeElement !== slider) {
                slider.value = data.volume_percent;
                display.innerText = `${data.volume_percent}%`;
            }
        }

    } catch (e) {
        // ignore parsing errors for state
    }
}

// Modal Logic
const modal = document.getElementById("tool-modal");

function openToolModal(toolName) {
    const tool = availableTools.find(t => t.name === toolName);
    if (!tool) return;

    // Reset actions visibility in case it was hidden by selection
    document.querySelector(".form-actions").style.display = "flex";

    // Reset Form Listener for standard tools
    const form = document.getElementById("tool-form");
    const newForm = form.cloneNode(true);
    form.parentNode.replaceChild(newForm, form);
    newForm.addEventListener("submit", handleToolSubmit);

    document.getElementById("modal-title").innerText = toolName;
    const formFields = document.getElementById("form-fields");
    formFields.innerHTML = "";

    const props = tool.inputSchema.properties || {};
    const required = tool.inputSchema.required || [];

    if (Object.keys(props).length === 0) {
        formFields.innerHTML = "<p>No arguments required.</p>";
    } else {
        for (const [key, schema] of Object.entries(props)) {
            if (key === "host") continue; // Skip host

            const group = document.createElement("div");
            group.className = "form-group";

            const label = document.createElement("label");
            label.innerText = `${key}${required.includes(key) ? '*' : ''}`;

            let input;
            if (schema.type === "boolean") {
                input = document.createElement("select");
                input.innerHTML = `<option value="true">True</option><option value="false">False</option>`;
            } else if (schema.enum) {
                input = document.createElement("select");
                schema.enum.forEach(opt => {
                    input.innerHTML += `<option value="${opt}">${opt}</option>`;
                });
            } else {
                input = document.createElement("input");
                input.type = schema.type === "integer" ? "number" : "text";
                if (schema.default) input.value = schema.default;
            }

            input.name = key;
            input.dataset.type = schema.type;

            group.appendChild(label);
            group.appendChild(input);
            formFields.appendChild(group);
        }
    }

    modal.dataset.currentTool = toolName;
    modal.classList.remove("hidden");
}

function closeModal() {
    modal.classList.add("hidden");
}

function handleToolSubmit(e) {
    e.preventDefault();
    const toolName = modal.dataset.currentTool;
    const formData = new FormData(e.target);
    const tool = availableTools.find(t => t.name === toolName);

    const args = {};
    const props = tool.inputSchema.properties || {};

    for (const [key, value] of formData.entries()) {
        const type = props[key]?.type;
        if (type === "integer") {
            args[key] = parseInt(value);
        } else if (type === "boolean") {
            args[key] = (value === "true");
        } else {
            args[key] = value;
        }
    }

    // Auto-inject host
    const cachedHost = localStorage.getItem("STREAMMAGIC_HOST");
    if (cachedHost && !args.host) {
        args.host = cachedHost;
    }

    executeTool(toolName, args);
    closeModal();
}

// Shortcuts
function toggleMute() {
    openToolModal("set_mute");
}

// DLNA Browser Logic
// DLNA Browser Logic

async function scanDlnaServers() {
    log("Scanning for DLNA servers...");
    const content = document.getElementById("dlna-content");
    content.innerHTML = '<div class="loading-spinner"></div>';

    try {
        const response = await fetch(`${API_BASE}/execute`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tool_name: "discover_media_servers", arguments: { timeout: 3 } })
        });

        if (!response.ok) {
            const err = await response.text();
            throw new Error(`Server error (${response.status}): ${err}`);
        }

        const result = await response.json();

        if (result.status === "error") {
            log(`Scan failed: ${result.output}`);
            content.innerHTML = `<p class="error">Scan failed: ${result.output}</p>`;
        } else {
            try {
                const servers = JSON.parse(result.output);
                if (servers.length === 0) {
                    content.innerHTML = "<p>No media servers found.</p>";
                } else {
                    renderServerList(servers);
                }
            } catch (parseErr) {
                log(`Failed to parse scan output: ${result.output}`);
                throw new Error("Invalid response format from server.");
            }
        }
    } catch (e) {
        log(`Server scan error: ${e.message}`);
        content.innerHTML = `<p class="error">Error scanning servers: ${e.message}</p>`;
    }
}

function renderServerList(servers) {
    const content = document.getElementById("dlna-content");
    currentPathStack = [];
    updateBrowserPath();

    content.innerHTML = servers.map(s => `
        <div class="dlna-item" onclick="browseServer('${s.location}', '0', '${s.name}')">
            <span class="icon">🖥️</span>
            <div class="info">
                <strong>${s.name}</strong>
                <small>${s.host}</small>
            </div>
        </div>
    `).join("");
}

async function searchDlna() {
    const query = document.getElementById("dlna-search-input").value.trim();
    if (!query || !currentServerLocation) return;

    log(`Searching for "${query}"...`);
    const content = document.getElementById("dlna-content");
    content.innerHTML = '<div class="loading-spinner"></div>';
    document.getElementById("btn-clear-search").classList.remove("hidden");

    try {
        const response = await fetch(`${API_BASE}/execute`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                tool_name: "search_media_server",
                arguments: { location: currentServerLocation, query: query }
            })
        });
        const result = await response.json();

        if (result.status === "error") {
            log(`Search failed: ${result.output}`);
            content.innerHTML = `
                <div class="dlna-item back-item" onclick="clearSearch()">
                    <span class="icon">⬅️</span> <strong>Back to Browsing</strong>
                </div>
                <p class="error" style="padding:20px; text-align:center;">Search failed: ${result.output.split(':').pop().trim()}</p>
            `;
        } else {
            const items = JSON.parse(result.output);
            if (items.length === 0) {
                content.innerHTML = `
                    <div class="dlna-item back-item" onclick="clearSearch()">
                        <span class="icon">⬅️</span> <strong>Back to Browsing</strong>
                    </div>
                    <p style="padding:20px; text-align:center; color:var(--text-muted)">No results found for "${query}"</p>
                `;
            } else {
                renderBrowserItems(items);
                // Override back button for search results
                const backBtn = document.querySelector(".back-item");
                if (backBtn) {
                    backBtn.onclick = clearSearch;
                    backBtn.innerHTML = '<span class="icon">⬅️</span> <strong>Back to Browsing</strong>';
                }
            }
        }
    } catch (e) {
        log(`Search request failed: ${e.message}`);
    }
}

function clearSearch() {
    document.getElementById("dlna-search-input").value = "";
    document.getElementById("btn-clear-search").classList.add("hidden");
    const last = currentPathStack[currentPathStack.length - 1];
    if (last) {
        browseServer(currentServerLocation, last.id, last.title);
    } else {
        scanDlnaServers();
    }
}

async function browseServer(location, objectId = "0", title = "", append = false, startIndex = 0) {
    currentServerLocation = location;
    localStorage.setItem("lastDlnaServer", location);

    if (!append) {
        // Clear search on normal browse
        document.getElementById("dlna-search-input").value = "";
        document.getElementById("btn-clear-search").classList.add("hidden");

        // Update Stack
        if (objectId === "0") {
            currentPathStack = [{ id: "0", title: title }];
        } else if (currentPathStack.length === 0 || currentPathStack[currentPathStack.length - 1].id !== objectId) {
            currentPathStack.push({ id: objectId, title: title });
        }
        updateBrowserPath();

        const content = document.getElementById("dlna-content");
        content.innerHTML = '<div class="loading-spinner"></div>';
    }

    try {
        const response = await fetch(`${API_BASE}/execute`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                tool_name: "browse_media_server",
                arguments: { location: location, object_id: objectId, start_index: startIndex }
            })
        });
        const result = await response.json();

        if (result.status === "error") {
            log(`Browse failed: ${result.output}`);
            if (!append) content.innerHTML = `<p>Error browsing.</p>`;
        } else {
            const data = JSON.parse(result.output);
            const items = data.items;
            const total = data.total;
            renderBrowserItems(items, append, objectId, title, total);
        }
    } catch (e) {
        log(`Browse request failed: ${e.message}`);
    }
}

function renderBrowserItems(items, append = false, currentObjectId = "0", currentTitle = "", totalMatches = 0) {
    const content = document.getElementById("dlna-content");

    if (!append) {
        content.innerHTML = ""; // Clear existing
    } else {
        // Remove old load more button if exists
        const oldLoadMore = document.getElementById("btn-load-more");
        if (oldLoadMore) oldLoadMore.remove();
    }

    if (!append && items.length === 0) {
        content.innerHTML = `
            <div class="dlna-item back-item" onclick="goBack()">
                <span class="icon">⬅️</span> <strong>Back</strong>
            </div>
            <p style="padding:10px; color:var(--text-muted)">Empty folder.</p>
        `;
        return;
    }

    if (!append) {
        // Add Context/Header Items first
        const backBtn = document.createElement("div");
        backBtn.className = "dlna-item back-item";
        backBtn.onclick = goBack;
        backBtn.innerHTML = `<span class="icon">⬅️</span> <strong>Back</strong>`;
        content.appendChild(backBtn);

        const tracks = items.filter(i => !i.is_container && i.res_url);
        window.currentFolderTracks = tracks; // Store for Play All

        if (tracks.length > 1) {
            const actionBar = document.createElement("div");
            actionBar.className = "dlna-action-bar";
            actionBar.innerHTML = `<button class="btn-primary small" onclick="playAllInFolder()">▶️ Play All (${tracks.length})</button>`;
            content.appendChild(actionBar);
        }
    } else {
        // Update Play All list if we appended tracks
        const newTracks = items.filter(i => !i.is_container && i.res_url);
        if (newTracks.length > 0) {
            window.currentFolderTracks = (window.currentFolderTracks || []).concat(newTracks);
            // Update the "Play All" button text if it exists
            const playAllBtn = content.querySelector(".dlna-action-bar button");
            if (playAllBtn) {
                playAllBtn.innerText = `▶️ Play All (${window.currentFolderTracks.length})`;
            } else if (window.currentFolderTracks.length > 1) {
                // Should probably show it if it wasn't there
                const actionBar = document.createElement("div");
                actionBar.className = "dlna-action-bar";
                actionBar.innerHTML = `<button class="btn-primary small" onclick="playAllInFolder()">▶️ Play All (${window.currentFolderTracks.length})</button>`;
                // Insert after back button
                const backBtn = content.querySelector(".back-item");
                if (backBtn) backBtn.after(actionBar);
            }
        }
    }

    // Batched Rendering of actual items
    let index = 0;
    const batchSize = 25;

    function renderBatch() {
        const end = Math.min(index + batchSize, items.length);
        const fragment = document.createDocumentFragment();

        for (; index < end; index++) {
            const item = items[index];
            const div = document.createElement("div");

            if (item.is_container) {
                div.className = "dlna-item folder";
                const escTitle = item.title.replace(/'/g, "\\'");
                div.onclick = () => browseServer(currentServerLocation, item.id, item.title);
                div.innerHTML = `
                    <span class="icon">📁</span>
                    <strong>${item.title}</strong>
                `;
            } else {
                div.className = "dlna-item file";
                const escTitle = item.title.replace(/'/g, "\\'");
                div.innerHTML = `
                    <span class="icon">🎵</span>
                    <div class="info" onclick="playDlnaItem('${item.res_url}', '${escTitle}', '')">
                        <strong>${item.title}</strong>
                        <small>${item.artist || 'Unknown Artist'}</small>
                    </div>
                    <button class="btn-icon small" title="Add to Queue" onclick="addToQueue('${item.res_url}', '${escTitle}', '')">➕</button>
                `;
            }
            fragment.appendChild(div);
        }

        content.appendChild(fragment);

        if (index < items.length) {
            requestAnimationFrame(renderBatch);
        } else {
            // Check if we should show "Load More"
            const totalLoaded = content.querySelectorAll('.dlna-item:not(.back-item)').length;
            if (totalMatches > totalLoaded) {
                const loadMoreBtn = document.createElement("button");
                loadMoreBtn.id = "btn-load-more";
                loadMoreBtn.className = "btn-secondary small";
                loadMoreBtn.style.width = "calc(100% - 20px)";
                loadMoreBtn.style.margin = "10px";
                loadMoreBtn.innerText = `Load More (${totalLoaded} / ${totalMatches})`;
                loadMoreBtn.onclick = () => {
                    loadMoreBtn.innerText = "Loading...";
                    loadMoreBtn.disabled = true;
                    browseServer(currentServerLocation, currentObjectId, currentTitle, true, totalLoaded);
                };
                content.appendChild(loadMoreBtn);
            }
        }
    }

    renderBatch();
}

function goBack() {
    if (currentPathStack.length <= 1) {
        // Back to server list
        scanDlnaServers();
        return;
    }
    currentPathStack.pop(); // Remove current
    const prev = currentPathStack.pop(); // Get previous
    browseServer(currentServerLocation, prev.id, prev.title);
}

function updateBrowserPath() {
    const el = document.getElementById("browser-path");
    const icon = "📁 ";
    if (searchState.isSearching) {
        el.innerText = `🔍 Search: "${searchState.query}"`;
    } else if (currentPathStack.length === 0) {
        el.innerText = icon + "/";
    } else {
        el.innerText = icon + currentPathStack.map(p => p.title).join(" > ");
    }
}

function playAllInFolder() {
    if (!window.currentFolderTracks || window.currentFolderTracks.length === 0) return;

    log(`Playing all ${window.currentFolderTracks.length} tracks...`);
    playbackQueue = window.currentFolderTracks.map(t => ({
        url: t.res_url,
        title: t.title,
        metadata: ""
    }));
    currentQueueIndex = 0;
    const first = playbackQueue[0];
    playDlnaItem(first.url, first.title, first.metadata, true);
}

function addToQueue(url, title, metadata) {
    playbackQueue.push({ url, title, metadata });
    log(`Added to queue: ${title}`);
}

async function playDlnaItem(url, title, metadata, fromQueue = false) {
    if (!fromQueue) {
        // Reset queue if playing manual item
        playbackQueue = [];
        currentQueueIndex = -1;
    }

    log(`Requesting playback of: ${title}`);
    const host = localStorage.getItem("STREAMMAGIC_HOST");
    if (!host) {
        alert("Please connect to a device first.");
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/execute`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                tool_name: "play_stream_url",
                arguments: { url: url, metadata: metadata, host: host }
            })
        });
        const result = await response.json();

        if (result.status === "error") {
            log(`Playback failed: ${result.output}`);
        } else {
            log(`Playback started: ${title}`);
        }
    } catch (e) {
        log(`Playback request error: ${e.message}`);
    }
}

function setVolume(val) {
    document.getElementById("volume-display").innerText = `${val}%`;
}

document.getElementById("volume-slider").onchange = (e) => {
    const cachedHost = localStorage.getItem("STREAMMAGIC_HOST");
    const args = { level: parseInt(e.target.value) };
    if (cachedHost) args.host = cachedHost;

    executeTool("set_volume", args);
};

function controlPlayback(action) {
    const cachedHost = localStorage.getItem("STREAMMAGIC_HOST");
    const args = { action: action };
    if (cachedHost) args.host = cachedHost;

    executeTool("control_playback", args);
}
