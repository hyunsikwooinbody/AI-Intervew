import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import google.generativeai as genai
import time
import tempfile
import os
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs

# ==========================================
# 0. 페이지 기본 설정 (사이드바 숨김 처리 포함)
# ==========================================
st.set_page_config(
    page_title="인터뷰 기획 자동화 시스템", 
    layout="wide", 
    initial_sidebar_state="collapsed" # API 사이드바 기본 숨김
)

# 세션 상태 초기화 (1단계 결과를 2단계로 넘기기 위함)
if 'generated_questions' not in st.session_state:
    st.session_state['generated_questions'] = ""

# ==========================================
# 1. 보조 함수들 (웹 크롤링 & 유튜브 스크립트 추출)
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

# ==========================================
# 2. UI 및 메인 화면 구성
# ==========================================
st.title("🎬 인터뷰 기획 자동화 시스템")
# 설명 텍스트 제거 완료

# 사이드바 (API 키 설정)
with st.sidebar:
    st.header("🔑 API 설정")
    api_key = st.text_input("Google Gemini API Key를 입력하세요", type="password")
    st.markdown("*테스트를 위해 본인의 Google AI Studio API 키가 필요합니다.*")

# 탭(Tab)으로 1단계, 2단계 분리
tab1, tab2 = st.tabs(["📝 1단계: 질문지 생성", "🎞️ 2단계: 스토리보드(20컷) 생성"])

# ------------------------------------------
# [탭 1] 인터뷰 질문 생성 영역
# ------------------------------------------
with tab1:
    col1, col2 = st.columns([1, 1.5])

    with col1:
        st.subheader("📝 인터뷰 대상자 정보 입력")
        person_name = st.text_input("👤 인터뷰이 이름", "예: 김도윤 원장")
        job = st.text_input("💼 직무 및 타이틀", "예: 신장내과 전문의")
        ref_text = st.text_area("📰 핵심 임상 이력 및 참고 자료 (URL 링크 포함 가능)", height=150)
        mood = st.selectbox("영상 분위기", ["전문적이고 날카로운 톤", "따뜻하고 공감하는 톤", "빠르고 트렌디한 숏폼 톤"])
        
        generate_btn = st.button("🚀 인터뷰 질문 생성", use_container_width=True)

    with col2:
        st.subheader("🤖 인터뷰 질문 자동 생성기")
        
        if generate_btn:
            if not api_key:
                st.error("왼쪽 메뉴( > )를 열어 Google Gemini API Key를 먼저 입력해 주세요.")
            else:
                with st.spinner("자료를 분석하여 질문을 생성 중입니다..."):
                    try:
                        final_context = process_input_text(ref_text)
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        
                        system_prompt = f"""
                        당신은 글로벌 헬스케어 기업 '인바디(InBody)'의 B2B 마케팅 인터뷰 전문 기획자입니다.
                        대상자: '{person_name}', 직무: '{job}'
                        이 인터뷰의 목적은 원장님(대표님)의 운영 노하우를 존중하며, 인바디(BWA 등) 활용 우수 사례를 뽑아내는 것입니다.

                        [🚨 필수 규칙]
                        1. 지역 경쟁, 매출 등 심기를 건드릴 질문 절대 금지. 자랑을 유도하는 정중한 대화체 사용.
                        2. 직무({job}) 맞춤 질문: 양방은 '표준 진료/모니터링 데이터', 한방은 '원장님 고유 치료법과의 시너지', 피트니스는 '회원 동기부여'에 초점.
                        3. 절반 이상은 자사 장비(인바디) 도입 이유 및 활용 노하우와 연결.

                        [📋 출력 구조 (헤딩 유지)]
                        **자기소개** (1~2개)
                        **Why InBody & How InBody** (3~4개)
                        **{person_name} X InBody** (2~3개)
                        **With InBody** (1~2개)

                        [참고자료]
                        {final_context}
                        """
                        
                        response = model.generate_content(system_prompt)
                        st.session_state['generated_questions'] = response.text # 2단계를 위해 저장
                        
                        st.success("✨ 질문지 생성이 완료되었습니다! (이제 2단계 탭으로 이동해 보세요)")
                        st.markdown(st.session_state['generated_questions'])
                                
                    except Exception as e:
                        st.error(f"API 에러가 발생했습니다: {e}")

# ------------------------------------------
# [탭 2] 스토리보드 생성 영역 (유튜브/영상 분석)
# ------------------------------------------
with tab2:
    st.subheader("🎞️ 영상 분석 및 20컷 스토리보드 생성")
    st.markdown("1단계에서 생성된 질문을 바탕으로, 업로드한 영상(또는 유튜브)의 컷을 분류하고 스토리보드를 짭니다.")

    if not st.session_state['generated_questions']:
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
                            st.error("대본을 추출할 수 없는 영상입니다. (자막이 없는 영상일 수 있습니다)")
                            sb_generate_btn = False
                    else:
                        st.error("올바른 유튜브 링크가 아닙니다.")
                        sb_generate_btn = False

        else:
            uploaded_file = st.file_uploader("영상 파일을 업로드하세요 (최대 200MB 권장)", type=['mp4', 'mov', 'avi'])
            sb_generate_btn = st.button("🎬 업로드 영상 기반 스토리보드 생성", use_container_width=True)
            
            if sb_generate_btn and uploaded_file:
                with st.spinner("영상을 구글 AI 서버로 업로드 및 분석 중입니다. (파일 크기에 따라 수 분 소요)..."):
                    # 임시 파일로 저장 후 Gemini API로 업로드
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
                        tmp.write(uploaded_file.read())
                        tmp_path = tmp.name
                    
                    try:
                        genai.configure(api_key=api_key)
                        video_file = genai.upload_file(path=tmp_path)
                        # 영상 처리가 끝날 때까지 대기
                        while video_file.state.name == "PROCESSING":
                            time.sleep(2)
                            video_file = genai.get_file(video_file.name)
                        
                        video_context = video_file
                    except Exception as e:
                        st.error(f"영상 업로드 실패: {e}")
                        sb_generate_btn = False
                    finally:
                        os.unlink(tmp_path) # 임시 파일 삭제

        # 스토리보드 생성 실행
        if sb_generate_btn and video_context:
            with st.spinner("영상을 분석하여 20컷 스토리보드를 구성 중입니다..."):
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    
                    storyboard_prompt = f"""
                    당신은 베테랑 영상 PD이자 스토리보드 기획자입니다.
                    앞서 기획된 [인터뷰 질문]과 아래 제공된 [영상 데이터/대본]을 완벽하게 매칭하여, 최종 영상 편집을 위한 **스토리보드(총 20컷 내외)**를 구성해 주세요.

                    [인터뷰 질문 내용]
                    {st.session_state['generated_questions']}

                    [🚨 필수 작성 규칙]
                    1. 반드시 20컷 내외로 구성할 것 (도입부, 각 질문에 대한 답변, 마무리 아웃트로 포함).
                    2. 앞서 기획된 [인터뷰 질문]의 흐름과 순서에 맞춰서, 영상의 내용을 적절히 배치하고 컷을 나눌 것.
                    3. 각 컷마다 [컷 번호 / 화면 구성(예: 원장님 바스트 샷, 인서트 컷 등) / 핵심 자막 및 내용 요약 / 매칭된 질문 번호]를 명확히 작성할 것.
                    4. 가독성 좋게 마크다운 표(Table) 형식으로 깔끔하게 출력할 것.
                    """
                    
                    # 텍스트(유튜브)냐 영상 객체(파일)냐에 따라 입력 방식 다름
                    if isinstance(video_context, str):
                        response = model.generate_content([storyboard_prompt, video_context])
                    else:
                        response = model.generate_content([storyboard_prompt, video_context])
                        genai.delete_file(video_context.name) # 분석 끝난 영상 서버에서 삭제
                    
                    st.success("✨ 영상 분석 및 20컷 스토리보드 구성이 완료되었습니다!")
                    st.markdown(response.text)

                except Exception as e:
                    st.error(f"스토리보드 생성 중 에러가 발생했습니다: {e}")
