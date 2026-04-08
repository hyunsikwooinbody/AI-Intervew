import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import google.generativeai as genai
import time

# ==========================================
# 1. 웹 크롤링 함수 (링크를 읽어오는 역할)
# ==========================================
def extract_text_from_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)
        return text[:3000] 
    except Exception as e:
        return f"[링크 읽기 실패: {url}]"

def process_input_text(text):
    urls = re.findall(r'(https?://[^\s]+)', text)
    processed_text = text
    
    for url in urls:
        st.toast(f"🔗 링크 분석 중: {url}")
        scraped_content = extract_text_from_url(url)
        processed_text += f"\n\n[웹사이트 '{url}' 스크랩 내용]\n{scraped_content}"
    
    return processed_text

# ==========================================
# 2. UI 및 메인 화면 구성
# ==========================================
st.set_page_config(page_title="AI 초개인화 기획 어시스턴트", layout="wide")

st.title("🎬 실전형 AI 초개인화 질문지 생성기 (구글 Gemini 버전)")
st.markdown("인물 정보와 **뉴스/블로그 링크**를 입력하면, 구글 AI가 직접 사이트를 읽고 분석하여 실제 질문을 생성합니다.")

# 보안을 위해 API 키를 사이드바에서 입력받음
with st.sidebar:
    st.header("🔑 API 설정")
    # 구글 API 키를 입력받도록 문구 수정
    api_key = st.text_input("Google Gemini API Key를 입력하세요", type="password")
    st.markdown("*테스트를 위해 본인의 Google AI Studio API 키가 필요합니다.*")

col1, col2 = st.columns([1, 1.5])

with col1:
    st.subheader("📝 인터뷰 대상자 정보 입력")
    person_name = st.text_input("👤 인터뷰이 이름", "예: 김도윤 원장")
    job = st.text_input("💼 직무 및 타이틀", "예: 신장내과 전문의")
    
    ref_text = st.text_area("📰 핵심 임상 이력 및 참고 자료 (URL 링크 포함 가능)", 
"""관련 뉴스 기사 링크나 블로그 주소(http://...)를 여기에 포함해서 적어주시면 AI가 접속해서 읽어옵니다.""", height=150)
    
    mood = st.selectbox("영상 분위기", ["전문적이고 날카로운 톤", "따뜻하고 공감하는 톤", "빠르고 트렌디한 숏폼 톤"])
    
    st.write("")
    generate_btn = st.button("🚀 실제 AI 기획안 생성", use_container_width=True)

with col2:
    st.subheader("🤖 AI 생성 결과 (Gemini 1.5 Flash API)")
    
    if generate_btn:
        if not api_key:
            st.error("앗! 왼쪽 사이드바에 Google Gemini API Key를 먼저 입력해 주세요.")
        else:
            with st.spinner("1단계: 입력하신 자료와 링크(URL)를 분석하고 있습니다..."):
                final_context = process_input_text(ref_text)
                
            with st.spinner("2단계: 구글 AI가 텍스트를 파악하여 딥다이브 질문을 생성 중입니다..."):
                try:
                    # 🌟 구글 Gemini API 셋팅
                    genai.configure(api_key=api_key)
                    # 가장 빠르고 가성비 좋은 최신 모델 적용
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    
                    system_prompt = f"""
                    당신은 10년 차 베테랑 방송 작가이자 인터뷰어입니다. 
                    대상자의 이름은 '{person_name}', 직무는 '{job}'입니다.
                    아래 제공되는 [참고자료 및 크롤링 데이터]를 완벽하게 숙지한 뒤, 대상자에게 던질 아주 날카롭고 딥다이브한 인터뷰 질문 5가지를 작성하세요.
                    영상의 톤앤매너는 '{mood}'에 맞춰야 합니다.
                    
                    [조건]
                    1. 흔하고 뻔한 질문은 절대 금지합니다. 제공된 자료의 구체적인 사실(기사 내용, 성과 등)을 직접 언급하며 질문하세요.
                    2. 반드시 '1. 질문내용' '2. 질문내용' 처럼 번호 매기기 형식으로만 출력하세요. 다른 군더더기 말은 하지 마세요.
                    
                    [참고자료 및 크롤링 데이터]
                    {final_context}
                    """
                    
                    # 🌟 구글 AI에게 전송 및 결과 받기
                    response = model.generate_content(system_prompt)
                    ai_result = response.text
                    
                    st.success("✨ 구글 AI 분석 및 질문지 생성이 완료되었습니다!")
                    st.markdown(f"### 💡 '{person_name}' 맞춤형 딥다이브 질문")
                    
                    questions = ai_result.split('\n')
                    for q in questions:
                        if q.strip(): 
                            st.info(q.strip())
                            
                except Exception as e:
                    st.error(f"API 통신 중 에러가 발생했습니다. API 키가 정확한지 확인해 주세요! (에러내용: {e})")
