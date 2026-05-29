import os
import json
import time
import requests
import traceback
import streamlit as st
from openai import AzureOpenAI
import warnings

# 경고 로그 무시 및 초기 환경설정
warnings.filterwarnings(action='ignore', category=DeprecationWarning)
st.set_page_config(page_title="말랑 만능 AI 비서", layout="wide")

# 1. API 안전 관리 정의
ENDPOINT = st.secrets["ENDPOINT"]
API_KEY = st.secrets["API_KEY"]

# 🎬 영화 데이터베이스(Azure AI Search) 용 비밀값 로드
SEARCH_ENDPOINT = st.secrets["SEARCH_ENDPOINT"]
SEARCH_KEY = st.secrets["SEARCH_KEY"]
SEARCH_INDEX = "rag-10ai034realmovie" 

client = AzureOpenAI(
    azure_endpoint=ENDPOINT,
    api_key=API_KEY,
    api_version="2024-05-01-preview"
)

# 🎨 테마 스타일시트 주입
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
    
    .custom-citation {
        background-color: #EAE3D8 !important; 
        padding: 12px !important; 
        border-left: 5px solid #C4A482 !important;
        border-radius: 6px !important; 
        margin-top: 15px !important; 
        font-size: 0.93rem !important; 
        color: #2B1E17 !important; 
        line-height: 1.6 !important;
        display: block !important;
    }
    .custom-citation b { color: #1A0F0A !important; }
    </style>
""", unsafe_allow_html=True)

st.title("🧸 말랑말랑 통합 AI 비서")
st.caption("외부 실시간 API 연동부터 파이썬 시각화, 문서 정밀 탐색까지 모두 처리합니다.")

# ==========================================
# 🛠️ 백엔드 연동 도구 기능정의 부문
# ==========================================

def getMultipliedValue(num1, num2):
    return json.dumps({"result": num1 * num2})

def get_weather(location):
    try:
        location_map = {
            "용인시": "Yongin", "용인": "Yongin", "서울시": "Seoul", "서울": "Seoul",
            "안양시": "Anyang", "안양": "Anyang", "인천": "Incheon", "부산": "Busan"
        }
        eng_location = location_map.get(location, location)
        url = f"https://wttr.in/{eng_location},KR?format=j1"
        response = requests.get(url, headers={"User-Agent": "curl"}, timeout=10)
        
        if response.status_code == 200:
            current = response.json()["current_condition"][0]
            return json.dumps({
                "location": location, "temp_c": current["temp_C"],
                "condition": current["weatherDesc"][0]["value"], "humidity": f"{current['humidity']}%"
            }, ensure_ascii=False)
        return json.dumps({"error": "Weather API failed"})
    except Exception as e:
        return json.dumps({"error": str(e)})

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
            return json.dumps({"search_results": search_snippets}, ensure_ascii=False)
        return json.dumps({"error": f"SerpApi returned status {response.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})

def search_movie_rag(query):
    """Azure AI Search 인덱스에서 순수 데이터와 사이테이션 원본을 정제하여 어시스턴트에 리턴합니다."""
    try:
        rag_completion = client.chat.completions.create(
            model="gpt-4o-mini-10ai034", 
            messages=[
                {"role": "system", "content": "사용자가 정보를 찾는 데 도움이 되는 AI 도우미입니다."},
                {"role": "user", "content": query}
            ],
            max_tokens=5000,
            temperature=0.7,
            extra_body={
              "data_sources": [{
                  "type": "azure_search",
                  "parameters": {
                    "endpoint": f"{SEARCH_ENDPOINT}",
                    "index_name": f"{SEARCH_INDEX}",
                    "semantic_configuration": "rag-10ai034realmovie-semantic-configuration",
                    "query_type": "semantic",
                    "fields_mapping": {}, 
                    "in_scope": True, 
                    "filter": None, 
                    "strictness": 3, 
                    "top_n_documents": 5,
                    "authentication": {"type": "api_key", "key": f"{SEARCH_KEY}"}
                  }
                }]
            }
        )
        
        answer_content = rag_completion.choices[0].message.content
        movie_citations = []
        
        message_extra = rag_completion.choices[0].message.model_extra
        if message_extra and 'context' in message_extra:
            raw_citations = message_extra['context'].get('citations', [])
            for idx, cit in enumerate(raw_citations, 1):
                title = cit.get('title') or cit.get('metadata_storage_name') or cit.get('filepath') or ''
                title = title.replace('.pdf', '').replace('.txt', '').strip()
                
                if not title:
                    title = f"영화 데이터베이스 검색 단락 (ID: {cit.get('chunk_id', idx)})"
                movie_citations.append(f"[{idx}] {title}")
                
        return json.dumps({
            "answer": answer_content,
            "movie_citations": movie_citations
        }, ensure_ascii=False)
        
    except Exception as e:
        error_msg = f"❌ [영화 RAG 시스템 내부 크래시 발생]\n\n원인: {str(e)}\n\n상세 추적 경로:\n{traceback.format_exc()}"
        return json.dumps({"error": error_msg}, ensure_ascii=False)

# ==========================================
# ⚙️ 세션 가두리 및 안정화 변수 세팅
# ==========================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "thread_id" not in st.session_state:
    st.session_state.thread_id = client.beta.threads.create().id

# 영화 출처 임시 저장을 위한 세션 상태 추가
if "temp_movie_citations" not in st.session_state:
    st.session_state.temp_movie_citations = None

if "assistant_id" not in st.session_state:
    with st.spinner("🐻 만능 비서 툴셋 장착 중... 잠시만 기다려주세요"):
        assistant = client.beta.assistants.create(
            model="gpt-4o-mini-10ai034", 
            instructions=(
                "당신은 사용자의 복합 질문에 답변하는 만능 데이터 분석 비서입니다. 답변은 한국어로 친절하고 상냥하게 작성해주세요.\n\n"
                "🚨 [최종 답변 작성 및 툴 사용 필수 엄수 지침] 🚨\n"
                "1. 사용자가 멀티 복합 질문을 던지면 절대로 생략하지 말고 모든 번호에 대한 답변을 결과물에 정렬하여 출력하세요.\n"
                "2. 날씨 질문의 `get_weather` 함수를 트리거할 때, location 인자값은 가능한 영문 도시명으로 추출하여 전달하세요.\n"
                "3. 문서 검색(LH 매입임대 등)은 `file_search` 도구를 활용해 깊숙이 조회하여 팩트 기반으로 답변하세요.\n"
                "4. 영화 추천 관련 검색 요청이 들어오면 반드시 `search_movie_rag` 함수를 호출하세요. "
                "그 결과 리턴되는 JSON 데이터 내의 `answer` 내용을 바탕으로 가공 없이 솔직하고 명확하게 답변 본문을 작성하세요."
            ),
            tools=[
                {"type": "code_interpreter"}, {"type": "file_search"},
                {"type": "function", "function": {"name": "getMultipliedValue", "description": "두 수의 곱셈 연산", "parameters": {"type": "object", "properties": {"num1": {"type": "number"}, "num2": {"type": "number"}}, "required": ["num1", "num2"]}}},
                {"type": "function", "function": {"name": "get_weather", "description": "실시간 도시 날씨 정보 조회", "parameters": {"type": "object", "properties": {"location": {"type": "string"}}, "required": ["location"]}}},
                {"type": "function", "function": {"name": "search_web", "description": "구글 최신 웹정보 검색 트랙 빌드", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
                {"type": "function", "function": {"name": "search_movie_rag", "description": "자체 전용 영화 데이터베이스 RAG 조회", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}}
            ],
            tool_resources={
                "file_search": {"vector_store_ids": ["vs_VLR7NXPhY4H3pt1vbniuDuVr"]}, "code_interpreter": {"file_ids": []}
            },
            temperature=0.7, top_p=1
        )
        st.session_state.assistant_id = assistant.id

# 📁 사이드바 가이드라인 빌드
st.sidebar.header("📁 데이터 창고 & 매뉴얼")
st.sidebar.markdown("""
### 🚀 사용 가능한 도구 목록
1. **🧮 초정밀 계산기**: 대형 숫자 곱셈 연산 기능
2. **🌤️ 실시간 날씨 조회**: 외부 wttr.in 동적 API 연동
3. **🔍 LH 매입임대 문서 검색**: LH 매입임대 관련 지식 탐색
4. **📊 파이썬 코드 실행**: 데이터 시각화 및 인라인 차트 빌드
5. **🌐 실시간 구글 웹 검색**: 최신 뉴스 및 웹 트렌드 실시간 검색 (SerpApi)
6. **🎬 전용 영화 데이터 RAG**: Azure AI Search 연동 맞춤형 영화 추천 및 조회
---
""")

uploaded_file = st.sidebar.file_uploader("새로운 파일 분석 및 임시 요약", type=["txt", "pdf", "docx", "xlsx", "csv"])

file_id_to_attach = None
if uploaded_file is not None:
    if "last_file_name" not in st.session_state or st.session_state.last_file_name != uploaded_file.name:
        with st.sidebar.spinner("서버에 안전하게 파일을 올리는 중..."):
            openai_file = client.files.create(file=(uploaded_file.name, uploaded_file.getvalue()), purpose="assistants")
            st.session_state.uploaded_file_id = openai_file.id
            st.session_state.last_file_name = uploaded_file.name
        st.sidebar.success("🎈 파일 업로드 성공!")
        
    file_id_to_attach = st.session_state.uploaded_file_id
    if st.sidebar.button("✨ 이 파일 초고속 요약하기"):
        st.session_state.trigger_prompt = f"첨부 파일 '{uploaded_file.name}'의 핵심 내용을 파악하기 쉽게 항목별로 요약해줘."

# 렌더링 파트 
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        for element in msg["elements"]:
            if element["type"] == "text":
                st.markdown(element["value"], unsafe_allow_html=True)
            elif element["type"] == "image":
                st.image(element["value"])

# 입력 제어 게이트웨이
prompt_to_send = None
if user_input := st.chat_input("쿠키 한 입 먹으면서 대화해봐요..."):
    prompt_to_send = user_input
elif "trigger_prompt" in st.session_state:
    prompt_to_send = st.session_state.trigger_prompt
    del st.session_state.trigger_prompt

# ==========================================
# ⚡ DYNAMIC RUNTIME EVENT LOOP
# ==========================================
if prompt_to_send:
    st.chat_message("user").markdown(prompt_to_send)
    st.session_state.messages.append({"role": "user", "elements": [{"type": "text", "value": prompt_to_send}]})
    
    attachments = []
    if file_id_to_attach:
        tool_type = "code_interpreter" if uploaded_file.name.endswith(('.csv', '.xlsx')) else "file_search"
        attachments.append({"file_id": file_id_to_attach, "tools": [{"type": tool_type}]})
    
    client.beta.threads.messages.create(
        thread_id=st.session_state.thread_id, role="user", content=prompt_to_send, attachments=attachments if attachments else None
    )
    
    run = client.beta.threads.runs.create(thread_id=st.session_state.thread_id, assistant_id=st.session_state.assistant_id)
    
    with st.chat_message("assistant"):
        with st.spinner("🍪 생각 주머니 돌리는 중..."):
            
            while True:
                while run.status in ['queued', 'in_progress', 'cancelling']:
                    time.sleep(0.5)
                    run = client.beta.threads.runs.retrieve(thread_id=st.session_state.thread_id, run_id=run.id)
                
                # 분기 ①: 최종 런(Run) 완료 수집 시 (영화 출처 순서 패치 완료)
                if run.status == 'completed':
                    messages = client.beta.threads.messages.list(thread_id=st.session_state.thread_id)
                    assistant_messages = [m for m in messages.data if m.role == 'assistant' and m.run_id == run.id]
                    
                    if assistant_messages:
                        last_message = assistant_messages[0]
                        current_elements = []
                        
                        for content_block in reversed(last_message.content):
                            if content_block.type == 'text':
                                text_content = content_block.text.value
                                annotations = getattr(content_block.text, 'annotations', [])
                                lh_citations = []
                                
                                # LH 문서 검색 주석 가공
                                for index, annotation in enumerate(annotations):
                                    text_content = text_content.replace(annotation.text, f' [{index + 1}]')
                                    if file_citation := getattr(annotation, 'file_citation', None):
                                        try:
                                            cited_file = client.files.retrieve(file_citation.file_id)
                                            lh_citations.append(f"[{index + 1}] {cited_file.filename}")
                                        except:
                                            lh_citations.append(f"[{index + 1}] 내부 참조 문서 (ID: {file_citation.file_id[:8]}...)")
                                            
                                # 1. AI 답변 본문 먼저 출력
                                st.markdown(text_content, unsafe_allow_html=True)
                                current_elements.append({"type": "text", "value": text_content})
                                
                                # 2. 만약 보관된 '영화 RAG 출처'가 있다면, 답변 본문 바로 다음에 렌더링하도록 유도
                                if st.session_state.temp_movie_citations:
                                    movie_citation_box = f"<div class='custom-citation'><b>🎬 영화 DB 참조 출처:</b><br>" + "<br>".join(st.session_state.temp_movie_citations) + "</div>"
                                    st.markdown(movie_citation_box, unsafe_allow_html=True)
                                    current_elements.append({"type": "text", "value": movie_citation_box})
                                    # 출력 완료 후 임시 보관함 비우기
                                    st.session_state.temp_movie_citations = None
                                
                                # 3. LH 출처 출력
                                if lh_citations:
                                    citation_box_html = f"<div class='custom-citation'><b>📄 LH 문서 검색 참조 출처:</b><br>" + "<br>".join(lh_citations) + "</div>"
                                    st.markdown(citation_box_html, unsafe_allow_html=True)
                                    current_elements.append({"type": "text", "value": citation_box_html})
                                    
                            elif content_block.type == 'image_file':
                                f_id = content_block.image_file.file_id
                                image_data = client.files.content(f_id).read()
                                st.image(image_data)
                                current_elements.append({"type": "image", "value": image_data})
                        
                        st.session_state.messages.append({"role": "assistant", "elements": current_elements})
                    break
                
                # 분기 ②: 중간 도구 함수 트리거 수령 시 (Requires Action)
                elif run.status == 'requires_action':
                    tool_calls = run.required_action.submit_tool_outputs.tool_calls
                    tool_outputs = []
                    
                    for tool_call in tool_calls:
                        f_name = tool_call.function.name
                        f_args = json.loads(tool_call.function.arguments)
                        
                        info_text = f"⚙️ **[만능 비서 내부 연산 가동]** `{f_name}` 함수를 실행하고 있습니다. (인자값: {f_args})"
                        st.info(info_text)
                        st.session_state.messages.append({
                            "role": "assistant", "elements": [{"type": "text", "value": info_text}]
                        })
                        st.toast(f"📡 {f_name} 호출됨", icon="🤖")
                        
                        if f_name == "getMultipliedValue":
                            output = getMultipliedValue(num1=f_args.get("num1"), num2=f_args.get("num2"))
                        elif f_name == "get_weather":
                            output = get_weather(location=f_args.get("location"))
                        elif f_name == "search_web":
                            output = search_web(query=f_args.get("query"))
                        elif f_name == "search_movie_rag":
                            output = search_movie_rag(query=f_args.get("query"))
                            
                            if "❌ [영화 RAG 시스템 내부 크래시 발생]" in output:
                                parsed_err = json.loads(output).get("error", "")
                                st.error(parsed_err)
                                st.session_state.messages.append({
                                    "role": "assistant", "elements": [{"type": "text", "value": f"```text\n{parsed_err}\n```"}]
                                })
                            else:
                                try:
                                    rag_data = json.loads(output)
                                    # 🌟 [패치 핵심]: 화면에 바로 출력하지 않고 세션 임시 스토리지에 출처 데이터를 고이 모셔둡니다.
                                    st.session_state.temp_movie_citations = rag_data.get("movie_citations", [])
                                    
                                    # 어시스턴트는 팩트 본문만 읽을 수 있도록 순수 대답 텍스트만 환류
                                    output = json.dumps({"search_result": rag_data.get("answer", "")}, ensure_ascii=False)
                                except:
                                    pass
                        else:
                            output = json.dumps({"error": "Unknown function"})
                            
                        tool_outputs.append({"tool_call_id": tool_call.id, "output": output})
                    
                    run = client.beta.threads.runs.submit_tool_outputs(
                        thread_id=st.session_state.thread_id, run_id=run.id, tool_outputs=tool_outputs
                    )
                else:
                    st.error(f"삐비빅... 연산 중 오류가 났어요. 상태: {run.status}")
                    break
                    
            st.rerun()
