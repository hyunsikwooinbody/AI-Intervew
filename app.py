import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import google.generativeai as genai
import time
import tempfile
import os
import io
import PyPDF2
import docx
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs

# ==========================================
# 0. 페이지 기본 설정 
# ==========================================
st.set_page_config(
    page_title="인터뷰 기획 자동화 시스템", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# 세션 상태 초기화 (1단계 결과를 개별적으로 저장하고 2단계로 넘기기 위함)
if 'edited_questions' not in st.session_state:
    st.session_state['edited_questions'] = {}

# ==========================================
# 1. 보조 함수들 (웹 크롤링 & 문서 추출 & AI 수정)
# ==========================================
def extract_text_from_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup.get_text(separator=' ', strip=True)[:3000] 
    except Exception:
        return f"[링크 읽기 실패: {url}]"

def process_input_text(text):
    urls = re.findall(r'(https?://[^\s]+)', text)
    processed_text = text
    for url in urls:
        scraped_content = extract_text_from_url(url)
        processed_text += f"\n\n[웹사이트 '{url}' 스크랩 내용]\n{scraped_content}"
    return processed_text

def extract_text_from_file(uploaded_file):
    text = ""
    try:
        if uploaded_file.name.endswith('.pdf'):
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        elif uploaded_file.name.endswith('.docx'):
            doc = docx.Document(uploaded_file)
            for para in doc.paragraphs:
                text += para.text + "\n"
        elif uploaded_file.name.endswith('.txt'):
            text = uploaded_file.read().decode('utf-8')
    except Exception as e:
        return f"[문서 읽기 실패: {uploaded_file.name}]"
    return text

def get_youtube_video_id(url):
    query = urlparse(url)
    if query.hostname == 'youtu.be': return query.path[1:]
    if query.hostname in ('www.youtube.com', 'youtube.com'):
        if query.path == '/watch': return parse_qs(query.query)['v'][0]
        if query.path[:7] == '/embed/': return query.path.split('/')[2]
        if query.path[:3] == '/v/': return query.path.split('/')[2]
    return None

def extract_youtube_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko'])
        text = " ".join([t['text'] for t in transcript_list])
        return text
    except Exception as e:
        return None

# 개별 질문을 AI가 재수정해주는 함수
def rewrite_question_with_ai(api_key, original_question, user_request):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"""
        당신은 베테랑 인터뷰 기획자입니다.
        아래의 기존 인터뷰 질문을 사용자의 요청에 맞게 완벽하게 수정해 주세요.
        
        [기존 질문]
        {original_question}
        
        [사용자 요청]
        {user_request}
        
        [규칙]
        반드시 수정된 '질문 텍스트'만 출력하세요. 인사말, 부가 설명, 마크다운 기호는 절대 넣지 마세요.
        """
        response = model.generate_content(prompt)
        
        # AI가 빈 값을 반환했을 때의 에러 방지
        if response.text:
            return response.text.strip()
        else:
            return "[AI 응답 오류: 생성된 텍스트가 없습니다. 요청을 조금 바꿔서 다시 시도해 주세요.]"
    except Exception as e:
        return f"[AI 통신 오류: {e}]"

# ==========================================
# 2. UI 및 메인 화면 구성
# ==========================================
st.title("🎬 인터뷰 기획 자동화 시스템")

with st.sidebar:
    st.header("🔑 API 설정")
    api_key = st.text_input("Google Gemini API Key를 입력하세요", type="password")
    st.markdown("*테스트를 위해 본인의 Google AI Studio API 키가 필요합니다.*")

tab1, tab2 = st.tabs(["📝 1단계: 질문지 생성 및 편집", "🎞️ 2단계: 스토리보드(20컷) 생성"])

# ------------------------------------------
# [탭 1] 인터뷰 질문 생성 및 개별 편집 영역
# ------------------------------------------
with tab1:
    col1, col2 = st.columns([1, 1.5])

    with col1:
        st.subheader("📝 인터뷰 대상자 정보 입력")
        person_name = st.text_input("👤 인터뷰이 이름")
        job = st.text_input("💼 직무 및 타이틀")
        
        # 1. 파일 업로드 기능 추가
        uploaded_docs = st.file_uploader("📂 우수 레퍼런스 및 참고 문서 (PDF, Word, TXT)", type=['pdf', 'docx', 'txt'], accept_multiple_files=True)
        
        ref_text = st.text_area("📰 핵심 임상 이력 및 참고 링크 (URL 포함 가능)", height=100)
        
        st.write("")
        generate_btn = st.button("🚀 인터뷰 질문 생성", use_container_width=True)

    with col2:
        st.subheader("🤖 인터뷰 질문 자동 생성기")
        
        if generate_btn:
            if not api_key:
                st.error("왼쪽 메뉴( > )를 열어 Google Gemini API Key를 먼저 입력해 주세요.")
            else:
                with st.spinner("자료와 문서를 분석하여 질문을 생성 중입니다..."):
                    try:
                        # 텍스트 + 업로드된 문서 합치기
                        docs_context = ""
                        if uploaded_docs:
                            for f in uploaded_docs:
                                docs_context += f"\n\n[업로드 문서 '{f.name}' 내용]\n{extract_text_from_file(f)}"
                        
                        final_context = process_input_text(ref_text) + docs_context
                        
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        
                        system_prompt = f"""
                        당신은 글로벌 헬스케어 기업 '인바디(InBody)'의 B2B 마케팅 인터뷰 전문 기획자입니다.
                        대상자: '{person_name}', 직무: '{job}'
                        이 인터뷰의 목적은 원장님(대표님)의 운영 노하우를 존중하며, 인바디(BWA 등) 활용 우수 사례를 뽑아내는 것입니다.

                        [🚨 필수 규칙]
                        1. 직무({job}) 맞춤 질문: 양방은 '표준 진료/모니터링 데이터', 한방은 '치료법과의 시너지', 피트니스는 '회원 동기부여'에 초점.
                        2. 만약 제공된 [참고자료]에 '기존 우수 인터뷰 답변지' 같은 문서 내용이 있다면, 해당 문서의 **질문 형식, 톤앤매너, 질문의 깊이를 철저하게 벤치마킹하여 현재 대상자에게 적용**하세요.
                        3. 절반 이상은 자사 장비(인바디) 도입 이유 및 활용 노하우와 연결하세요.

                        [📋 출력 구조 (헤딩 유지)]
                        **자기소개** (1~2개)
                        **Why InBody & How InBody** (3~4개)
                        **{person_name} X InBody** (2~3개)
                        **With InBody** (1~2개)

                        [참고자료 및 업로드 문서]
                        {final_context}
                        """
                        
                        response = model.generate_content(system_prompt)
                        # AI 결과를 줄 단위로 쪼개서 세션 딕셔너리에 저장
                        raw_lines = response.text.split('\n')
                        st.session_state['edited_questions'] = {i: line for i, line in enumerate(raw_lines)}
                        st.rerun() # 화면 새로고침하여 아래 편집기 UI 출력
                                
                    except Exception as e:
                        st.error(f"API 에러가 발생했습니다: {e}")

        # --- 개별 질문 편집 UI 출력부 ---
        if st.session_state['edited_questions']:
            st.success("✨ 질문지 생성이 완료되었습니다! (마음에 안 드는 질문은 개별 수정이 가능합니다)")
            st.divider()
            
            for i, line in st.session_state['edited_questions'].items():
                if line.startswith('**'):
                    # 카테고리 제목
                    st.markdown(f"#### {line.replace('**', '')}")
                elif line.strip():
                    # 개별 질문 단위
                    with st.container():
                        st.markdown(f"{line}")
                        
                        # 버튼 배치
                        btn_col1, btn_col2, btn_col3 = st.columns([1.5, 2.5, 6])
                        with btn_col2:
                            if st.button("🤖 질문 재생성", key=f"btn_ai_{i}"):
                                st.session_state[f"mode_{i}"] = "ai"
                        with btn_col2:
                            if st.button("🤖 질문 변경 AI 프롬프트 작성", key=f"btn_ai_{i}"):
                                st.session_state[f"mode_{i}"] = "ai"
                                
                        # 편집 모드 활성화 시
                        current_mode = st.session_state.get(f"mode_{i}")
                        if current_mode == "manual":
                            new_text = st.text_area("직접 수정", value=line, key=f"text_manual_{i}", label_visibility="collapsed")
                            if st.button("✅ 저장", key=f"save_manual_{i}"):
                                st.session_state['edited_questions'][i] = new_text
                                st.session_state[f"mode_{i}"] = None
                                st.rerun()
                                
                        elif current_mode == "ai":
                            ai_req = st.text_input("AI에게 수정 요청", placeholder="예: 조금 더 원장님을 띄워주는 부드러운 말투로 바꿔줘", key=f"text_ai_{i}")
                            if st.button("✨ AI 재생성", key=f"save_ai_{i}"):
                                if not api_key:
                                    st.error("API 키를 먼저 입력하세요.")
                                else:
                                    with st.spinner("AI가 질문을 수정 중입니다..."):
                                        new_q = rewrite_question_with_ai(api_key, line, ai_req)
                                        st.session_state['edited_questions'][i] = new_q
                                        st.session_state[f"mode_{i}"] = None
                                        st.rerun()
                        st.markdown("---")

# ------------------------------------------
# [탭 2] 스토리보드 생성 영역 
# ------------------------------------------
with tab2:
    st.subheader("🎞️ 영상 분석 및 20컷 스토리보드 생성")
    
    # 1단계에서 수정 완료된 최종 질문들을 하나로 합치기
    final_questions_for_sb = "\n".join([q for q in st.session_state['edited_questions'].values() if q.strip()])

    if not final_questions_for_sb:
        st.warning("⚠️ 1단계 탭에서 먼저 '인터뷰 질문'을 생성해 주세요!")
    else:
        video_source = st.radio("영상 소스 선택", ["🔗 유튜브 링크 입력", "📁 영상 파일 업로드 (mp4 등)"])
        
        video_context = ""
        sb_generate_btn = False
        
        if video_source == "🔗 유튜브 링크 입력":
            youtube_url = st.text_input("유튜브 영상 링크(URL)를 붙여넣으세요")
            sb_generate_btn = st.button("🎬 유튜브 기반 스토리보드 생성", use_container_width=True)
            
            if sb_generate_btn and youtube_url:
                with st.spinner("유튜브 대본을 추출하고 있습니다..."):
                    vid_id = get_youtube_video_id(youtube_url)
                    if vid_id:
                        transcript = extract_youtube_transcript(vid_id)
                        if transcript:
                            video_context = f"[유튜브 영상 대본 내용]\n{transcript}"
                        else:
                            st.error("대본을 추출할 수 없는 영상입니다.")
                            sb_generate_btn = False
                    else:
                        st.error("올바른 유튜브 링크가 아닙니다.")
                        sb_generate_btn = False

        else:
            uploaded_vid = st.file_uploader("영상 파일을 업로드하세요 (최대 200MB 권장)", type=['mp4', 'mov', 'avi'])
            sb_generate_btn = st.button("🎬 업로드 영상 기반 스토리보드 생성", use_container_width=True)
            
            if sb_generate_btn and uploaded_vid:
                with st.spinner("영상을 서버로 업로드 및 분석 중입니다. (수 분 소요)..."):
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
                        tmp.write(uploaded_vid.read())
                        tmp_path = tmp.name
                    
                    try:
                        genai.configure(api_key=api_key)
                        video_file = genai.upload_file(path=tmp_path)
                        while video_file.state.name == "PROCESSING":
                            time.sleep(2)
                            video_file = genai.get_file(video_file.name)
                        video_context = video_file
                    except Exception as e:
                        st.error(f"영상 업로드 실패: {e}")
                        sb_generate_btn = False
                    finally:
                        os.unlink(tmp_path)

        if sb_generate_btn and video_context:
            with st.spinner("영상을 분석하여 스토리보드를 구성 중입니다..."):
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    
                    # 💡 변경된(수정된) 최종 질문이 스토리보드 프롬프트로 들어감
                    storyboard_prompt = f"""
                    당신은 베테랑 영상 PD입니다.
                    앞서 기획된 [최종 인터뷰 질문]과 제공된 [영상 데이터/대본]을 완벽하게 매칭하여 **스토리보드(총 20컷 내외)**를 구성하세요.

                    [최종 인터뷰 질문 내용]
                    {final_questions_for_sb}

                    [🚨 필수 규칙]
                    1. 20컷 내외로 구성 (도입, 답변, 아웃트로 포함).
                    2. 위 질문의 흐름과 순서에 맞춰서 영상을 배치할 것.
                    3. 마크다운 표 형식 (컷 번호 / 화면 구성 / 내용 요약 / 매칭 질문 번호)으로 깔끔하게 출력할 것.
                    """
                    
                    if isinstance(video_context, str):
                        response = model.generate_content([storyboard_prompt, video_context])
                    else:
                        response = model.generate_content([storyboard_prompt, video_context])
                        genai.delete_file(video_context.name)
                    
                    st.success("✨ 스토리보드 구성이 완료되었습니다!")
                    st.markdown(response.text)

                except Exception as e:
                    st.error(f"스토리보드 생성 중 에러가 발생했습니다: {e}")
