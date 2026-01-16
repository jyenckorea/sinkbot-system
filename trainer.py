# trainer.py (v2.03 - 로컬 SQLite 및 클라우드 PostgreSQL 통합 지원)
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
import joblib
import os
import psycopg2
import sqlite3
import io
from datetime import datetime

# --- 1. 환경 설정 ---
# 클라우드타입 환경 변수가 있는지 확인합니다.
IS_CLOUD_ENV = 'DB_HOST' in os.environ
DB_FILE = "sinkbot_data.db"

print(f"🤖 SinkBot v2.03 AI 모델 학습 시작 (모드: {'Cloud' if IS_CLOUD_ENV else 'Local'})")

def get_db_connection():
    """환경에 맞는 데이터베이스 연결을 반환합니다."""
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
        if not os.path.exists(DB_FILE):
            print(f"❌ 오류: {DB_FILE} 파일을 찾을 수 없습니다. 데이터를 먼저 수집하세요.")
            return None
        return sqlite3.connect(DB_FILE)

def load_and_process(conn):
    """DB에서 데이터를 읽어와 AI 학습용 특징(Feature)을 추출합니다."""
    try:
        # DB에서 전체 데이터 로드
        df = pd.read_sql_query("SELECT * FROM displacement ORDER BY device_id, timestamp", conn)
        
        if len(df) < 20:
            print(f"⚠️ 데이터 부족: 현재 {len(df)}건 (최소 20건 필요)")
            return None
            
        processed_frames = []
        for dev_id, group in df.groupby('device_id'):
            group = group.sort_values('timestamp').reset_index(drop=True)
            # 기준점 설정 (각 장치의 첫 데이터)
            ref = group.iloc[0]
            
            # 특징 추출 1: 수직 침하량 (Z축 변화의 절대값)
            group['delta_z'] = abs(group['z'] - ref['z'])
            
            # 특징 추출 2: 3차원 변위 거리
            group['dist_3d'] = np.sqrt(
                (group['x'] - ref['x'])**2 + 
                (group['y'] - ref['y'])**2 + 
                (group['z'] - ref['z'])**2
            )
            
            # 특징 추출 3: 기울기 변화량
            curr_mag = np.sqrt(group['tilt_x']**2 + group['tilt_y']**2)
            ref_mag = np.sqrt(ref['tilt_x']**2 + ref['tilt_y']**2)
            group['delta_tilt'] = curr_mag - ref_mag
            
            processed_frames.append(group)
            
        return pd.concat(processed_frames)
    except Exception as e:
        print(f"❌ 데이터 가공 중 오류: {e}")
        return None

def main():
    conn = get_db_connection()
    if conn is None: return

    full_df = load_and_process(conn)
    
    if full_df is not None:
        # 학습에 사용할 핵심 특징 선택
        features = full_df[['delta_z', 'dist_3d', 'delta_tilt']]
        
        # 모델 초기화 (이상치 비율 1% 설정)
        model = IsolationForest(contamination=0.01, random_state=42)
        
        print(f"⏳ {len(full_df)}개의 데이터를 학습 중...")
        model.fit(features)
        
        try:
            # 모델을 바이너리로 변환하여 DB에 저장 (파일 시스템 권한 문제 회피)
            buf = io.BytesIO()
            joblib.dump(model, buf)
            model_binary = buf.getvalue()
            
            cur = conn.cursor()
            if IS_CLOUD_ENV:
                # PostgreSQL용 저장 (기존 모델이 있으면 덮어쓰기)
                cur.execute("""
                    INSERT INTO ai_models (model_name, model_data) 
                    VALUES (%s, %s) 
                    ON CONFLICT (model_name) 
                    DO UPDATE SET model_data = EXCLUDED.model_data, created_at = NOW();
                """, ('sinkbot_model', model_binary))
            else:
                # 로컬 SQLite용 저장
                cur.execute("""
                    INSERT OR REPLACE INTO ai_models (model_name, model_data, created_at) 
                    VALUES (?, ?, ?)
                """, ('sinkbot_model', model_binary, datetime.now()))
                
            conn.commit()
            print("💾 v2.03 통합 AI 모델이 데이터베이스에 저장되었습니다.")
            
        except Exception as e:
            print(f"❌ 모델 저장 실패: {e}")
    
    conn.close()

if __name__ == "__main__":
    main()