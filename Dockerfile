# 1. 파이썬 3.11 슬림 버전 이미지 사용
FROM python:3.11-slim

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. 시스템 패키지 설치 (PostgreSQL 연결용)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 4. 종속성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 소스 코드 복사
COPY . .

# 6. 스트림릿 권한 에러 해결을 위한 설정
# .streamlit 폴더를 미리 만들고 권한을 부여하거나, 
# 환경 변수를 통해 루트가 아닌 /app 경로를 홈으로 사용하도록 설정합니다.
ENV HOME=/app
RUN mkdir -p /app/.streamlit && chmod 777 /app/.streamlit

# 7. 스트림릿 통계 수집 비활성화 (권한 에러 방지 핵심)
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_SERVER_HEADLESS=true

# 8. 포트 설정
EXPOSE 5000
EXPOSE 8501

# 9. 기본 실행 명령 (기본값은 collector)
CMD ["python", "collector.py"]