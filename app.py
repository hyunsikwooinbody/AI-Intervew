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
                    당신은 글로벌 헬스케어 기업 '인바디(InBody)'의 B2B 마케팅 인터뷰 전문 기획자입니다.
                    대상자의 이름은 '{person_name}', 직무는 '{job}'입니다.
                    이 인터뷰의 목적은 원장님(또는 대표님)의 운영 노하우를 깊이 존중하며 칭찬하고, 인바디(특히 BWA 장비)를 어떻게 훌륭하게 활용하고 있는지 우수 사례를 뽑아내는 것입니다.

                    아래 제공되는 [참고자료 및 크롤링 데이터]를 완벽하게 숙지한 뒤, 다음 섹션 구조에 맞춰 인터뷰 질문을 작성하세요.

                    [🚨 필수 규칙 - 반드시 지킬 것]
                    1. 심기 경호 및 자랑 유도: 지역 경쟁, 매출 하락, 부정적인 이슈 등 심기를 건드릴 수 있는 질문은 절대 금지합니다. 철학, 전문성, 공간의 우수성을 마음껏 자랑할 수 있도록 판을 깔아주는 정중한 질문을 하세요.
                    2. 자연스러운 대화체(구어체) 사용: "~하신 특별한 계기가 있으실까요?", "~인지 궁금합니다", "~소개해 주실 수 있을까요?" 등 정중하고 예의 바른 방송 인터뷰어의 말투를 사용하세요.
                    3. 직무({job}) 분과에 따른 섬세한 맞춤형 질문 (매우 중요):
                       - 서양의학 전문의(내과, 신장내과, 가정의학과 등): '독자적인 치료법'이라는 표현을 절대 쓰지 마세요. 대신 해당 분과의 표준 진료(만성질환, 혈액투석, 부종 관리 등)에서 BWA/인바디 데이터가 임상적으로 어떤 도움을 주는지 묻는 데 집중하세요.
                       - 한의사: '원장님만의 고유한 치료법(침, 추나, 한약 등)'과 체수분/체성분 분석 결과지를 어떻게 접목해 시너지를 내는지 질문하세요.
                       - 피트니스/필라테스 대표: 환자나 진료라는 단어 대신 '회원, 수업, PT 상담'이라는 단어를 쓰고, 회원들의 동기부여나 운동 방향 설정에 인바디를 어떻게 활용하는지 묻는 데 집중하세요.
                    4. 인바디(BWA) 장비 연계: 전체 질문의 절반 이상은 자사 장비의 도입 이유, 활용 노하우, 환자(회원)의 긍정적 반응 등과 연결되어야 합니다.

                    [📋 출력 구조 (이 카테고리 헤딩을 그대로 출력하고 아래에 번호를 매겨 질문을 작성할 것)]
                    
                    **자기소개**
                    (대상자 소개 및 병원/센터 자랑을 유도하는 질문 1~2개)

                    **Why InBody & How InBody**
                    ({job}의 특성에 맞춘 장비 도입 기준, 장비 활용 노하우, 결과지 설명 팁, 기억에 남는 긍정적 사례 질문 3~4개)

                    **{person_name} X InBody**
                    (제공된 [참고자료]의 구체적인 사실(이력, 슬로건 등)과 인바디 활용의 시너지를 묻는 초개인화 질문 2~3개)

                    **With InBody**
                    (직무 철학, 향후 목표, 인바디에 바라는 점 등 마무리 질문 1~2개)

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
