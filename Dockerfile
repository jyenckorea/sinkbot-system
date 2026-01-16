# 1. 파이썬 3.11 슬림 버전 이미지 사용
FROM python:3.11-slim

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. PostgreSQL 라이브러리 설치를 위한 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 4. 종속성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 소스 코드 복사
COPY . .

# 6. 포트 설정
EXPOSE 5000
EXPOSE 8501

# 7. 기본 실행 명령
CMD ["python", "collector.py"]