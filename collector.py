# collector.py (v2.02 - 다중 장치 및 배터리 잔량 지원)
import os
from flask import Flask, request, jsonify
import psycopg2
import sqlite3
from datetime import datetime

app = Flask(__name__)

# --- 1. 환경 설정 ---
IS_CLOUD_ENV = 'DB_HOST' in os.environ

def get_db_connection():
    """환경에 따른 DB 연결 객체 반환"""
    if IS_CLOUD_ENV:
        dsn = (
            f"host={os.environ.get('DB_HOST')} "
            f"port={os.environ.get('DB_PORT')} "
            f"dbname={os.environ.get('DB_NAME')} "
            f"user={os.environ.get('DB_USER')} "
            f"password={os.environ.get('DB_PASSWORD')}"
        )
        return psycopg2.connect(dsn)
    else:
        return sqlite3.connect('sinkbot_data.db')

def init_db():
    """데이터베이스 v2.02 초기화 (battery 컬럼 및 ai_models 테이블 포함)"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    if IS_CLOUD_ENV:
        # 변위 데이터 테이블 (v2.02: battery 컬럼 추가)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS displacement (
                id SERIAL PRIMARY KEY,
                device_id VARCHAR(50),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                x DOUBLE PRECISION,
                y DOUBLE PRECISION,
                z DOUBLE PRECISION,
                tilt_x DOUBLE PRECISION,
                tilt_y DOUBLE PRECISION,
                battery DOUBLE PRECISION DEFAULT 100.0
            )
        """)
        # AI 모델 저장용 테이블
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ai_models (
                model_name VARCHAR(50) PRIMARY KEY,
                model_data BYTEA,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS displacement (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                x REAL, y REAL, z REAL,
                tilt_x REAL, tilt_y REAL,
                battery REAL DEFAULT 100.0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ai_models (
                model_name TEXT PRIMARY KEY,
                model_data BLOB,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
    conn.commit()
    conn.close()
    print("✅ 데이터베이스 v2.02 초기화 완료")

@app.route('/health', methods=['GET'])
def health():
    return "Healthy", 200

@app.route('/data', methods=['POST'])
def receive_data():
    """현장 에이전트로부터 데이터를 수신하여 저장합니다."""
    try:
        data = request.json
        device_id = data.get('device_id', 'SB-001')
        x, y, z = data.get('x'), data.get('y'), data.get('z')
        tx, ty = data.get('tilt_x'), data.get('tilt_y')
        battery = data.get('battery', 100.0)

        conn = get_db_connection()
        cur = conn.cursor()
        
        if IS_CLOUD_ENV:
            cur.execute(
                "INSERT INTO displacement (device_id, x, y, z, tilt_x, tilt_y, battery) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (device_id, x, y, z, tx, ty, battery)
            )
        else:
            cur.execute(
                "INSERT INTO displacement (device_id, x, y, z, tilt_x, tilt_y, battery) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (device_id, x, y, z, tx, ty, battery)
            )
            
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "device_id": device_id}), 201

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)