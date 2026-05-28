import os
import json
import time
import requests
import streamlit as st
from openai import AzureOpenAI

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

# 🎨 정밀 레이트 CSS 주입 (디자인 보호 및 테마 셋팅)
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
    </style>
""", unsafe_allow_html=True)

st.title("🧸 말랑말랑 통합 AI 비서 (Full Spec)")
st.caption("외부 실시간 API 연동부터 파이썬 시각화, 사내 문서 정밀 탐색까지 모두 처리합니다.")

# 🛠️ [백엔드 함수 정의 1] 곱셈 연산
def getMultipliedValue(num1, num2):
    return json.dumps({"result": num1 * num2})

# 🛠️ [백엔드 함수 정의 2] 실시간 날씨 API (한글 예외 처리 포함)
def get_weather(location):
    try:
        location_map = {
            "용인시": "Yongin", "용인": "Yongin",
            "서울시": "Seoul", "서울": "Seoul",
            "인천": "Incheon", "부산": "Busan"
        }
        eng_location = location_map.get(location, location)
        url = f"https://wttr.in/{eng_location}?format=j1"
        response = requests.get(url, headers={"User-Agent": "curl"}, timeout=10)
        
        if response.status_code == 200:
            current = response.json()["current_condition"][0]
            return json.dumps({
                "location": location,
                "temp_c": current["temp_C"],
                "condition": current["weatherDesc"][0]["value"],
                "humidity": f"{current['humidity']}%"
            }, ensure_ascii=False)
        return json.dumps({"error": "Weather API failed"})
    except Exception as e:
        return json.dumps({"error": str(e)})

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

if "thread_id" not in st.session_state:
    thread = client.beta.threads.create()
    st.session_state.thread_id = thread.id

# 어시스턴트 생성 시 테스트 완료한 모든 툴셋 탑재
if "assistant_id" not in st.session_state:
    with st.spinner("🐻 만능 비서 툴셋 장착 중... 잠시만 기다려주세요"):
        assistant = client.beta.assistants.create(
            model="gpt-4o-mini-10ai034", 
            instructions=(
                "당신은 사용자의 복합 질문에 답변하는 만능 데이터 분석 비서입니다. 답변은 한국어로 친절하고 상냥하게 작성해주세요.\n\n"
                "🚨 [최종 답변 작성 및 툴 사용 필수 엄수 지침] 🚨\n"
                "1. 사용자가 멀티 복합 질문을 던지면 절대로 생략하지 말고 모든 번호에 대한 답변을 결과물에 정렬하여 출력하세요.\n"
                "2. 날씨 질문의 `get_weather` 함수를 트리거할 때, location 인자값은 가능한 영문 도시명으로 추출하여 전달하세요.\n"
                "3. 문서 검색(LH 매입임대 등)은 `file_search` 도구를 활용해 깊숙이 조회하여 팩트 기반으로 답변하세요.\n\n"
                "📊 [그래프 생성 시 필수 에러 방지 지침] 📊\n"
                "- `code_interpreter`로 그래프를 그릴 때, 절대로 한글 세팅이나 외부 폰트 파일을 다루는 코드를 작성하지 마세요.\n"
                "- 모든 타이틀과 축 레이블은 100% 영문(English)으로만 작성하세요. (예: title='Histogram', xlabel='X', ylabel='Y')\n"
                "- 축 간격을 설정할 때는 `plt.xticks(range(0, 101, 10))`와 같이 표준적이고 에러 없는 문법만 사용하세요.\n"
                "- 그래프 크기는 `plt.figure(figsize=(10, 5))`로 조정하세요."
            ),
            tools=[
                {"type": "code_interpreter"}, 
                {"type": "file_search"},
                {
                    "type": "function",
                    "function": {
                        "name": "getMultipliedValue",
                        "description": "두 수를 받아 곱한 결과값을 반환",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "num1": {"type": "number"},
                                "num2": {"type": "number"}
                            },
                            "required": ["num1", "num2"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "특정 도시나 지역의 현재 실시간 날씨 정보 조회",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "location": {"type": "string", "description": "도시 이름 (예: Yongin, Seoul)"}
                            },
                            "required": ["location"]
                        }
                    }
                }
            ],
            tool_resources={
                "file_search": {"vector_store_ids": ["vs_VLR7NXPhY4H3pt1vbniuDuVr"]},
                "code_interpreter": {"file_ids": []}
            },
            temperature=0.7,
            top_p=1
        )
        st.session_state.assistant_id = assistant.id

# 📁 사이드바 구성 및 기능 안내 명시
st.sidebar.header("📁 데이터 창고 & 매뉴얼")

# ⭐ 사용법 및 탑재된 강력한 기능 안내 문구 추가
st.sidebar.markdown("""
### 🚀 사용 가능한 도구 목록
1. **🧮 초정밀 계산기**: 대형 숫자 곱셈 연산 기능
2. **🌤️ 실시간 날씨 조회**: 외부 wttr.in 동적 API 연동
3. **🔍 사내 문서 검색**: LH 매입임대 기준 등 탑재된 지식 탐색
4. **📊 파이썬 코드 실행**: 데이터 시각화 및 인라인 차트 빌드
---
""")

uploaded_file = st.sidebar.file_uploader(
    "새로운 파일 분석 및 임시 요약", 
    type=["txt", "pdf", "docx", "xlsx", "csv"]
)

file_id_to_attach = None
if uploaded_file is not None:
    if "last_file_name" not in st.session_state or st.session_state.last_file_name != uploaded_file.name:
        with st.sidebar.spinner("서버에 안전하게 파일을 올리는 중..."):
            openai_file = client.files.create(
                file=(uploaded_file.name, uploaded_file.getvalue()),
                purpose="assistants"
            )
            st.session_state.uploaded_file_id = openai_file.id
            st.session_state.last_file_name = uploaded_file.name
        st.sidebar.success("🎈 파일 업로드 성공!")
    
    file_id_to_attach = st.session_state.uploaded_file_id
    if st.sidebar.button("✨ 이 파일 초고속 요약하기"):
        st.session_state.trigger_prompt = f"첨부 파일 '{uploaded_file.name}'의 핵심 내용을 파악하기 쉽게 항목별로 요약해줘."

# 기존 저장된 대화 레이아웃 렌더링
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        for element in msg["elements"]:
            if element["type"] == "text":
                st.markdown(element["value"])
            elif element["type"] == "image":
                st.image(element["value"])

# 입력 제어 트리거 통합
prompt_to_send = None
if user_input := st.chat_input("쿠키 한 입 먹으면서 대화해봐요..."):
    prompt_to_send = user_input
elif "trigger_prompt" in st.session_state:
    prompt_to_send = st.session_state.trigger_prompt
    del st.session_state.trigger_prompt

# ⚡ [핵심 엔진] 메시지 처리 및 다단계 툴 콜 통합 구동
if prompt_to_send:
    st.chat_message("user").markdown(prompt_to_send)
    st.session_state.messages.append({
        "role": "user", 
        "elements": [{"type": "text", "value": prompt_to_send}]
    })
    
    attachments = []
    if file_id_to_attach:
        tool_type = "code_interpreter" if uploaded_file.name.endswith(('.csv', '.xlsx')) else "file_search"
        attachments.append({
            "file_id": file_id_to_attach,
            "tools": [{"type": tool_type}]
        })
    
    client.beta.threads.messages.create(
        thread_id=st.session_state.thread_id,
        role="user",
        content=prompt_to_send,
        attachments=attachments if attachments else None
    )
    
    run = client.beta.threads.runs.create(
        thread_id=st.session_state.thread_id,
        assistant_id=st.session_state.assistant_id
    )
    
    with st.chat_message("assistant"):
        with st.spinner("🍪 생각 주머니 돌리는 중..."):
            
            # 다단계 통합 상태 전개 루프
            while True:
                # 1단계: 기본 큐 및 인터프리터 연산 대기
                while run.status in ['queued', 'in_progress', 'cancelling']:
                    time.sleep(0.5)
                    run = client.beta.threads.runs.retrieve(thread_id=st.session_state.thread_id, run_id=run.id)
                
                # 분기 ①: 최종 완료 상태 도달 시 (화면 렌더링)
                if run.status == 'completed':
                    messages = client.beta.threads.messages.list(thread_id=st.session_state.thread_id)
                    last_message = messages.data[0]
                    
                    current_elements = []
                    # 정상 정렬 출력을 위해 reversed 사용
                    for content_block in reversed(last_message.content):
                        if content_block.type == 'text':
                            text_content = content_block.text.value
                            st.markdown(text_content)
                            current_elements.append({"type": "text", "value": text_content})
                        
                        elif content_block.type == 'image_file':
                            f_id = content_block.image_file.file_id
                            image_data = client.files.content(f_id).read()
                            st.image(image_data)
                            current_elements.append({"type": "image", "value": image_data})
                    
                    # 최종 누적 및 리프레시
                    st.session_state.messages.append({
                        "role": "assistant",
                        "elements": current_elements
                    })
                    break
                
                # 분기 ②: 백엔드 커스텀 파이썬 함수 트리거가 작동했을 때 (Requires Action)
                elif run.status == 'requires_action':
                    tool_calls = run.required_action.submit_tool_outputs.tool_calls
                    tool_outputs = []
                    
                    for tool_call in tool_calls:
                        f_name = tool_call.function.name
                        f_args = json.loads(tool_call.function.arguments)
                        
                        if f_name == "getMultipliedValue":
                            output = getMultipliedValue(num1=f_args.get("num1"), num2=f_args.get("num2"))
                        elif f_name == "get_weather":
                            output = get_weather(location=f_args.get("location"))
                        else:
                            output = json.dumps({"error": "Unknown function"})
                            
                        tool_outputs.append({"tool_call_id": tool_call.id, "output": output})
                    
                    # 획득한 백엔드 데이터를 어시스턴트에 환류 및 상위 와일문으로 회귀
                    run = client.beta.threads.runs.submit_tool_outputs(
                        thread_id=st.session_state.thread_id,
                        run_id=run.id,
                        tool_outputs=tool_outputs
                    )
                else:
                    st.error(f"삐비빅... 연산 중 오류가 났어요. 상태: {run.status}")
                    break
                    
            st.rerun()
