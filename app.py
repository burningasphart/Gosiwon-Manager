import streamlit as st
import pandas as pd
import plotly.express as px
import time
import re

st.set_page_config(page_title="고시원 누적 정산 시스템", layout="wide")

# --- [1] 세션 초기화 ---
if 'cat_df' not in st.session_state:
    st.session_state.cat_df = pd.DataFrame({
        "항목명": ["입실료", "공과금", "식품", "비품", "임대료", "보증금", "인건비", "시설비", "기타"],
        "연결구분": ["수익", "비용", "비용", "비용", "비용", "-", "비용", "비용", "비용"]
    })

if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame(columns=["연도", "월", "날짜", "내용", "용도", "구분", "금액", "비고"])

# --- [2] 보조 함수: 실제 데이터를 반영한 초정밀 분류 로직 ---
def smart_categorize(content, is_income):
    if is_income: return "입실료"
    
    text = str(content).upper() # 영문 대소문자 구분 없이 인식
    
    # 1. 보증금
    if '보증금' in text or '반환' in text: return "보증금"
    
    # 2. 공과금 (인터넷, 세무, 보험 등 대폭 보강)
    if any(k in text for k in ['전기', '수도', '예스코', '가스', '한전', '공과금', 'SKB', 'SK인터넷', 'KT', '인터넷', '전화', '세무', '부가세', '삼성화재', 'NH손보', 'ETAX', '대출']): 
        return "공과금"
    
    # 3. 식품 (실제 구매 품목 반영)
    if any(k in text for k in ['쌀', '라면', '사리면', '우유', '커피', '식료', '햇반', '오뚜기', '진라면', '신라면', '포카리', '하늘보리', '바나나', '고구마']): 
        return "식품"
    
    # 4. 비품 (다이소 및 소모품 보강)
    if any(k in text for k in ['다이소', '아성다', '비품', '세제', '비누', '휴지', '점보롤', '타월', '세탁', '봉투', '쓰레기', '매트리스', '건전지', '형광등', '샤워', '뚫어뻥', '프린트']): 
        return "비품"
    
    # 5. 시설비 (수리비 등)
    if any(k in text for k in ['수리', '냉장고', '에어컨', '도어락', '보일러']): 
        return "시설비"
    
    # 6. 임대료 및 인건비
    if '임대료' in text or '월세' in text: return "임대료"
    if any(k in text for k in ['인건비', '급여', '알바', '이명희']): return "인건비" # 실제 성함 반영
    
    return "기타"

# (기존 데이터 처리 및 대시보드 코드는 동일하게 유지됩니다)
# ... [이후 코드는 이전과 동일]
