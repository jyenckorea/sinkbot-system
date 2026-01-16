# dashboard.py (v2.15 - Scikit-learn Feature Name 경고 해결 버전)
import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import os
import psycopg2
import plotly.express as px
import folium
from streamlit_folium import st_folium
from streamlit.components.v1 import html
import joblib
import io

# --- 1. Session State 및 설정 초기화 ---
if 'init' not in st.session_state:
    st.session_state.init = True
    st.session_state.auto_refresh = True
    st.session_state.refresh_interval = 10
    if 'thresholds' not in st.session_state:
        st.session_state.thresholds = {} 

# --- 2. 페이지 레이아웃 설정 ---
st.set_page_config(layout="wide", page_title="SinkBot Multi-Device v2.15")
st.title("🛰️ SinkBot v2.15 통합 관제 및 AI 실시간 분석 시스템")

# --- 3. 데이터베이스 및 보안 설정 ---
IS_CLOUD_ENV = 'DB_HOST' in os.environ
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin1234')

if IS_CLOUD_ENV:
    dsn = f"host={os.environ.get('DB_HOST')} port={os.environ.get('DB_PORT')} dbname={os.environ.get('DB_NAME')} user={os.environ.get('DB_USER')} password={os.environ.get('DB_PASSWORD')}"
else:
    DB_FILE = "sinkbot_data.db"

def get_connection():
    return psycopg2.connect(dsn) if IS_CLOUD_ENV else sqlite3.connect(DB_FILE)

@st.cache_data(ttl=2)
def load_all_data():
    """DB에서 모든 변위 데이터를 로드합니다."""
    try:
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM displacement ORDER BY timestamp ASC", conn)
        conn.close()
        required_cols = ['device_id', 'timestamp', 'x', 'y', 'z', 'tilt_x', 'tilt_y', 'battery']
        if df.empty: return pd.DataFrame(columns=required_cols)
        if 'device_id' not in df.columns: df['device_id'] = 'Unknown-01'
        if 'battery' not in df.columns: df['battery'] = 100.0
        return df
    except:
        return pd.DataFrame(columns=['device_id', 'timestamp', 'x', 'y', 'z', 'tilt_x', 'tilt_y', 'battery'])

@st.cache_resource(ttl=30)
def load_ai_model():
    """DB에서 최신 AI 모델을 불러옵니다."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT model_data, created_at FROM ai_models WHERE model_name = 'sinkbot_model'")
        row = cur.fetchone()
        conn.close()
        if row:
            model = joblib.load(io.BytesIO(row[0]))
            return model, row[1]
        return None, None
    except:
        return None, None

df_raw = load_all_data()
ai_model, model_updated_at = load_ai_model()

# --- 4. 사이드바 제어판 ---
with st.sidebar:
    st.header("⚙️ 시스템 설정 및 관리")
    
    # 4-1. AI 모델 상태 및 데이터 현황
    st.subheader("🤖 AI 분석 엔진")
    total_data_count = len(df_raw)
    if model_updated_at:
        st.success(f"모델 활성화 중 (갱신: {model_updated_at})")
    else:
        progress = min(total_data_count / 20, 1.0)
        st.warning(f"학습 데이터 수집 중 ({total_data_count}/20)")
        st.progress(progress)
    
    st.info(f"📊 수집된 총 데이터: {total_data_count} 건")
    st.markdown("---")
    
    # 4-2. 장치 선택
    if not df_raw.empty:
        device_list = sorted(df_raw['device_id'].unique())
        selected_device = st.selectbox("🎯 관제 장치 선택", device_list)
    else:
        selected_device = "N/A"

    st.markdown("---")
    
    # 4-3. 그래프 출력 항목
    st.subheader("📈 그래프 출력 항목")
    field_options = {
        "delta_z": "1. 수직 변위 (delta_z)",
        "dist_3d": "2. 3D 변위 거리 (dist_3d)",
        "delta_tilt": "3. 기울기 변화량 (delta_tilt)",
        "tilt_mag": "4. 총 기울기 (Magnitude)",
        "battery": "5. 배터리 잔량",
        "z": "6. 고도 (z)",
        "tilt_x": "7. X축 상세 기울기",
        "tilt_y": "8. Y축 상세 기울기",
        "x": "9. 경도 (x)",
        "y": "10. 위도 (y)"
    }
    selected_field = st.selectbox("조회 항목 선택", options=list(field_options.keys()), format_func=lambda x: field_options[x])

    st.markdown("---")
    
    # 4-4. 안전 기준 설정
    if selected_device != "N/A":
        st.subheader(f"⚠️ {selected_device} 안전 기준")
        curr_lim = st.session_state.thresholds.get(selected_device, [0.010, 0.030, 0.050])
        l1 = st.number_input("1차 주의 (m)", value=float(curr_lim[0]), format="%.3f", step=0.001)
        l2 = st.number_input("2차 경고 (m)", value=float(curr_lim[1]), format="%.3f", step=0.001)
        l3 = st.number_input("3차 위험 (m)", value=float(curr_lim[2]), format="%.3f", step=0.001)
        
        if st.button("설정값 저장"):
            st.session_state.thresholds[selected_device] = [l1, l2, l3]
            st.toast(f"{selected_device} 기준이 업데이트되었습니다.")

    st.markdown("---")
    st.toggle("자동 새로고침", key="auto_refresh", value=True)
    st.select_slider("새로고침 주기(초)", options=[5, 10, 30, 60], key="refresh_interval")

    with st.expander("🔒 관리자 전용"):
        pwd = st.text_input("보안 코드 입력", type="password")
        if pwd == ADMIN_PASSWORD:
            if st.button("🚨 데이터베이스 초기화"):
                conn = get_connection(); cur = conn.cursor()
                cur.execute("DELETE FROM displacement")
                cur.execute("DELETE FROM ai_models")
                conn.commit(); conn.close()
                st.cache_data.clear()
                st.rerun()

# --- 5. 데이터 가공 및 AI 예측 로직 ---
def process_device_data(df, dev_id):
    if df.empty or dev_id == "N/A": return None
    df_dev = df[df['device_id'] == dev_id].copy()
    if df_dev.empty: return None
    df_dev['timestamp'] = pd.to_datetime(df_dev['timestamp'])
    df_dev = df_dev.sort_values('timestamp').reset_index(drop=True)
    
    # 기준점 대비 변위 및 AI 특징 추출
    ref = df_dev.iloc[0]
    df_dev['delta_z'] = abs(df_dev['z'] - ref['z'])
    df_dev['dist_3d'] = np.sqrt((df_dev['x']-ref['x'])**2 + (df_dev['y']-ref['y'])**2 + (df_dev['z']-ref['z'])**2)
    df_dev['tilt_mag'] = np.sqrt(df_dev['tilt_x']**2 + df_dev['tilt_y']**2)
    ref_tilt_mag = np.sqrt(ref['tilt_x']**2 + ref['tilt_y']**2)
    df_dev['delta_tilt'] = df_dev['tilt_mag'] - ref_tilt_mag
    
    return df_dev

df_target = process_device_data(df_raw, selected_device)

# --- 6. 메인 시각화 UI ---
if df_target is not None:
    latest = df_target.iloc[-1]
    cur_dz = latest['delta_z']
    cur_bat = latest['battery']
    limits = st.session_state.thresholds.get(selected_device, [0.010, 0.030, 0.050])
    
    # 6-1. AI 예측 수행 (Feature Name 경고 수정 지점)
    ai_status = "데이터 부족"
    ai_color = "gray"
    if ai_model:
        # ⭐️ 중요: 학습 시 사용한 컬럼명과 동일한 데이터프레임으로 변환하여 전달
        input_df = pd.DataFrame([[latest['delta_z'], latest['dist_3d'], latest['delta_tilt']]], 
                                columns=['delta_z', 'dist_3d', 'delta_tilt'])
        prediction = ai_model.predict(input_df)[0] 
        ai_status = "정상 패턴" if prediction == 1 else "이상 탐지"
        ai_color = "#28a745" if prediction == 1 else "#dc3545"

    # 6-2. 상단 알림 배너
    if ai_status == "이상 탐지":
        st.error(f"🔥 [AI 경고] {selected_device}에서 패턴 이상이 탐지되었습니다!", icon="⚠️")
    
    if cur_dz >= limits[2]:
        st.error(f"🚨 [3차 위험] 변위 {cur_dz:.4f}m가 위험 기준을 초과했습니다!", icon="🔥")
    elif cur_dz >= limits[1]:
        st.warning(f"🟠 [2차 경고] 변위 {cur_dz:.4f}m가 경고 수준입니다.", icon="⚠️")
    elif cur_dz >= limits[0]:
        st.info(f"🟡 [1차 주의] 변위 {cur_dz:.4f}m가 감지되었습니다.", icon="👀")
    
    if cur_bat < 20.0:
        st.error(f"🪫 [배터리 부족] {selected_device} 잔량: {cur_bat}%", icon="🔋")

    st.subheader(f"📢 {selected_device} 실시간 관제 현황")

    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("📍 현재 위치 및 AI 분석")
        m = folium.Map(location=[latest['y'], latest['x']], zoom_start=17)
        folium.Marker([latest['y'], latest['x']], popup=selected_device).add_to(m)
        st_folium(m, height=300, width='stretch', key=f"map_{selected_device}_{len(df_target)}")
        
        st.markdown(f"""
            <div style="background-color: {ai_color}; padding: 15px; border-radius: 10px; text-align: center; color: white; font-weight: bold; margin-bottom: 20px; font-size: 1.2em;">
                AI 패턴 분석 결과: {ai_status}
            </div>
        """, unsafe_allow_html=True)

        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("수직 변위", f"{cur_dz:.4f} m")
        m_col2.metric("기울기 변화", f"{latest['delta_tilt']:.2f}°")
        m_col3.metric("배터리", f"{cur_bat}%")

    with col2:
        st.subheader(f"📈 {field_options[selected_field]} 실시간 추이")
        fig = px.line(df_target, x='timestamp', y=selected_field, markers=True, 
                      title=f"{selected_device} - {field_options[selected_field]} 변화 기록")
        
        if selected_field == "delta_z":
            fig.add_hline(y=limits[0], line_dash="dot", line_color="yellow", annotation_text="주의")
            fig.add_hline(y=limits[1], line_dash="dash", line_color="orange", annotation_text="경고")
            fig.add_hline(y=limits[2], line_dash="solid", line_color="red", annotation_text="위험")
        
        st.plotly_chart(fig, width='stretch')

    st.subheader("🗃️ 상세 데이터 로그 (최신 10건)")
    st.dataframe(df_target.tail(10).iloc[::-1], width='stretch')
else:
    st.info("데이터 수집 대기 중입니다. 현장 장비나 시뮬레이터를 실행해 주세요.")

if st.session_state.auto_refresh:
    html(f"""<meta http-equiv="refresh" content="{st.session_state.refresh_interval}">""", height=0)