from flask import Flask, render_template_string, jsonify, request
import subprocess
import os
import json
import pandas as pd
import numpy as np
import math

def safe_float(value, default=0.0):
    """Convert value to float, handling NaN values"""
    try:
        result = float(value)
        return default if math.isnan(result) else result
    except (ValueError, TypeError):
        return default

def safe_int(value, default=0):
    """Convert value to int, handling NaN values"""
    try:
        if pd.isna(value):
            return default
        return int(value)
    except (ValueError, TypeError):
        return default

def clean_path_data(path_list):
    """Clean path data by removing NaN values"""
    if not isinstance(path_list, list):
        return []

    cleaned_path = []
    for point in path_list:
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            lat = safe_float(point[0])
            lng = safe_float(point[1])
            # Only add valid coordinates (non-zero)
            if lat != 0.0 or lng != 0.0:
                cleaned_path.append([lat, lng])
        elif isinstance(point, dict):
            lat = safe_float(point.get('lat', 0))
            lng = safe_float(point.get('lng', 0))
            if lat != 0.0 or lng != 0.0:
                cleaned_path.append([lat, lng])

    return cleaned_path

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
        /* Removed satellite count styles */

        /* ===== DistanceMeasurer Phase 1: CSS 스타일 ===== */
        .distance-measurer-selected {
            animation: pulse-gold 1.5s infinite;
            box-shadow: 0 0 15px rgba(255, 215, 0, 0.8) !important;
            z-index: 1000 !important;
        }

        @keyframes pulse-gold {
            0% {
                box-shadow: 0 0 15px rgba(255, 215, 0, 0.8);
                transform: scale(1);
            }
            50% {
                box-shadow: 0 0 25px rgba(255, 215, 0, 1);
                transform: scale(1.1);
            }
            100% {
                box-shadow: 0 0 15px rgba(255, 215, 0, 0.8);
                transform: scale(1);
            }
        }

        .distance-measurer-hover {
            cursor: crosshair !important;
            transition: all 0.2s ease;
        }

        .distance-measurer-hover:hover {
            transform: scale(1.15);
            box-shadow: 0 0 10px rgba(255, 215, 0, 0.6);
        }

        /* ===== DistanceMeasurer Phase 4: 우하단 거리 박스 ===== */
        #distanceInfoBox {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 1001;
            background: rgba(255, 255, 255, 0.95);
            border: 2px solid #FF6B35;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
            padding: 15px;
            min-width: 200px;
            max-width: 280px;
            font-family: Arial, sans-serif;
            display: none;
            transition: all 0.3s ease;
        }

        #distanceInfoBox.show {
            display: block;
            animation: slideInUp 0.3s ease;
        }

        @keyframes slideInUp {
            from {
                transform: translateY(20px);
                opacity: 0;
            }
            to {
                transform: translateY(0);
                opacity: 1;
            }
        }

        .distance-box-title {
            font-size: 14px;
            font-weight: bold;
            color: #FF6B35;
            margin-bottom: 10px;
            text-align: center;
            border-bottom: 1px solid #FF6B35;
            padding-bottom: 5px;
        }

        .distance-box-content {
            display: grid;
            gap: 8px;
        }

        .distance-box-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 4px 0;
        }

        .distance-box-label {
            font-size: 12px;
            color: #666;
            font-weight: normal;
        }

        .distance-box-value {
            font-size: 14px;
            font-weight: bold;
            color: #333;
        }

        .distance-box-primary {
            font-size: 16px;
            color: #FF6B35;
        }

        /* 반응형 디자인 */
        @media (max-width: 768px) {
            #distanceInfoBox {
                bottom: 10px;
                right: 10px;
                min-width: 160px;
                max-width: 200px;
                padding: 12px;
            }

            .distance-box-title {
                font-size: 13px;
            }

            .distance-box-value {
                font-size: 12px;
            }

            .distance-box-primary {
                font-size: 14px;
            }
        }
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
                <div class="legend-item" data-layer="gps_loss" onclick="toggleLayer('gps_loss')">
                    <div class="legend-color" style="background: #9C27B0; border-radius: 50%;"></div>
                    <span>IMU Recovery</span>
                </div>
            </div>
        </div>

        <!-- ===== Phase 4: 우하단 거리 정보 박스 ===== -->
        <div id="distanceInfoBox">
            <div class="distance-box-title">📏 Distance Measurement</div>
            <div class="distance-box-content">
                <div class="distance-box-row">
                    <span class="distance-box-label">Distance:</span>
                    <span class="distance-box-value distance-box-primary" id="distanceValue">0 m</span>
                </div>
                <div class="distance-box-row">
                    <span class="distance-box-label">In Kilometers:</span>
                    <span class="distance-box-value" id="distanceKm">0.000 km</span>
                </div>
                <div class="distance-box-row">
                    <span class="distance-box-label">Point 1:</span>
                    <span class="distance-box-value" id="point1Coords">-</span>
                </div>
                <div class="distance-box-row">
                    <span class="distance-box-label">Point 2:</span>
                    <span class="distance-box-value" id="point2Coords">-</span>
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
                    <!-- Removed satellite count display -->
                    <!-- <div class="status-item">
                        <label>GPS-ESKF Distance:</label>
                        <span id="distanceDiff">0.0m</span>
                    </div> -->
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
            gps_loss: null
        };
        let layerVisibility = {
            eskf: true,
            gps: true,
            rail: true,
            initialization: true,
            gps_loss: true
        };

        // Initialize map
        window.onload = function() {
            map = L.map('map').setView([37.5665, 126.9780], 11);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap'
            }).addTo(map);

            // ===== Phase 6: DistanceMeasurer 통합 초기화 =====
            distanceMeasurer = new DistanceMeasurer(map);
            distanceMeasurer.init();

            // Phase 2의 외부 지도 클릭 리스너는 Phase 6에서 init() 메서드로 통합됨

            console.log('[DistanceMeasurer] 지도 로드 완료 후 초기화됨 (Phase 1+2)');
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
                gps_loss: '#9C27B0'
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

            // Draw GPS Loss Points (tunnel entrances)
            if (pathsData.gps_loss && pathsData.gps_loss.length > 0) {
                const lossMarkers = [];

                pathsData.gps_loss.forEach((lossPoint, index) => {
                    const marker = L.circleMarker(lossPoint, {
                        color: colors.gps_loss,
                        fillColor: colors.gps_loss,
                        fillOpacity: 0.8,
                        radius: 8,
                        weight: 2
                    }).bindTooltip(`GPS Loss ${index + 1}<br>Lat: ${lossPoint[0].toFixed(6)}<br>Lon: ${lossPoint[1].toFixed(6)}`, {
                        permanent: false,
                        direction: 'top',
                        className: 'coordinate-tooltip'
                    }).bindPopup(`GPS Loss Point ${index + 1}<br>Coordinates: ${lossPoint[0].toFixed(6)}, ${lossPoint[1].toFixed(6)}<br><small>GPS Signal Lost</small>`);

                    lossMarkers.push(marker);
                });

                // Create a layer group for all GPS loss markers
                layers.gps_loss = L.layerGroup(lossMarkers);

                if (layerVisibility.gps_loss) layers.gps_loss.addTo(map);
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

                    // ===== DistanceMeasurer Phase 1: 마커 클릭 이벤트 추가 =====
                    // GPS 마커에 원본 스타일 저장 및 클릭 이벤트 추가
                    gpsMarker._originalColor = '#FF0000';
                    gpsMarker._originalFillColor = '#FF0000';
                    gpsMarker._originalFillOpacity = 0.8;
                    gpsMarker._originalRadius = 5;
                    gpsMarker._originalWeight = 2;
                    gpsMarker._markerType = 'GPS';
                    gpsMarker._frameId = data.result.frame_id;

                    gpsMarker.on('click', function(e) {
                        L.DomEvent.stopPropagation(e); // 지도 클릭 이벤트 방지
                        if (distanceMeasurer && distanceMeasurer.isEnabled) {
                            distanceMeasurer.selectPinForMeasurement(this);
                        }
                    });

                    // ESKF 마커에 원본 스타일 저장 및 클릭 이벤트 추가
                    eskfMarker._originalColor = '#0066CC';
                    eskfMarker._originalFillColor = '#0066CC';
                    eskfMarker._originalFillOpacity = 0.8;
                    eskfMarker._originalRadius = 5;
                    eskfMarker._originalWeight = 2;
                    eskfMarker._markerType = 'ESKF';
                    eskfMarker._frameId = data.result.frame_id;

                    eskfMarker.on('click', function(e) {
                        L.DomEvent.stopPropagation(e); // 지도 클릭 이벤트 방지
                        if (distanceMeasurer && distanceMeasurer.isEnabled) {
                            distanceMeasurer.selectPinForMeasurement(this);
                        }
                    });

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
                    updateRealtimeStatus(data.result.distance);

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

        function updateRealtimeStatus(distance) {
            // Removed satellite count display
            // document.getElementById('distanceDiff').textContent = distance.toFixed(1) + 'm';
        }


        function clearStatus() {
            document.getElementById('status').innerHTML = 'Ready...';
            document.getElementById('status').className = '';
            document.getElementById('stats').style.display = 'none';
            document.getElementById('legend').style.display = 'none';
            clearAllLayers();
        }

        // ===== DistanceMeasurer Phase 1: 핀 선택 + 하이라이트 =====
        // ===== Phase 6: DistanceMeasurer 클래스 - 완전 통합 버전 =====
        /**
         * DistanceMeasurer - 지도상 거리 측정 기능 제공
         *
         * 주요 기능:
         * - Phase 1: 핀 선택 + 하이라이트
         * - Phase 2: 거리 계산 + 선 그리기
         * - Phase 3: 중간점 텍스트 표시
         * - Phase 4: 우하단 고정 정보 박스
         * - Phase 5: 측정 삭제 + 리셋
         * - Phase 6: 통합 최적화 + 에러 핸들링
         *
         * 워크플로우:
         * 1. 첫 번째 마커 클릭 → 하이라이트
         * 2. 두 번째 점 클릭 → 거리 측정 완료 (선, 텍스트, 박스 표시)
         * 3. 지도 빈 공간 클릭 → 모든 측정 요소 삭제
         */
        class DistanceMeasurer {
            constructor(map) {
                this.map = map;
                this.selectedMarker = null;
                this.isEnabled = true;

                // 거리 측정 상태 변수
                this.firstPoint = null;
                this.secondPoint = null;
                this.waitingForSecondPoint = false;
                this.measurementLine = null;
                this.currentDistance = 0;
                this.measurementTextMarker = null;

                console.log('[DistanceMeasurer] Phase 6 완전 통합 버전 초기화 완료');
            }

            // 초기화 - 이벤트 리스너 부착
            init() {
                console.log('[DistanceMeasurer] init() 호출됨');

                // ===== Phase 6: 통합 지도 클릭 이벤트 리스너 (Phase 2 + Phase 5) =====
                this.map.on('click', (e) => {
                    // Phase 2: 두 번째 점 선택 대기 중인 경우
                    if (this.isEnabled && this.waitingForSecondPoint) {
                        this.secondPoint = e.latlng;
                        this.performDistanceMeasurement();
                        console.log('[DistanceMeasurer] 지도 클릭으로 두 번째 점 선택됨:', {
                            lat: e.latlng.lat,
                            lng: e.latlng.lng
                        });
                    }
                    // Phase 5: 측정 결과가 있을 때 삭제 처리
                    else if (this.hasMeasurement()) {
                        console.log('[DistanceMeasurer] 지도 클릭으로 측정 결과 삭제');
                        this.clearMeasurement();
                    }
                });

                console.log('[DistanceMeasurer] Phase 6 통합 지도 클릭 이벤트 리스너 등록 완료');
                return this;
            }

            // 핀 선택 처리
            selectPin(marker) {
                console.log('[DistanceMeasurer] selectPin() 호출됨', marker);

                // 이전 선택 해제
                if (this.selectedMarker) {
                    this.clearSelection();
                }

                // 새로운 핀 선택
                this.selectedMarker = marker;
                this.highlightPin(marker);

                console.log('[DistanceMeasurer] 마커 선택됨:', {
                    lat: marker.getLatLng().lat,
                    lng: marker.getLatLng().lng
                });
            }

            // 핀 하이라이트
            highlightPin(marker) {
                if (!marker) return;

                // 하이라이트 스타일 적용
                marker.setStyle({
                    color: '#FFD700',        // 골드 색상
                    fillColor: '#FFD700',
                    weight: 4,
                    radius: 12,
                    fillOpacity: 1
                });

                console.log('[DistanceMeasurer] 마커 하이라이트 적용됨');
            }

            // 선택 해제
            clearSelection() {
                if (this.selectedMarker) {
                    // 원래 스타일로 복원 (실시간 마커 기본 스타일)
                    this.selectedMarker.setStyle({
                        color: this.selectedMarker._originalColor || '#0066CC',
                        fillColor: this.selectedMarker._originalFillColor || '#0066CC',
                        weight: this.selectedMarker._originalWeight || 2,
                        radius: this.selectedMarker._originalRadius || 5,
                        fillOpacity: this.selectedMarker._originalFillOpacity || 0.8
                    });

                    console.log('[DistanceMeasurer] 마커 선택 해제됨');
                    this.selectedMarker = null;
                }
            }

            // 활성화/비활성화
            setEnabled(enabled) {
                this.isEnabled = enabled;
                console.log('[DistanceMeasurer] 활성화 상태:', enabled);
            }

            // ===== Phase 2: 거리 계산 + 선 그리기 메서드 =====

            // 두 점 사이 거리 계산 (하버사인 공식)
            measureDistance(point1, point2) {
                if (!point1 || !point2) return 0;

                const lat1 = point1[0] * Math.PI / 180;  // 라디안 변환
                const lat2 = point2[0] * Math.PI / 180;
                const deltaLat = (point2[0] - point1[0]) * Math.PI / 180;
                const deltaLng = (point2[1] - point1[1]) * Math.PI / 180;

                const a = Math.sin(deltaLat/2) * Math.sin(deltaLat/2) +
                         Math.cos(lat1) * Math.cos(lat2) *
                         Math.sin(deltaLng/2) * Math.sin(deltaLng/2);
                const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));

                const distance = 6371000 * c; // 지구 반지름 6371km를 미터로
                console.log('[DistanceMeasurer] 거리 계산됨:', distance.toFixed(2) + 'm');
                return distance;
            }

            // 두 점 사이 직선 그리기
            drawLine(point1, point2) {
                if (!point1 || !point2) return null;

                // 기존 측정선 제거
                if (this.measurementLine) {
                    this.map.removeLayer(this.measurementLine);
                }

                // 새로운 측정선 그리기
                this.measurementLine = L.polyline([point1, point2], {
                    color: '#FF6B35',        // 주황색
                    weight: 3,
                    opacity: 0.8,
                    dashArray: '10, 5'      // 점선 효과
                }).addTo(this.map);

                console.log('[DistanceMeasurer] 측정선 그려짐:', point1, '→', point2);
                return this.measurementLine;
            }

            // Phase 2: 개선된 핀 선택 처리 (거리 측정 로직 추가)
            selectPinForMeasurement(marker) {
                if (!this.waitingForSecondPoint) {
                    // 첫 번째 점 선택
                    this.firstPoint = marker.getLatLng();
                    this.selectedMarker = marker;
                    this.highlightPin(marker);
                    this.waitingForSecondPoint = true;

                    console.log('[DistanceMeasurer] 첫 번째 점 선택됨:', {
                        lat: this.firstPoint.lat,
                        lng: this.firstPoint.lng,
                        type: marker._markerType || 'Unknown',
                        frame: marker._frameId || 'N/A'
                    });
                    console.log('[DistanceMeasurer] 두 번째 점을 선택하거나 지도를 클릭하세요');
                } else {
                    // 두 번째 점 선택 - 거리 측정 수행
                    this.secondPoint = marker.getLatLng();
                    this.performDistanceMeasurement();
                }
            }

            // ===== Phase 6: 에러 핸들링 강화된 거리 측정 수행 =====
            performDistanceMeasurement() {
                try {
                    // 기본 null/undefined 체크
                    if (!this.firstPoint || !this.secondPoint) {
                        console.error('[DistanceMeasurer] 측정에 필요한 점이 부족함');
                        return false;
                    }

                    // 좌표값 유효성 검사
                    if (!this.isValidCoordinate(this.firstPoint) || !this.isValidCoordinate(this.secondPoint)) {
                        console.error('[DistanceMeasurer] 유효하지 않은 좌표값');
                        this.resetMeasurementState();
                        return false;
                    }

                    // 거리 계산
                    const point1 = [this.firstPoint.lat, this.firstPoint.lng];
                    const point2 = [this.secondPoint.lat, this.secondPoint.lng];

                    this.currentDistance = this.measureDistance(point1, point2);

                    // 거리 계산 결과 검증
                    if (isNaN(this.currentDistance) || this.currentDistance < 0) {
                        console.error('[DistanceMeasurer] 거리 계산 실패');
                        this.resetMeasurementState();
                        return false;
                    }

                    // 직선 그리기
                    this.drawLine(point1, point2);

                    // ===== Phase 3: 중간점에 거리 텍스트 표시 =====
                    this.showMiddleText(point1, point2, this.currentDistance);

                    // ===== Phase 4: 우하단 거리 박스 표시 =====
                    this.showDistanceBox(this.currentDistance, point1, point2);

                    // 측정 결과 로그 출력
                    console.log('[DistanceMeasurer] ===== 거리 측정 완료 =====');
                    console.log('첫 번째 점:', point1);
                    console.log('두 번째 점:', point2);
                    console.log('측정 거리:', this.currentDistance.toFixed(2) + 'm');
                    console.log('측정 거리:', (this.currentDistance / 1000).toFixed(3) + 'km');
                    console.log('========================================');

                    // 상태 초기화 (다음 측정을 위해)
                    this.resetMeasurementState();
                    return true;

                } catch (error) {
                    console.error('[DistanceMeasurer] 거리 측정 중 오류 발생:', error);
                    this.resetMeasurementState();
                    return false;
                }
            }

            // ===== Phase 6: 좌표 유효성 검사 =====
            isValidCoordinate(point) {
                if (!point || typeof point !== 'object') return false;
                if (typeof point.lat !== 'number' || typeof point.lng !== 'number') return false;
                if (isNaN(point.lat) || isNaN(point.lng)) return false;
                if (Math.abs(point.lat) > 90 || Math.abs(point.lng) > 180) return false;
                return true;
            }

            // ===== Phase 5: 완전한 측정 상태 초기화 =====
            resetMeasurementState() {
                this.waitingForSecondPoint = false;
                this.firstPoint = null;
                this.secondPoint = null;
                this.currentDistance = 0;  // Phase 5: 거리값도 초기화

                // 선택된 마커 하이라이트 해제
                if (this.selectedMarker) {
                    this.clearSelection();
                }

                console.log('[DistanceMeasurer] Phase 5 완전한 측정 상태 초기화됨 - 새로운 측정 준비 완료');
            }

            // 측정 결과 삭제
            clearMeasurement() {
                if (this.measurementLine) {
                    this.map.removeLayer(this.measurementLine);
                    this.measurementLine = null;
                    console.log('[DistanceMeasurer] 측정선 제거됨');
                }

                // ===== Phase 3: 중간점 텍스트도 함께 제거 =====
                if (this.measurementTextMarker) {
                    this.map.removeLayer(this.measurementTextMarker);
                    this.measurementTextMarker = null;
                    console.log('[DistanceMeasurer] 중간점 텍스트 제거됨');
                }

                // ===== Phase 4: 거리 정보 박스도 함께 숨기기 =====
                this.hideDistanceBox();

                this.resetMeasurementState();
            }

            // ===== Phase 5: 측정 상태 체크 메서드 =====
            // 현재 완료된 측정 결과가 있는지 확인 (측정 중이 아닌 완료된 상태)
            hasMeasurement() {
                // 측정 완료 상태: 선이나 텍스트가 표시되어 있고, 두 번째 점 대기 중이 아닌 상태
                return !!(this.measurementLine || this.measurementTextMarker) && !this.waitingForSecondPoint;
            }

            // ===== Phase 3: 중간점 텍스트 표시 메서드 =====

            // 두 점의 중간점 계산
            calculateMidpoint(point1, point2) {
                if (!point1 || !point2) return null;

                const midLat = (point1[0] + point2[0]) / 2;
                const midLng = (point1[1] + point2[1]) / 2;

                console.log('[DistanceMeasurer] 중간점 계산됨:', {
                    lat: midLat.toFixed(6),
                    lng: midLng.toFixed(6)
                });

                return [midLat, midLng];
            }

            // 중간점에 거리 텍스트 표시
            showMiddleText(point1, point2, distance) {
                if (!point1 || !point2 || distance <= 0) return null;

                // 기존 중간점 텍스트 제거
                if (this.measurementTextMarker) {
                    this.map.removeLayer(this.measurementTextMarker);
                }

                // 중간점 계산
                const midpoint = this.calculateMidpoint(point1, point2);
                if (!midpoint) return null;

                // 거리 텍스트 포맷팅
                let distanceText;
                if (distance >= 1000) {
                    distanceText = (distance / 1000).toFixed(2) + ' km';
                } else {
                    distanceText = distance.toFixed(1) + ' m';
                }

                // 커스텀 DivIcon 생성 (텍스트 마커)
                const textIcon = L.divIcon({
                    html: `<div style="
                        background: rgba(255, 107, 53, 0.9);
                        color: white;
                        padding: 4px 8px;
                        border-radius: 4px;
                        font-size: 12px;
                        font-weight: bold;
                        text-align: center;
                        box-shadow: 0 2px 6px rgba(0,0,0,0.3);
                        border: 2px solid white;
                        min-width: 50px;
                        font-family: Arial, sans-serif;
                    ">${distanceText}</div>`,
                    className: 'distance-text-marker',
                    iconSize: [70, 25],
                    iconAnchor: [35, 12.5]
                });

                // 중간점에 텍스트 마커 생성
                this.measurementTextMarker = L.marker(midpoint, {
                    icon: textIcon,
                    interactive: false,  // 클릭 이벤트 방지
                    zIndexOffset: 1000   // 다른 마커들보다 위에 표시
                }).addTo(this.map);

                console.log('[DistanceMeasurer] 중간점 텍스트 표시됨:', distanceText, 'at', midpoint);
                return this.measurementTextMarker;
            }

            // ===== Phase 4: 우하단 거리 박스 메서드 =====

            // 우하단 거리 정보 박스 표시
            showDistanceBox(distance, point1, point2) {
                if (!distance || distance <= 0) return;

                const distanceBox = document.getElementById('distanceInfoBox');
                if (!distanceBox) {
                    console.error('[DistanceMeasurer] 거리 박스 요소를 찾을 수 없음');
                    return;
                }

                // 거리 정보 업데이트
                const distanceValue = document.getElementById('distanceValue');
                const distanceKm = document.getElementById('distanceKm');
                const point1Coords = document.getElementById('point1Coords');
                const point2Coords = document.getElementById('point2Coords');

                // 거리 텍스트 포맷팅
                let distanceText;
                if (distance >= 1000) {
                    distanceText = (distance / 1000).toFixed(2) + ' km';
                } else {
                    distanceText = distance.toFixed(1) + ' m';
                }

                // 데이터 업데이트
                if (distanceValue) distanceValue.textContent = distanceText;
                if (distanceKm) distanceKm.textContent = (distance / 1000).toFixed(3) + ' km';

                if (point1 && point1Coords) {
                    point1Coords.textContent = `${point1[0].toFixed(4)}, ${point1[1].toFixed(4)}`;
                }
                if (point2 && point2Coords) {
                    point2Coords.textContent = `${point2[0].toFixed(4)}, ${point2[1].toFixed(4)}`;
                }

                // 박스 표시 (애니메이션 효과 포함)
                distanceBox.classList.add('show');

                console.log('[DistanceMeasurer] 거리 박스 표시됨:', distanceText);
            }

            // 우하단 거리 정보 박스 숨기기
            hideDistanceBox() {
                const distanceBox = document.getElementById('distanceInfoBox');
                if (!distanceBox) return;

                distanceBox.classList.remove('show');

                // 내용 초기화
                const distanceValue = document.getElementById('distanceValue');
                const distanceKm = document.getElementById('distanceKm');
                const point1Coords = document.getElementById('point1Coords');
                const point2Coords = document.getElementById('point2Coords');

                if (distanceValue) distanceValue.textContent = '0 m';
                if (distanceKm) distanceKm.textContent = '0.000 km';
                if (point1Coords) point1Coords.textContent = '-';
                if (point2Coords) point2Coords.textContent = '-';

                console.log('[DistanceMeasurer] 거리 박스 숨겨짐');
            }
        }

        // DistanceMeasurer 전역 인스턴스 (기존 코드와 분리)
        let distanceMeasurer = null;
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
            'message': f'Python processing complete! {safe_int(gps_count)} GPS, {safe_int(imu_count)} IMU updates',
            'gps_count': safe_int(gps_count),
            'imu_count': safe_int(imu_count),
            'rail_count': 0,
            'process_time': safe_float(process_time),
            'path': clean_path_data(path)
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

            # GPS Loss Points (tunnel entrances)
            if 'is_gps_loss' in df.columns:
                loss_rows = df[df['is_gps_loss'] == 1]
                if len(loss_rows) > 0:
                    paths['gps_loss'] = [[row['eskf_lat'], row['eskf_lon']] for _, row in loss_rows.iterrows()]

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
            'message': f'C processing complete! {safe_int(gps_count)} GPS, {safe_int(imu_count)} IMU updates',
            'gps_count': safe_int(gps_count),
            'imu_count': safe_int(imu_count),
            'rail_count': safe_int(rail_count),
            'process_time': safe_float(process_time),
            'path': clean_path_data(path),  # 호환성을 위한 기본 경로
            'paths': {k: clean_path_data(v) for k, v in paths.items()} if isinstance(paths, dict) else {}  # 다중 경로 데이터
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

        # Removed satellite information loading

        # Use all frames from C output for complete timeline
        for i, idx in enumerate(range(len(c_df))):
            frame_data = c_df.iloc[idx]

            # Removed satellite information extraction

            realtime_session['data_frames'].append({
                'frame_id': i,
                'timestamp': float(frame_data['timestamp']),
                'gps_lat': float(frame_data['gps_raw_lat']),
                'gps_lng': float(frame_data['gps_raw_lon']),
                'eskf_lat': float(frame_data['eskf_lat']),
                'eskf_lng': float(frame_data['eskf_lon']),
                'route_projection': False  # Disabled route projection
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
            'timestamp': safe_float(current_data['timestamp']),
            'gps': [safe_float(current_data['gps_lat']), safe_float(current_data['gps_lng'])],
            'eskf': [safe_float(eskf_lat), safe_float(eskf_lng)],
            # 'satellites': removed,
            'route_projection': bool(current_data['route_projection']),
            'distance': safe_float(distance)
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