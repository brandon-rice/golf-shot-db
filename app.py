"""
Golf Shot DB - Cloud Version with Local PostgreSQL Sync
Deploy this to Render.com or Railway.app
"""

from flask import Flask, render_template_string, request, jsonify, send_from_directory
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Cloud PostgreSQL connection (provided by Render/Railway)
DATABASE_URL = os.environ.get('DATABASE_URL')

# Parse DATABASE_URL for cloud services
if DATABASE_URL:
    # Handle Render's postgresql:// URLs
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_db_connection():
    """Create a database connection to cloud PostgreSQL"""
    return psycopg2.connect(DATABASE_URL)

def init_db():
    """Initialize the PostgreSQL database with required tables"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Create tables if they don't exist
    cur.execute('''
        CREATE TABLE IF NOT EXISTS rounds (
            round_id BIGINT PRIMARY KEY,
            date TIMESTAMP NOT NULL,
            course_name VARCHAR(255),
            total_holes INTEGER,
            total_shots INTEGER,
            total_score INTEGER,
            weather VARCHAR(100),
            notes TEXT,
            synced_to_local BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS shots (
            shot_id SERIAL PRIMARY KEY,
            round_id BIGINT NOT NULL,
            hole INTEGER NOT NULL,
            shot_number INTEGER NOT NULL,
            club VARCHAR(50) NOT NULL,
            shot_type VARCHAR(50) NOT NULL,
            latitude DOUBLE PRECISION NOT NULL,
            longitude DOUBLE PRECISION NOT NULL,
            accuracy REAL,
            distance INTEGER,
            elevation_change REAL,
            wind_speed INTEGER,
            wind_direction VARCHAR(10),
            timestamp TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (round_id) REFERENCES rounds (round_id) ON DELETE CASCADE
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS holes (
            hole_id SERIAL PRIMARY KEY,
            round_id BIGINT NOT NULL,
            hole_number INTEGER NOT NULL,
            score INTEGER NOT NULL,
            par INTEGER,
            fairway_hit BOOLEAN,
            green_in_regulation BOOLEAN,
            putts INTEGER,
            notes TEXT,  -- Added notes field for each hole
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (round_id) REFERENCES rounds (round_id) ON DELETE CASCADE
        )
    ''')
    
    # Create indexes for better performance
    cur.execute('CREATE INDEX IF NOT EXISTS idx_shots_round_id ON shots(round_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_holes_round_id ON holes(round_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_rounds_date ON rounds(date DESC)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_rounds_synced ON rounds(synced_to_local)')
    
    conn.commit()
    cur.close()
    conn.close()
    print("Cloud PostgreSQL database initialized successfully!")

# HTML Template with Notes Feature
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <title>Golf Shot DB</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 500px;
            margin: 0 auto;
        }
        
        .card {
            background: white;
            border-radius: 20px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        h1 {
            color: #333;
            margin-bottom: 20px;
            text-align: center;
            font-size: 28px;
        }
        
        h2 {
            color: #555;
            margin-bottom: 15px;
            font-size: 20px;
        }
        
        .round-info {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .info-box {
            background: #f7f7f7;
            padding: 10px;
            border-radius: 10px;
            text-align: center;
        }
        
        .info-label {
            font-size: 12px;
            color: #666;
            margin-bottom: 5px;
        }
        
        .info-value {
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
        }
        
        .form-group {
            margin-bottom: 15px;
        }
        
        label {
            display: block;
            margin-bottom: 5px;
            color: #555;
            font-weight: 500;
        }
        
        select, input[type="number"], textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            background: white;
            transition: border-color 0.3s;
            font-family: inherit;
        }
        
        textarea {
            min-height: 80px;
            resize: vertical;
        }
        
        select:focus, input[type="number"]:focus, textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .button {
            width: 100%;
            padding: 15px;
            border: none;
            border-radius: 10px;
            font-size: 18px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            margin-bottom: 10px;
        }
        
        .button-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .button-secondary {
            background: #f0f0f0;
            color: #333;
        }
        
        .button-danger {
            background: #ff6b6b;
            color: white;
        }
        
        .button-success {
            background: #51cf66;
            color: white;
        }
        
        .gps-status {
            padding: 10px;
            border-radius: 10px;
            text-align: center;
            margin-bottom: 15px;
            font-weight: 500;
        }
        
        .gps-active {
            background: #d4edda;
            color: #155724;
        }
        
        .gps-waiting {
            background: #fff3cd;
            color: #856404;
        }
        
        .gps-error {
            background: #f8d7da;
            color: #721c24;
        }
        
        .shot-list {
            max-height: 300px;
            overflow-y: auto;
        }
        
        .shot-item {
            background: #f7f7f7;
            padding: 10px;
            border-radius: 10px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .shot-details {
            flex: 1;
        }
        
        .shot-distance {
            font-size: 18px;
            font-weight: bold;
            color: #667eea;
            margin-left: 10px;
        }
        
        .hole-notes {
            background: #f0f8ff;
            padding: 10px;
            border-radius: 10px;
            margin-top: 10px;
            font-style: italic;
            color: #555;
        }
        
        .sync-status {
            position: fixed;
            top: 20px;
            right: 20px;
            background: #28a745;
            color: white;
            padding: 10px 15px;
            border-radius: 20px;
            font-size: 12px;
            display: none;
            z-index: 1000;
        }
        
        .sync-status.show {
            display: block;
        }
    </style>
</head>
<body>
    <div class="sync-status" id="sync-status">
        ☁️ Saved to cloud
    </div>
    
    <div class="container">
        <div class="card">
            <h1>⛳ Golf Shot DB</h1>
            <p style="text-align: center; color: #999; font-size: 14px; margin-bottom: 20px;">
                Cloud Database - Syncs to Local PostgreSQL
            </p>
            
            <div class="round-info">
                <div class="info-box">
                    <div class="info-label">Current Hole</div>
                    <div class="info-value" id="current-hole">1</div>
                </div>
                <div class="info-box">
                    <div class="info-label">Total Shots</div>
                    <div class="info-value" id="total-shots">0</div>
                </div>
            </div>
            
            <div class="form-group">
                <label for="course-name">Golf Course</label>
                <input type="text" id="course-name" placeholder="Enter course name" list="course-list" style="width: 100%; padding: 12px; border: 2px solid #e0e0e0; border-radius: 10px; font-size: 16px;">
                <datalist id="course-list">
                    <!-- Will be populated with nearby courses -->
                </datalist>
                <button class="button button-secondary" onclick="findNearbyCourses()" style="margin-top: 10px;">
                    📍 Find Nearby Courses
                </button>
            </div>
            
            <div id="gps-status" class="gps-status gps-waiting">
                📍 Waiting for GPS...
            </div>
            
            <div class="form-group">
                <label for="club">Club Selection</label>
                <select id="club">
                    <option value="">Select Club</option>
                    <optgroup label="Woods">
                        <option value="Driver">Driver</option>
                        <option value="3 Wood">3 Wood</option>
                        <option value="5 Wood">5 Wood</option>
                    </optgroup>
                    <optgroup label="Hybrids">
                        <option value="2 Hybrid">2 Hybrid</option>
                        <option value="3 Hybrid">3 Hybrid</option>
                        <option value="4 Hybrid">4 Hybrid</option>
                    </optgroup>
                    <optgroup label="Irons">
                        <option value="3 Iron">3 Iron</option>
                        <option value="4 Iron">4 Iron</option>
                        <option value="5 Iron">5 Iron</option>
                        <option value="6 Iron">6 Iron</option>
                        <option value="7 Iron">7 Iron</option>
                        <option value="8 Iron">8 Iron</option>
                        <option value="9 Iron">9 Iron</option>
                    </optgroup>
                    <optgroup label="Wedges">
                        <option value="PW">Pitching Wedge</option>
                        <option value="GW">Gap Wedge</option>
                        <option value="SW">Sand Wedge</option>
                        <option value="LW">Lob Wedge</option>
                    </optgroup>
                    <optgroup label="Putter">
                        <option value="Putter">Putter</option>
                    </optgroup>
                </select>
            </div>
            
            <div class="form-group">
                <label for="shot-type">Shot Type</label>
                <select id="shot-type">
                    <option value="Tee">Tee Shot</option>
                    <option value="Fairway">Fairway</option>
                    <option value="Rough">Rough</option>
                    <option value="Sand">Sand/Bunker</option>
                    <option value="Chip">Chip</option>
                    <option value="Putt">Putt</option>
                    <option value="Recovery">Recovery</option>
                </select>
            </div>
            
            <button class="button button-primary" onclick="recordShot()">
                📍 Record Shot
            </button>
            
            <h2>Current Hole Shots</h2>
            <div id="shot-list" class="shot-list">
                <p style="color: #999; text-align: center;">No shots recorded yet</p>
            </div>
            
            <div class="form-group" style="margin-top: 20px;">
                <label for="hole-notes">Hole Notes (optional)</label>
                <textarea id="hole-notes" placeholder="Add notes about this hole - conditions, strategy, lessons learned..."></textarea>
            </div>
            
            <div class="form-group">
                <label for="hole-score">Hole Score</label>
                <input type="number" id="hole-score" min="1" max="15" placeholder="Enter score">
            </div>
            
            <button class="button button-success" onclick="finishHole()">
                ✅ Finish Hole
            </button>
            
            <button class="button button-danger" onclick="endRound()">
                🏁 End Round
            </button>
        </div>
    </div>
    
    <script>
        let currentPosition = null;
        let shots = [];
        let currentHole = 1;
        let roundId = Date.now();
        let holeNotes = {};
        let courseName = '';
        let savedCourses = JSON.parse(localStorage.getItem('savedCourses') || '[]');
        
        // Load saved courses into datalist
        function loadSavedCourses() {
            const datalist = document.getElementById('course-list');
            savedCourses.forEach(course => {
                const option = document.createElement('option');
                option.value = course;
                datalist.appendChild(option);
            });
        }
        
        // Find nearby golf courses using Overpass API (OpenStreetMap)
        async function findNearbyCourses() {
            if (!currentPosition) {
                alert('Waiting for GPS location. Please try again in a moment.');
                return;
            }
            
            const lat = currentPosition.coords.latitude;
            const lon = currentPosition.coords.longitude;
            const radius = 10000; // 10km radius
            
            // Show loading state
            const btn = event.target;
            const originalText = btn.innerHTML;
            btn.innerHTML = '⏳ Searching...';
            btn.disabled = true;
            
            try {
                // Overpass API query for golf courses
                const query = `
                    [out:json][timeout:25];
                    (
                        way["leisure"="golf_course"](around:${radius},${lat},${lon});
                        node["leisure"="golf_course"](around:${radius},${lat},${lon});
                        relation["leisure"="golf_course"](around:${radius},${lat},${lon});
                    );
                    out body;
                    >;
                    out skel qt;
                `;
                
                const response = await fetch('https://overpass-api.de/api/interpreter', {
                    method: 'POST',
                    body: query,
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    }
                });
                
                if (response.ok) {
                    const data = await response.json();
                    const courses = new Set();
                    
                    data.elements.forEach(element => {
                        if (element.tags && element.tags.name) {
                            courses.add(element.tags.name);
                        }
                    });
                    
                    // Update datalist with found courses
                    const datalist = document.getElementById('course-list');
                    datalist.innerHTML = '';
                    
                    // Add saved courses first
                    savedCourses.forEach(course => {
                        const option = document.createElement('option');
                        option.value = course;
                        datalist.appendChild(option);
                    });
                    
                    // Add newly found courses
                    courses.forEach(course => {
                        if (!savedCourses.includes(course)) {
                            const option = document.createElement('option');
                            option.value = course;
                            datalist.appendChild(option);
                        }
                    });
                    
                    if (courses.size > 0) {
                        alert(`Found ${courses.size} golf courses nearby. Select from the dropdown or type your own.`);
                    } else {
                        alert('No courses found nearby. You can still type the course name manually.');
                    }
                } else {
                    // Fallback to manual entry
                    alert('Could not search for courses. Please enter the course name manually.');
                }
            } catch (error) {
                console.error('Error searching for courses:', error);
                alert('Could not search for courses. Please enter the course name manually.');
            } finally {
                btn.innerHTML = originalText;
                btn.disabled = false;
            }
        }
        
        // Save course name when entered
        function saveCourseName() {
            const input = document.getElementById('course-name');
            courseName = input.value.trim();
            
            // Save to recent courses if not already there
            if (courseName && !savedCourses.includes(courseName)) {
                savedCourses.unshift(courseName);
                // Keep only last 10 courses
                if (savedCourses.length > 10) {
                    savedCourses.pop();
                }
                localStorage.setItem('savedCourses', JSON.stringify(savedCourses));
            }
        }
        
        // Initialize GPS tracking
        function initGPS() {
            if ("geolocation" in navigator) {
                navigator.geolocation.watchPosition(
                    (position) => {
                        currentPosition = position;
                        updateGPSStatus('active');
                    },
                    (error) => {
                        console.error("GPS Error:", error);
                        updateGPSStatus('error');
                    },
                    {
                        enableHighAccuracy: true,
                        timeout: 5000,
                        maximumAge: 0
                    }
                );
            } else {
                updateGPSStatus('error');
                alert("GPS is not available on this device");
            }
        }
        
        function updateGPSStatus(status) {
            const statusEl = document.getElementById('gps-status');
            if (status === 'active') {
                statusEl.className = 'gps-status gps-active';
                statusEl.innerHTML = '📍 GPS Active - Ready to record';
            } else if (status === 'error') {
                statusEl.className = 'gps-status gps-error';
                statusEl.innerHTML = '❌ GPS Error - Check permissions';
            } else {
                statusEl.className = 'gps-status gps-waiting';
                statusEl.innerHTML = '📍 Waiting for GPS...';
            }
        }
        
        function showSyncStatus() {
            const status = document.getElementById('sync-status');
            status.classList.add('show');
            setTimeout(() => {
                status.classList.remove('show');
            }, 2000);
        }
        
        function recordShot() {
            const club = document.getElementById('club').value;
            const shotType = document.getElementById('shot-type').value;
            
            if (!club) {
                alert('Please select a club');
                return;
            }
            
            if (!currentPosition) {
                alert('Waiting for GPS signal. Please try again in a moment.');
                return;
            }
            
            const shot = {
                shot_number: shots.filter(s => s.hole === currentHole).length + 1,
                hole: currentHole,
                club: club,
                shot_type: shotType,
                latitude: currentPosition.coords.latitude,
                longitude: currentPosition.coords.longitude,
                accuracy: currentPosition.coords.accuracy,
                timestamp: new Date().toISOString()
            };
            
            // Calculate distance from previous shot if exists
            const currentHoleShots = shots.filter(s => s.hole === currentHole);
            if (currentHoleShots.length > 0) {
                const lastShot = currentHoleShots[currentHoleShots.length - 1];
                shot.distance = calculateDistance(
                    lastShot.latitude, 
                    lastShot.longitude,
                    shot.latitude,
                    shot.longitude
                );
            }
            
            shots.push(shot);
            updateShotList();
            saveShot(shot);
            
            // Clear club selection for next shot
            document.getElementById('club').value = '';
            
            // Update total shots
            document.getElementById('total-shots').textContent = shots.length;
        }
        
        function calculateDistance(lat1, lon1, lat2, lon2) {
            const R = 6371000; // Earth's radius in meters
            const φ1 = lat1 * Math.PI / 180;
            const φ2 = lat2 * Math.PI / 180;
            const Δφ = (lat2 - lat1) * Math.PI / 180;
            const Δλ = (lon2 - lon1) * Math.PI / 180;
            
            const a = Math.sin(Δφ/2) * Math.sin(Δφ/2) +
                    Math.cos(φ1) * Math.cos(φ2) *
                    Math.sin(Δλ/2) * Math.sin(Δλ/2);
            const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
            
            const meters = R * c;
            const yards = meters * 1.09361;
            return Math.round(yards);
        }
        
        function updateShotList() {
            const listEl = document.getElementById('shot-list');
            const currentHoleShots = shots.filter(s => s.hole === currentHole);
            
            if (currentHoleShots.length === 0) {
                listEl.innerHTML = '<p style="color: #999; text-align: center;">No shots recorded yet</p>';
                return;
            }
            
            listEl.innerHTML = currentHoleShots.map(shot => `
                <div class="shot-item">
                    <div class="shot-details">
                        <strong>Shot ${shot.shot_number}:</strong> ${shot.club} (${shot.shot_type})
                        ${shot.distance ? `<span class="shot-distance">${shot.distance} yds</span>` : ''}
                    </div>
                </div>
            `).join('');
        }
        
        function finishHole() {
            const score = document.getElementById('hole-score').value;
            const notes = document.getElementById('hole-notes').value;
            
            if (!score) {
                alert('Please enter your score for this hole');
                return;
            }
            
            // Save hole notes
            if (notes) {
                holeNotes[currentHole] = notes;
            }
            
            // Save hole data
            saveHoleScore(currentHole, score, notes);
            
            // Move to next hole
            currentHole++;
            document.getElementById('current-hole').textContent = currentHole;
            document.getElementById('hole-score').value = '';
            document.getElementById('hole-notes').value = '';
            
            updateShotList();
            alert(`Hole ${currentHole - 1} complete! Score: ${score}`);
        }
        
        function endRound() {
            if (confirm('Are you sure you want to end this round?')) {
                // Save course name
                saveCourseName();
                
                // Save round summary
                saveRoundSummary();
                alert('Round complete! Your data has been saved to the cloud.');
                
                // Reset everything
                shots = [];
                currentHole = 1;
                roundId = Date.now();
                holeNotes = {};
                courseName = '';
                document.getElementById('current-hole').textContent = currentHole;
                document.getElementById('total-shots').textContent = 0;
                document.getElementById('hole-notes').value = '';
                document.getElementById('course-name').value = '';
                updateShotList();
            }
        }
        
        // API calls to save data
        async function saveShot(shot) {
            try {
                const response = await fetch('/api/shot', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        ...shot,
                        round_id: roundId
                    })
                });
                const data = await response.json();
                console.log('Shot saved:', data);
                showSyncStatus();
            } catch (error) {
                console.error('Error saving shot:', error);
                // Store locally if server is not available
                localStorage.setItem('pending_shots', JSON.stringify(shots));
            }
        }
        
        async function saveHoleScore(hole, score, notes) {
            try {
                const response = await fetch('/api/hole', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        round_id: roundId,
                        hole: hole,
                        score: score,
                        notes: notes,
                        shots: shots.filter(s => s.hole === hole)
                    })
                });
                const data = await response.json();
                console.log('Hole saved:', data);
                showSyncStatus();
            } catch (error) {
                console.error('Error saving hole:', error);
            }
        }
        
        async function saveRoundSummary() {
            const courseName = document.getElementById('course-name').value.trim();
            
            try {
                const response = await fetch('/api/round', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        round_id: roundId,
                        course_name: courseName,
                        total_holes: currentHole - 1,
                        total_shots: shots.length,
                        shots: shots,
                        date: new Date().toISOString()
                    })
                });
                const data = await response.json();
                console.log('Round saved:', data);
                showSyncStatus();
            } catch (error) {
                console.error('Error saving round:', error);
            }
        }
        
        // Initialize on load
        window.addEventListener('load', () => {
            initGPS();
            loadSavedCourses();
        });
        
        // Prevent accidental page reload
        window.addEventListener('beforeunload', (e) => {
            if (shots.length > 0) {
                e.preventDefault();
                e.returnValue = '';
            }
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    """Serve the main HTML page"""
    return HTML_TEMPLATE

@app.route('/api/shot', methods=['POST'])
def save_shot():
    """Save a single shot to the database"""
    try:
        data = request.json
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute('''
            INSERT INTO shots (round_id, hole, shot_number, club, shot_type, 
                             latitude, longitude, accuracy, distance, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING shot_id
        ''', (
            data['round_id'],
            data['hole'],
            data['shot_number'],
            data['club'],
            data['shot_type'],
            data['latitude'],
            data['longitude'],
            data.get('accuracy'),
            data.get('distance'),
            data.get('timestamp', datetime.now())
        ))
        
        shot_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'shot_id': shot_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/hole', methods=['POST'])
def save_hole():
    """Save hole completion data with notes"""
    try:
        data = request.json
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute('''
            INSERT INTO holes (round_id, hole_number, score, notes)
            VALUES (%s, %s, %s, %s)
        ''', (
            data['round_id'],
            data['hole'],
            data['score'],
            data.get('notes', '')
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/round', methods=['POST'])
def save_round():
    """Save round summary data"""
    try:
        data = request.json
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute('''
            INSERT INTO rounds (round_id, date, course_name, total_holes, total_shots)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (round_id) 
            DO UPDATE SET
                course_name = EXCLUDED.course_name,
                total_holes = EXCLUDED.total_holes,
                total_shots = EXCLUDED.total_shots,
                date = EXCLUDED.date
        ''', (
            data['round_id'],
            data.get('date', datetime.now()),
            data.get('course_name', ''),
            data.get('total_holes'),
            data.get('total_shots')
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/export/unsynced', methods=['GET'])
def export_unsynced():
    """Export all unsynced rounds for local import"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get unsynced rounds
        cur.execute('''
            SELECT * FROM rounds 
            WHERE synced_to_local = FALSE 
            ORDER BY date DESC
        ''')
        rounds = cur.fetchall()
        
        result = []
        for round_data in rounds:
            # Get shots for this round
            cur.execute('''
                SELECT * FROM shots 
                WHERE round_id = %s 
                ORDER BY hole, shot_number
            ''', (round_data['round_id'],))
            shots = cur.fetchall()
            
            # Get holes for this round
            cur.execute('''
                SELECT * FROM holes 
                WHERE round_id = %s 
                ORDER BY hole_number
            ''', (round_data['round_id'],))
            holes = cur.fetchall()
            
            result.append({
                'round': round_data,
                'shots': shots,
                'holes': holes
            })
        
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/mark-synced/<round_id>', methods=['POST'])
def mark_synced(round_id):
    """Mark a round as synced to local database"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute('''
            UPDATE rounds 
            SET synced_to_local = TRUE 
            WHERE round_id = %s
        ''', (round_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Health check endpoint for cloud services"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT 1')
        cur.close()
        conn.close()
        return jsonify({'status': 'healthy', 'database': 'connected'})
    except:
        return jsonify({'status': 'unhealthy', 'database': 'disconnected'}), 500

if __name__ == '__main__':
    # Initialize database
    init_db()
    
    # For cloud deployment
    port = int(os.environ.get('PORT', 5000))
    
    print("\n" + "="*50)
    print("🏌️ Golf Shot DB Server Started!")
    print("="*50)
    print(f"Port: {port}")
    print("Database: Cloud PostgreSQL")
    print("="*50 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=False)