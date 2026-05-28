
import os
import time
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
st.set_page_config(page_title="말랑 AI 비서", layout="wide")

# 🎨 정밀 레이트 CSS 주입 (아이콘 및 파일 업로더 깨짐 방지 버전)
st.markdown("""
    <style>
    /* 1. 전체 배경색: 밀크티 베이지 */
    .stApp {
        background-color: #F7F4EF !important;
    }
    /* 2. 사이드바 배경색: 시나몬 베이지 */
    [data-testid="stSidebar"] {
        background-color: #EFE9E1 !important;
    }
    
    /* 3. 대화 본문, 타이틀, 마크다운 텍스트 영역만 콕 집어서 딥 브라운 지정 */
    /* (div, span 전역 지정을 제거하여 아이콘 및 파일 업로더 컴포넌트 보호) */
    .stApp h1, .stApp h2, .stApp h3, .stApp label, .stApp caption {
        color: #4A3B32 !important;
        font-family: 'Malgun Gothic', sans-serif;
    }
    .stApp p, .stApp li, .stMarkdown p, [data-testid="stChatMessage"] p {
        color: #4A3B32 !important;
        font-family: 'Malgun Gothic', sans-serif;
    }
    
    /* 4. 버튼 스타일: 둥글둥글하고 귀엽게 */
    div.stButton > button {
        border-radius: 20px !important;
        background-color: #D9C3B0 !important;
        color: #4A3B32 !important;
        border: 1px solid #C4A482 !important;
        font-weight: bold;
        transition: all 0.3s;
    }
    div.stButton > button:hover {
        background-color: #C4A482 !important;
        color: white !important;
        transform: scale(1.03);
    }
    
    /* 5. 하단 채팅 입력창 스타일 정렬 */
    .stChatInputContainer textarea {
        color: #4A3B32 !important;
    }
    .stChatInputContainer {
        border-radius: 15px !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🧸 말랑말랑 Azure AI 비서")
st.caption("무엇이든 물어보세요! 파일 요약과 데이터 분석도 뚝딱 해냅니다.")

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

if "thread_id" not in st.session_state:
    thread = client.beta.threads.create()
    st.session_state.thread_id = thread.id

if "assistant_id" not in st.session_state:
    with st.spinner("🐻 비서 깨우는 중... 잠시만 기다려주세요"):
        assistant = client.beta.assistants.create(
            model="gpt-4o-mini-10ai034", 
            instructions=(
                "당신은 데이터 분석 및 파일 검색을 돕는 유능하고 친절한 비서입니다. 답변은 한국어로 친절하고 상냥하게 작성해주세요.\n\n"
                "⭐ [그래프 생성 시 필수 지침] ⭐\n"
                "1. 텍스트 영문화: 그래프 내의 모든 텍스트(Title, X-label, Y-label)는 무조건 영어(English)로만 작성하세요.\n"
                "2. X축 수치 설정: 1부터 100까지의 범위라면 `plt.xticks(range(0, 101, 10))`를 사용하여 10 단위로 촘촘하게 표시되도록 설정하세요.\n"
                "3. 그래프 크기는 `plt.figure(figsize=(10, 5))`로 설정하여 가독성을 높이세요."
            ),
            tools=[{"type": "code_interpreter"}, {"type": "file_search"}],
            tool_resources={
                "file_search": {"vector_store_ids": ["vs_VLR7NXPhY4H3pt1vbniuDuVr"]},
                "code_interpreter": {"file_ids": []}
            },
            temperature=1,
            top_p=1
        )
        st.session_state.assistant_id = assistant.id

# 📁 사이드바 구성 (파일 업로드 기능)
st.sidebar.header("📁 파일 첨부 및 요약")
uploaded_file = st.sidebar.file_uploader(
    "분석할 파일을 올려주세요", 
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

# 기존 대화 출력
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        for element in msg["elements"]:
            if element["type"] == "text":
                st.markdown(element["value"])
            elif element["type"] == "image":
                st.image(element["value"])

# 💬 입력 트리거 통합 처리
prompt_to_send = None

if user_input := st.chat_input("쿠키 한 입 먹으면서 대화해봐요..."):
    prompt_to_send = user_input
elif "trigger_prompt" in st.session_state:
    prompt_to_send = st.session_state.trigger_prompt
    del st.session_state.trigger_prompt

# 메시지 처리 및 비서 Run 구동
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
            while run.status in ['queued', 'in_progress', 'cancelling']:
                time.sleep(1)
                run = client.beta.threads.runs.retrieve(thread_id=st.session_state.thread_id, run_id=run.id)
        
        if run.status == 'completed':
            messages = client.beta.threads.messages.list(thread_id=st.session_state.thread_id)
            last_message = messages.data[0]
            
            current_elements = []
            for content_block in reversed(last_message.content):
                if content_block.type == 'text':
                    text_content = content_block.text.value
                    st.markdown(text_content)
                    current_elements.append({"type": "text", "value": text_content})
                
                elif content_block.type == 'image_file':
                    file_id = content_block.image_file.file_id
                    image_data = client.files.content(file_id).read()
                    st.image(image_data)
                    current_elements.append({"type": "image", "value": image_data})
            
            st.session_state.messages.append({
                "role": "assistant",
                "elements": current_elements
            })
            st.rerun()
        else:
            st.error(f"삐비빅... 오류가 났어요. 상태: {run.status}")
