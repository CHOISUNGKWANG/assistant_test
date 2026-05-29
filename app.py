import os
import json
import time
import requests
import streamlit as st
from openai import AzureOpenAI
import warnings

# DeprecationWarning 계열의 경고 로그를 전면 차단하여 출력하지 않음
warnings.filterwarnings(action='ignore', category=DeprecationWarning)

# 1. API 설정
endpoint = st.secrets["ENDPOINT"]
apikey = st.secrets["API_KEY"]

client = AzureOpenAI(
    azure_endpoint=endpoint,
    api_key=apikey,
    api_version="2024-05-01-preview"
)

# 스트림릿 UI 구성
st.set_page_config(page_title="말랑 만능 AI 비서", layout="wide")

# 🎨 정밀 레이트 CSS 주입
st.markdown("""
    <style>
    .stApp { background-color: #F7F4EF !important; }
    [data-testid="stSidebar"] { background-color: #EFE9E1 !important; }
    .stApp h1, .stApp h2, .stApp h3, .stApp label, .stApp caption {
        color: #4A3B32 !important; font-family: 'Malgun Gothic', sans-serif;
    }
    .stApp p, .stApp li, .stMarkdown p, [data-testid="stChatMessage"] p {
        color: #4A3B32 !important; font-family: 'Malgun Gothic', sans-serif;
    }
    div.stButton > button {
        border-radius: 20px !important; background-color: #D9C3B0 !important;
        color: #4A3B32 !important; border: 1px solid #C4A482 !important;
        font-weight: bold; transition: all 0.3s;
    }
    div.stButton > button:hover {
        background-color: #C4A482 !important; color: white !important; transform: scale(1.03);
    }
    .stChatInputContainer textarea { color: #4A3B32 !important; }
    .stChatInputContainer { border-radius: 15px !important; }
    .citation-box {
        background-color: #EAE3D8; padding: 10px; border-left: 4px solid #C4A482;
        border-radius: 5px; margin-top: 10px; font-size: 0.9rem; color: #5A4A40;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🧸 말랑말랑 통합 AI 비서")
st.caption("외부 실시간 API 연동부터 파이썬 시각화, 문서 정밀 탐색까지 모두 처리합니다.")

# 🛠️ [백엔드 함수 정의 1] 곱셈 연산
def getMultipliedValue(num1, num2):
    return json.dumps({"result": num1 * num2})

# 🛠️ [백엔드 함수 정의 2] 실시간 날씨 API
def get_weather(location):
    try:
        location_map = {
            "용인시": "Yongin", "용인": "Yongin", "서울시": "Seoul", "서울": "Seoul",
            "안양시": "Anyang", "안양": "Anyang", "인천": "Incheon", "부산": "Busan"
        }
        eng_location = location_map.get(location, location)
        url = f"https://wttr.in/{eng_location},KR?format=j1"
        headers = {"User-Agent": "curl"}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            current = response.json()["current_condition"][0]
            return json.dumps({
                "location": location, "temp_c": current["temp_C"],
                "condition": current["weatherDesc"][0]["value"], "humidity": f"{current['humidity']}%"
            }, ensure_ascii=False)
        return json.dumps({"error": "Weather API failed"})
    except Exception as e:
        return json.dumps({"error": str(e)})

# 🛠️ [백엔드 함수 정의 3] 구글 웹 검색 (SerpApi)
def search_web(query):
    try:
        url = "https://serpapi.com/search"
        params = {"engine": "google", "q": query, "hl": "ko", "gl": "kr", "api_key": st.secrets["SERP_API_KEY"]}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            results = response.json()
            search_snippets = []
            for result in results.get("organic_results", [])[:3]:
                search_snippets.append(f"🔗 제목: {result.get('title')}\n내용: {result.get('snippet')}\n")
            return json.dumps({"search_results": search_snippets}, ensure_
