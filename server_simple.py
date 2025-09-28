from flask import Flask, render_template_string, jsonify, request
import subprocess
import os
import json
import pandas as pd
import numpy as np

app = Flask(__name__)

# Real-time Debug Session Management
realtime_session = {
    'active': False,
    'current_frame': 0,
    'total_frames': 0,
    'data_frames': [],
    'results': [],
    'start_time': None
}

# Simple HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>ESKF Test Server (Simple)</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f0f0f0; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; text-align: center; }
        .button-panel { text-align: center; margin: 20px 0; }
        button {
            background: #4CAF50; color: white; border: none;
            padding: 10px 30px; font-size: 16px; border-radius: 5px;
            cursor: pointer; margin: 0 10px;
        }
        button:hover { background: #45a049; }
        button:disabled { background: #ccc; cursor: not-allowed; }
        #status {
            background: #f9f9f9; padding: 15px; border-radius: 5px;
            margin: 20px 0; border-left: 4px solid #4CAF50;
        }
        #status.error { border-left-color: #f44336; background: #ffebee; }
        #status.running { border-left-color: #ff9800; background: #fff3e0; }
        #map { height: 700px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); position: relative; }
        .legend {
            position: absolute; top: 10px; right: 10px; z-index: 1000;
            background: white; padding: 10px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            font-size: 12px; min-width: 120px;
        }
        .legend-item {
            margin: 5px 0; cursor: pointer; display: flex; align-items: center;
        }
        .legend-color {
            width: 15px; height: 3px; margin-right: 8px; border-radius: 1px;
        }
        .legend-item.disabled {
            opacity: 0.5; text-decoration: line-through;
        }
        .coordinate-tooltip {
            background: rgba(0,0,0,0.8) !important;
            color: white !important;
            border: none !important;
            border-radius: 4px !important;
            font-size: 11px !important;
            font-family: monospace !important;
            padding: 6px !important;
        }
        .stats {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px; margin: 20px 0;
        }
        .stat {
            background: #e3f2fd; padding: 10px; border-radius: 5px;
            text-align: center;
        }
        .stat-value { font-size: 24px; font-weight: bold; color: #1976d2; }
        .stat-label { color: #666; font-size: 12px; }

        /* Real-time Debug Controls */
        #realtimeControls {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1000;
            background: rgba(255, 255, 255, 0.95);
            border: 2px solid #2196F3;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
        }
        .realtime-panel {
            padding: 15px;
            min-width: 300px;
        }
        .realtime-panel h3 {
            margin: 0 0 15px 0;
            color: #2196F3;
            border-bottom: 2px solid #2196F3;
            padding-bottom: 5px;
        }
        .player-controls {
            display: flex;
            gap: 10px;
            align-items: center;
            margin-bottom: 15px;
        }
        .player-controls button {
            padding: 8px 12px;
            border: 1px solid #ccc;
            border-radius: 4px;
            background: #f5f5f5;
            cursor: pointer;
        }
        .player-controls button:hover {
            background: #e0e0e0;
        }
        .time-scrubber {
            margin-bottom: 15px;
        }
        .time-scrubber input[type="range"] {
            width: 100%;
            margin: 10px 0;
        }
        .time-display {
            text-align: center;
            font-family: monospace;
            font-size: 14px;
        }
        .status-display {
            display: grid;
            gap: 8px;
            margin-bottom: 15px;
        }
        .status-item {
            display: flex;
            justify-content: space-between;
            padding: 5px;
            background: #f9f9f9;
            border-radius: 4px;
        }
        .sat-count {
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 3px;
        }
        .sat-low { background: #ffcdd2; color: #d32f2f; }
        .sat-high { background: #c8e6c9; color: #388e3c; }
    </style>
</head>
<body>
    <div class="container">
        <h1>[SATELLITE] ESKF Navigation Test</h1>

        <div class="button-panel">
            <button id="runPython" onclick="runTest('python')">Run Python Version</button>
            <button id="runCUp" onclick="runTest('c', 'up')">상행 C Version</button>
            <button id="runCDown" onclick="runTest('c', 'down')">하행 C Version</button>
            <button id="runRealtime" onclick="startRealtimeDebug()">Real-time Debug</button>
            <button onclick="clearStatus()">Clear</button>
        </div>

        <div id="status">Click a button to start processing...</div>

        <div class="stats" id="stats" style="display:none;">
            <div class="stat">
                <div class="stat-value" id="gpsCount">0</div>
                <div class="stat-label">GPS Updates</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="imuCount">0</div>
                <div class="stat-label">IMU Updates</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="railCount">0</div>
                <div class="stat-label">Rail Nodes</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="processTime">0s</div>
                <div class="stat-label">Process Time</div>
            </div>
        </div>

        <div id="map">
            <div class="legend" id="legend" style="display:none;">
                <div class="legend-item" data-layer="eskf" onclick="toggleLayer('eskf')">
                    <div class="legend-color" style="background: #2196F3;"></div>
                    <span>ESKF Path</span>
                </div>
                <div class="legend-item" data-layer="gps" onclick="toggleLayer('gps')">
                    <div class="legend-color" style="background: #f44336;"></div>
                    <span>GPS Raw</span>
                </div>
                <div class="legend-item" data-layer="rail" onclick="toggleLayer('rail')">
                    <div class="legend-color" style="background: #4CAF50;"></div>
                    <span>Railway</span>
                </div>
                <div class="legend-item" data-layer="initialization" onclick="toggleLayer('initialization')">
                    <div class="legend-color" style="background: #E91E63; border-radius: 50%;"></div>
                    <span>Init Point</span>
                </div>
                <div class="legend-item" data-layer="gps_recovery" onclick="toggleLayer('gps_recovery')">
                    <div class="legend-color" style="background: #9C27B0; border-radius: 50%;"></div>
                    <span>GPS Recovery</span>
                </div>
            </div>
        </div>

        <!-- Real-time Debug Control Panel (hidden by default) -->
        <div id="realtimeControls" style="display: none;">
            <div class="realtime-panel">
                <h3>Real-time Debug Controls</h3>

                <!-- Player Controls -->
                <div class="player-controls">
                    <button id="playBtn" onclick="togglePlayback()">Play</button>
                    <button id="pauseBtn" onclick="pausePlayback()">Pause</button>
                    <button id="resetBtn" onclick="resetPlayback()">Reset</button>

                    <label>Speed: </label>
                    <select id="speedSelect" onchange="changeSpeed()">
                        <option value="1">1x</option>
                        <option value="2">2x</option>
                        <option value="5">5x</option>
                        <option value="10">10x</option>
                    </select>
                </div>

                <!-- Time Scrubber -->
                <div class="time-scrubber">
                    <input type="range" id="timeSlider" min="0" max="100" value="0" onchange="jumpToTime()">
                    <div class="time-display">
                        <span id="currentTime">00:00:00</span> / <span id="totalTime">00:00:00</span>
                    </div>
                </div>

                <!-- Status Display -->
                <div class="status-display">
                    <div class="status-item">
                        <label>Satellites:</label>
                        <span id="satelliteCount" class="sat-count">0</span>
                    </div>
                    <div class="status-item">
                        <label>GPS-ESKF Distance:</label>
                        <span id="distanceDiff">0.0m</span>
                    </div>
                </div>

                <button onclick="hideRealtimeControls()">Close</button>
            </div>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        let map;
        let layers = {
            eskf: null,
            gps: null,
            rail: null,
            initialization: null,
            gps_recovery: null
        };
        let layerVisibility = {
            eskf: true,
            gps: true,
            rail: true,
            initialization: true,
            gps_recovery: true
        };

        // Initialize map
        window.onload = function() {
            map = L.map('map').setView([37.5665, 126.9780], 11);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap'
            }).addTo(map);
        };

        function toggleLayer(layerType) {
            layerVisibility[layerType] = !layerVisibility[layerType];
            const legendItem = document.querySelector(`[data-layer="${layerType}"]`);

            if (layerVisibility[layerType]) {
                if (layers[layerType]) map.addLayer(layers[layerType]);
                legendItem.classList.remove('disabled');
            } else {
                if (layers[layerType]) map.removeLayer(layers[layerType]);
                legendItem.classList.add('disabled');
            }
        }

        async function runTest(type, direction = null) {
            let btnId = 'run' + (type === 'python' ? 'Python' : 'C');
            if (type === 'c' && direction) {
                btnId = 'runC' + (direction === 'up' ? 'Up' : 'Down');
            }
            const btn = document.getElementById(btnId);
            const status = document.getElementById('status');
            const stats = document.getElementById('stats');

            // Disable buttons and update status
            document.querySelectorAll('button').forEach(b => b.disabled = true);
            let directionText = direction ? ` (${direction === 'up' ? '상행' : '하행'})` : '';
            status.className = 'running';
            status.innerHTML = '[RUNNING] Running ' + type.toUpperCase() + ' version' + directionText + '...';

            try {
                const requestData = {};
                if (type === 'c' && direction) {
                    requestData.direction = direction;
                }

                const response = await fetch('/run_' + type, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(requestData)
                });
                const data = await response.json();

                if (data.success) {
                    status.className = '';
                    status.innerHTML = '[SUCCESS] ' + data.message;

                    // Show stats
                    stats.style.display = 'grid';
                    document.getElementById('gpsCount').textContent = data.gps_count || 0;
                    document.getElementById('imuCount').textContent = data.imu_count || 0;
                    document.getElementById('railCount').textContent = data.rail_count || 0;
                    document.getElementById('processTime').textContent = (data.process_time || 0).toFixed(2) + 's';

                    // Draw paths if available
                    if (data.paths) {
                        drawMultiplePaths(data.paths, type);
                    } else if (data.path) {
                        drawPath(data.path, type);  // 호환성
                    }
                } else {
                    throw new Error(data.error);
                }
            } catch (error) {
                status.className = 'error';
                status.innerHTML = '[ERROR] Error: ' + error.message;
            } finally {
                document.querySelectorAll('button').forEach(b => b.disabled = false);
            }
        }

        function drawMultiplePaths(pathsData, type) {
            // Clear previous layers
            clearAllLayers();

            const colors = {
                eskf: '#2196F3',
                gps_raw: '#f44336',
                rail: '#4CAF50',
                initialization: '#E91E63',
                gps_recovery: '#9C27B0'
            };

            const legend = document.getElementById('legend');

            // Draw ESKF path
            if (pathsData.eskf && pathsData.eskf.length > 0) {
                layers.eskf = L.polyline(pathsData.eskf, {
                    color: colors.eskf,
                    weight: 3,
                    opacity: 0.8
                });
                if (layerVisibility.eskf) layers.eskf.addTo(map);
            }

            // Draw GPS raw path with coordinate labels
            if (pathsData.gps_raw && pathsData.gps_raw.length > 0) {
                // Create polyline for GPS path
                layers.gps = L.polyline(pathsData.gps_raw, {
                    color: colors.gps_raw,
                    weight: 2,
                    opacity: 0.7,
                    dashArray: '5, 5'
                });

                // Add individual GPS markers with coordinates
                const gpsMarkers = [];
                pathsData.gps_raw.forEach((point, index) => {
                    if (index % 5 === 0) { // Show every 5th point to avoid clutter
                        const marker = L.circleMarker(point, {
                            color: colors.gps_raw,
                            fillColor: colors.gps_raw,
                            fillOpacity: 0.8,
                            radius: 4,
                            weight: 2
                        }).bindTooltip(`GPS ${index + 1}<br>Lat: ${point[0].toFixed(6)}<br>Lon: ${point[1].toFixed(6)}`, {
                            permanent: false,
                            direction: 'top',
                            className: 'coordinate-tooltip'
                        });
                        gpsMarkers.push(marker);
                    }
                });

                // Group GPS elements
                layers.gps = L.layerGroup([layers.gps, ...gpsMarkers]);
                if (layerVisibility.gps) layers.gps.addTo(map);
            }

            // Draw Railway path
            if (pathsData.rail && pathsData.rail.length > 0) {
                layers.rail = L.polyline(pathsData.rail, {
                    color: colors.rail,
                    weight: 4,
                    opacity: 0.6
                });
                if (layerVisibility.rail) layers.rail.addTo(map);
            }

            // Draw Route-projected path

            // Draw Initialization Points (all of them)
            if (pathsData.initialization && pathsData.initialization.length > 0) {
                const initMarkers = [];

                pathsData.initialization.forEach((initPoint, index) => {
                    const marker = L.circleMarker(initPoint, {
                        color: colors.initialization,
                        fillColor: colors.initialization,
                        fillOpacity: 0.8,
                        radius: 8,
                        weight: 2
                    }).bindTooltip(`Init Point ${index + 1}<br>Lat: ${initPoint[0].toFixed(6)}<br>Lon: ${initPoint[1].toFixed(6)}`, {
                        permanent: false,
                        direction: 'top',
                        className: 'coordinate-tooltip'
                    }).bindPopup(`ESKF ${index === 0 ? 'Initialization' : 'Re-initialization'} Point ${index + 1}<br>Coordinates: ${initPoint[0].toFixed(6)}, ${initPoint[1].toFixed(6)}`);

                    initMarkers.push(marker);
                });

                // Create a layer group for all initialization markers
                layers.initialization = L.layerGroup(initMarkers);

                if (layerVisibility.initialization) layers.initialization.addTo(map);
            }

            // Draw GPS Recovery Points (tunnel exits)
            if (pathsData.gps_recovery && pathsData.gps_recovery.length > 0) {
                const recoveryMarkers = [];

                pathsData.gps_recovery.forEach((recoveryPoint, index) => {
                    const marker = L.circleMarker(recoveryPoint, {
                        color: colors.gps_recovery,
                        fillColor: colors.gps_recovery,
                        fillOpacity: 0.8,
                        radius: 8,
                        weight: 2
                    }).bindTooltip(`GPS Recovery ${index + 1}<br>Lat: ${recoveryPoint[0].toFixed(6)}<br>Lon: ${recoveryPoint[1].toFixed(6)}`, {
                        permanent: false,
                        direction: 'top',
                        className: 'coordinate-tooltip'
                    }).bindPopup(`GPS Recovery Point ${index + 1}<br>Coordinates: ${recoveryPoint[0].toFixed(6)}, ${recoveryPoint[1].toFixed(6)}<br><small>GPS Signal Restored</small>`);

                    recoveryMarkers.push(marker);
                });

                // Create a layer group for all GPS recovery markers
                layers.gps_recovery = L.layerGroup(recoveryMarkers);

                if (layerVisibility.gps_recovery) layers.gps_recovery.addTo(map);
            }

            // Show legend if we have paths
            if (Object.keys(pathsData).length > 0) {
                legend.style.display = 'block';
            }

            // Fit map to bounds using layer group (handle layerGroup objects properly)
            const group = L.featureGroup();
            Object.values(layers).forEach(layer => {
                if (layer) {
                    // If it's a layerGroup, add its individual layers
                    if (layer.getLayers && typeof layer.getLayers === 'function') {
                        layer.getLayers().forEach(sublayer => {
                            group.addLayer(sublayer);
                        });
                    } else {
                        // It's a regular layer (polyline, etc.)
                        group.addLayer(layer);
                    }
                }
            });
            if (group.getLayers().length > 0) {
                map.fitBounds(group.getBounds(), {padding: [50, 50]});
            }
        }

        function drawPath(pathData, type) {
            // Legacy support - convert to new format
            const pathsData = { eskf: pathData };
            drawMultiplePaths(pathsData, type);
        }

        function clearAllLayers() {
            Object.keys(layers).forEach(key => {
                if (layers[key]) {
                    map.removeLayer(layers[key]);
                    layers[key] = null;
                }
            });
        }

        // Real-time Debug Variables
        let realtimeSession = null;
        let isPlaying = false;
        let playbackSpeed = 1;
        let currentFrame = 0;
        let totalFrames = 0;
        let playbackTimer = null;
        let realtimeMarkers = [];  // Store all realtime markers
        let realtimeLines = [];    // Store path lines

        function startRealtimeDebug() {
            document.getElementById('status').innerHTML = 'Real-time Debug mode activated!';
            document.getElementById('status').className = '';

            // Show realtime controls
            document.getElementById('realtimeControls').style.display = 'block';

            // Initialize realtime session (use default 'up' direction for realtime)
            fetch('/start_realtime', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ direction: 'up' })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    totalFrames = data.total_frames;
                    currentFrame = 0;
                    updateTimeDisplay();
                    document.getElementById('status').innerHTML = `Real-time session ready: ${totalFrames} frames`;
                    console.log('Real-time session initialized:', data);
                } else {
                    document.getElementById('status').innerHTML = 'Error: ' + data.error;
                    console.error('Failed to initialize:', data.error);
                }
            })
            .catch(error => {
                document.getElementById('status').innerHTML = 'Connection error';
                console.error('Network error:', error);
            });
        }

        function hideRealtimeControls() {
            document.getElementById('realtimeControls').style.display = 'none';
            stopPlayback();
            clearRealtimeData();
        }

        function togglePlayback() {
            if (isPlaying) {
                pausePlayback();
            } else {
                startPlayback();
            }
        }

        function startPlayback() {
            if (totalFrames === 0) {
                console.log('No session available for playback');
                return;
            }

            isPlaying = true;
            document.getElementById('playBtn').disabled = true;
            document.getElementById('pauseBtn').disabled = false;

            // Start first frame immediately
            processNextFrame();

            console.log('Playback started at ' + playbackSpeed + 'x speed');
        }

        function pausePlayback() {
            isPlaying = false;
            document.getElementById('playBtn').disabled = false;
            document.getElementById('pauseBtn').disabled = true;

            if (playbackTimer) {
                clearTimeout(playbackTimer);
                playbackTimer = null;
            }

            console.log('Playback paused');
        }

        function stopPlayback() {
            isPlaying = false;
            currentFrame = 0;
            document.getElementById('playBtn').disabled = false;
            document.getElementById('pauseBtn').disabled = true;

            if (playbackTimer) {
                clearTimeout(playbackTimer);
                playbackTimer = null;
            }

            updateTimeDisplay();
        }

        function resetPlayback() {
            stopPlayback();

            // Clear realtime markers and lines
            clearRealtimeData();

            // Reset session on server
            fetch('/realtime_reset', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    currentFrame = 0;
                    totalFrames = 0;
                    updateTimeDisplay();
                    document.getElementById('status').innerHTML = 'Session reset - ready for new playback';
                    console.log('Playback reset successfully');
                } else {
                    console.error('Reset failed:', data.error);
                }
            })
            .catch(error => {
                console.error('Reset error:', error);
            });
        }

        function clearRealtimeData() {
            // Remove all realtime markers
            realtimeMarkers.forEach(marker => {
                map.removeLayer(marker);
            });
            realtimeMarkers = [];

            // Remove all realtime lines
            realtimeLines.forEach(line => {
                map.removeLayer(line);
            });
            realtimeLines = [];
        }

        function processNextFrame() {
            if (currentFrame >= totalFrames) {
                pausePlayback();
                document.getElementById('status').innerHTML = 'Playback completed';
                return;
            }

            fetch('/realtime_step', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    currentFrame = data.current_frame;
                    updateTimeDisplay();

                    // Add GPS and ESKF points to map
                    const gpsPoint = data.result.gps;
                    const eskfPoint = data.result.eskf;

                    // Create markers for current frame
                    const gpsMarker = L.circleMarker(gpsPoint, {
                        color: '#FF0000',
                        fillColor: '#FF0000',
                        fillOpacity: 0.8,
                        radius: 5,
                        weight: 2
                    }).bindTooltip(`GPS Frame ${data.result.frame_id}: ${gpsPoint[0].toFixed(6)}, ${gpsPoint[1].toFixed(6)}`);

                    const eskfMarker = L.circleMarker(eskfPoint, {
                        color: '#0066CC',
                        fillColor: '#0066CC',
                        fillOpacity: 0.8,
                        radius: 5,
                        weight: 2
                    }).bindTooltip(`ESKF Frame ${data.result.frame_id}: ${eskfPoint[0].toFixed(6)}, ${eskfPoint[1].toFixed(6)}`);

                    // Add to map and store
                    gpsMarker.addTo(map);
                    eskfMarker.addTo(map);
                    realtimeMarkers.push(gpsMarker, eskfMarker);

                    // Draw path lines if we have previous points
                    if (realtimeMarkers.length >= 4) { // At least 2 GPS and 2 ESKF markers
                        const prevGpsPoint = realtimeMarkers[realtimeMarkers.length - 4].getLatLng();
                        const prevEskfPoint = realtimeMarkers[realtimeMarkers.length - 3].getLatLng();

                        // GPS path line
                        const gpsLine = L.polyline([prevGpsPoint, gpsPoint], {
                            color: '#FF0000',
                            weight: 2,
                            opacity: 0.7
                        }).addTo(map);

                        // ESKF path line
                        const eskfLine = L.polyline([prevEskfPoint, eskfPoint], {
                            color: '#0066CC',
                            weight: 2,
                            opacity: 0.7
                        }).addTo(map);

                        realtimeLines.push(gpsLine, eskfLine);
                    }

                    // Update status display
                    updateRealtimeStatus(data.result.satellites, data.result.distance);

                    // Auto-pan map to follow latest points (every 5 frames for smoother tracking)
                    if (data.result.frame_id % 5 === 0) {
                        const bounds = L.latLngBounds([gpsPoint, eskfPoint]);
                        map.fitBounds(bounds, {padding: [50, 50], maxZoom: 16});
                    }

                    // Check if session completed
                    if (data.completed) {
                        pausePlayback();
                        document.getElementById('status').innerHTML = 'Playback completed - ' + currentFrame + ' frames processed';
                        return;
                    }

                    // Schedule next frame with consistent interval
                    if (isPlaying) {
                        scheduleNextFrame();
                    }

                } else {
                    console.error('Frame processing failed:', data.error);
                    pausePlayback();
                }
            })
            .catch(error => {
                console.error('Frame processing error:', error);
                pausePlayback();
            });
        }

        function scheduleNextFrame() {
            if (!isPlaying) return;

            // Calculate consistent frame interval based on playback speed
            const baseInterval = 150; // Base 150ms between frames (faster for more frames)
            const delay = Math.max(30, baseInterval / playbackSpeed); // Minimum 30ms

            // Schedule next frame
            playbackTimer = setTimeout(() => {
                if (isPlaying) {
                    processNextFrame();
                }
            }, delay);
        }

        function changeSpeed() {
            playbackSpeed = parseInt(document.getElementById('speedSelect').value);
            console.log('Speed changed to:', playbackSpeed + 'x');

            // Speed change is automatically applied in scheduleNextFrame function
            // No need to restart playback
        }

        function jumpToTime() {
            const slider = document.getElementById('timeSlider');
            currentFrame = Math.floor((slider.value / 100) * totalFrames);
            updateTimeDisplay();
            console.log('Jumped to frame:', currentFrame);
            // TODO: Update map to specific frame
        }

        function updateTimeDisplay() {
            const current = Math.floor(currentFrame / 10); // Assuming 10 frames per second
            const total = Math.floor(totalFrames / 10);

            const currentStr = formatTime(current);
            const totalStr = formatTime(total);

            document.getElementById('currentTime').textContent = currentStr;
            document.getElementById('totalTime').textContent = totalStr;

            if (totalFrames > 0) {
                document.getElementById('timeSlider').value = (currentFrame / totalFrames) * 100;
            }
        }

        function formatTime(seconds) {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = seconds % 60;
            return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }

        function updateRealtimeStatus(satellites, distance) {
            const satElement = document.getElementById('satelliteCount');
            satElement.textContent = satellites;
            satElement.className = satellites < 8 ? 'sat-count sat-low' : 'sat-count sat-high';

            document.getElementById('distanceDiff').textContent = distance.toFixed(1) + 'm';
        }


        function clearStatus() {
            document.getElementById('status').innerHTML = 'Ready...';
            document.getElementById('status').className = '';
            document.getElementById('stats').style.display = 'none';
            document.getElementById('legend').style.display = 'none';
            clearAllLayers();
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/run_python', methods=['POST'])
def run_python():
    """Run Python version of ESKF"""
    try:
        import time
        start_time = time.time()

        # Run Python script
        result = subprocess.run(
            ['python', 'python_version/map2.py'],
            capture_output=True,
            text=True,
            timeout=60
        )

        process_time = time.time() - start_time

        # Parse output to get counts
        output_lines = result.stdout.split('\n')
        gps_count = 0
        imu_count = 0

        for line in output_lines:
            if 'GPS updates:' in line:
                gps_count = int(line.split(':')[1].strip())
            elif 'IMU updates:' in line:
                imu_count = int(line.split(':')[1].strip())

        # Read output path if created
        path = []
        if os.path.exists('eskf_rail_matched.html'):
            # Extract path data from HTML if needed
            pass

        return jsonify({
            'success': True,
            'message': f'Python processing complete! {gps_count} GPS, {imu_count} IMU updates',
            'gps_count': gps_count,
            'imu_count': imu_count,
            'rail_count': 0,
            'process_time': process_time,
            'path': path
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/run_c', methods=['POST'])
def run_c():
    """Run C version using Python test script"""
    try:
        import time
        start_time = time.time()

        # Get direction from request
        direction = 'up'  # default
        if request.is_json:
            data = request.get_json()
            direction = data.get('direction', 'up')

        # Run the Python test that calls C library with direction parameter
        result = subprocess.run(
            ['python', 'test_c_python.py', '--direction', direction],
            capture_output=True,
            text=True,
            timeout=60
        )

        process_time = time.time() - start_time

        # Parse output
        output_lines = result.stdout.split('\n')
        gps_count = 0
        imu_count = 0
        rail_count = 0

        for line in output_lines:
            if 'GPS updates:' in line:
                gps_count = int(line.split(':')[1].strip())
            elif 'IMU updates:' in line:
                imu_count = int(line.split(':')[1].strip())
            elif 'Loaded' in line and 'railway nodes' in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part.isdigit():
                        rail_count = int(part)
                        break

        # Read output CSV for multiple paths
        paths = {}
        if os.path.exists('eskf_c_output.csv'):
            df = pd.read_csv('eskf_c_output.csv')

            # ESKF Path (기본)
            if 'eskf_lat' in df.columns and 'eskf_lon' in df.columns:
                paths['eskf'] = [[row['eskf_lat'], row['eskf_lon']] for _, row in df.iterrows()
                                if row['eskf_lat'] != 0 and row['eskf_lon'] != 0]

            # GPS Raw Path
            if 'gps_raw_lat' in df.columns and 'gps_raw_lon' in df.columns:
                paths['gps_raw'] = [[row['gps_raw_lat'], row['gps_raw_lon']] for _, row in df.iterrows()
                                  if row['gps_raw_lat'] != 0 and row['gps_raw_lon'] != 0]

            # Initialization Points (all of them)
            if 'is_initialization' in df.columns:
                init_rows = df[df['is_initialization'] == 1]
                if len(init_rows) > 0:
                    paths['initialization'] = [[row['eskf_lat'], row['eskf_lon']] for _, row in init_rows.iterrows()]

            # GPS Recovery Points (tunnel exits)
            if 'is_gps_recovery' in df.columns:
                recovery_rows = df[df['is_gps_recovery'] == 1]
                if len(recovery_rows) > 0:
                    paths['gps_recovery'] = [[row['eskf_lat'], row['eskf_lon']] for _, row in recovery_rows.iterrows()]

        # Railway Path - direction에 따라 읽기
        rail_nodes = []
        railway_file = f'data/railway_nodes_{direction}.csv'
        if not os.path.exists(railway_file):
            railway_file = 'data/railway_nodes.csv'  # fallback

        if os.path.exists(railway_file):
            try:
                rail_df = pd.read_csv(railway_file)
                if 'lat' in rail_df.columns and 'lng' in rail_df.columns:
                    rail_nodes = [[row['lat'], row['lng']] for _, row in rail_df.iterrows()]
                    paths['rail'] = rail_nodes
                elif 'lat' in rail_df.columns and 'lon' in rail_df.columns:
                    rail_nodes = [[row['lat'], row['lon']] for _, row in rail_df.iterrows()]
                    paths['rail'] = rail_nodes
                print(f"Loaded railway visualization from {railway_file}")
            except Exception as e:
                print(f"Warning: Could not load railway data: {e}")


        # 호환성을 위한 기본 path (ESKF)
        path = paths.get('eskf', [])

        return jsonify({
            'success': True,
            'message': f'C processing complete! {gps_count} GPS, {imu_count} IMU updates',
            'gps_count': gps_count,
            'imu_count': imu_count,
            'rail_count': rail_count,
            'process_time': process_time,
            'path': path,  # 호환성을 위한 기본 경로
            'paths': paths  # 다중 경로 데이터
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/start_realtime', methods=['POST'])
def start_realtime():
    """Initialize real-time debug session"""
    global realtime_session

    try:
        # Get direction from request
        direction = 'up'  # default
        if request.is_json:
            data = request.get_json()
            direction = data.get('direction', 'up')

        # Reset session
        realtime_session = {
            'active': True,
            'current_frame': 0,
            'total_frames': 0,
            'data_frames': [],
            'results': [],
            'start_time': pd.Timestamp.now(),
            'direction': direction
        }

        # Run C version first to get processed data with direction
        result = subprocess.run(
            ['python', 'test_c_python.py', '--direction', direction],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            return jsonify({'success': False, 'error': 'C version failed to run'})

        # Read C version output
        if not os.path.exists('eskf_c_output.csv'):
            return jsonify({'success': False, 'error': 'C output file not found'})

        # Load C ESKF results
        c_df = pd.read_csv('eskf_c_output.csv')

        # Load original data.csv to get satellites information
        original_df = pd.read_csv('data/data.csv')
        original_df['timestamp'] = pd.to_datetime(original_df['timestamp']).astype(np.int64) / 1e9

        # Use all frames from C output for complete timeline
        for i, idx in enumerate(range(len(c_df))):
            frame_data = c_df.iloc[idx]

            # Find matching timestamp in original data for satellites info
            satellites = 0
            if i < len(original_df):
                satellites = int(original_df.iloc[i].get('satellites', 0))

            realtime_session['data_frames'].append({
                'frame_id': i,
                'timestamp': float(frame_data['timestamp']),
                'gps_lat': float(frame_data['gps_raw_lat']),
                'gps_lng': float(frame_data['gps_raw_lon']),
                'eskf_lat': float(frame_data['eskf_lat']),
                'eskf_lng': float(frame_data['eskf_lon']),
                'satellites': satellites,
                'route_projection': bool(satellites < 4)  # Low satellites = route projection active
            })

        realtime_session['total_frames'] = len(realtime_session['data_frames'])

        return jsonify({
            'success': True,
            'total_frames': realtime_session['total_frames'],
            'message': f'Real-time session initialized with {realtime_session["total_frames"]} frames'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/realtime_step', methods=['POST'])
def realtime_step():
    """Process next frame in real-time session"""
    global realtime_session

    try:
        if not realtime_session['active']:
            return jsonify({'success': False, 'error': 'No active session'})

        if realtime_session['current_frame'] >= realtime_session['total_frames']:
            return jsonify({'success': False, 'error': 'Session completed'})

        # Get current frame data
        current_data = realtime_session['data_frames'][realtime_session['current_frame']]

        # Use actual C ESKF processed data
        eskf_lat = current_data['eskf_lat']
        eskf_lng = current_data['eskf_lng']

        # Calculate distance difference
        import math
        lat_diff = (eskf_lat - current_data['gps_lat']) * 111000
        lng_diff = (eskf_lng - current_data['gps_lng']) * 111000
        distance = math.sqrt(lat_diff**2 + lng_diff**2)

        # Store result
        result = {
            'frame_id': realtime_session['current_frame'],
            'timestamp': float(current_data['timestamp']),
            'gps': [float(current_data['gps_lat']), float(current_data['gps_lng'])],
            'eskf': [float(eskf_lat), float(eskf_lng)],
            'satellites': int(current_data['satellites']),
            'route_projection': bool(current_data['route_projection']),
            'distance': float(distance)
        }

        realtime_session['results'].append(result)
        realtime_session['current_frame'] += 1

        return jsonify({
            'success': True,
            'result': result,
            'current_frame': realtime_session['current_frame'],
            'total_frames': realtime_session['total_frames'],
            'completed': realtime_session['current_frame'] >= realtime_session['total_frames']
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/realtime_status', methods=['GET'])
def realtime_status():
    """Get current real-time session status"""
    global realtime_session

    return jsonify({
        'active': realtime_session['active'],
        'current_frame': realtime_session['current_frame'],
        'total_frames': realtime_session['total_frames'],
        'progress': realtime_session['current_frame'] / max(realtime_session['total_frames'], 1) * 100
    })

@app.route('/realtime_reset', methods=['POST'])
def realtime_reset():
    """Reset real-time session"""
    global realtime_session

    realtime_session = {
        'active': False,
        'current_frame': 0,
        'total_frames': 0,
        'data_frames': [],
        'results': [],
        'start_time': None
    }

    return jsonify({'success': True, 'message': 'Session reset'})

if __name__ == '__main__':
    print("\n" + "="*60)
    print("ESKF Test Server (Simple Version)")
    print("="*60)
    print("\nOpen browser: http://localhost:5000")
    print("\nFeatures:")
    print("   - Run Python version")
    print("   - Run C version")
    print("   - Multi-path visualization")
    print("   - Interactive legend")
    print("\nCtrl+C to stop")
    print("="*60 + "\n")

    app.run(debug=True, port=5000)