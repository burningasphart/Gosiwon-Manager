import streamlit as st
import pandas as pd
import plotly.express as px
import time
import re
import os

# [1] 페이지 설정
st.set_page_config(page_title="율곡고시원 정산 시스템", layout="wide")

# --- 데이터 로드 및 세션 초기화 ---
CAT_FILE = "cat_settings.csv"
if 'cat_df' not in st.session_state:
    if os.path.exists(CAT_FILE):
        st.session_state.cat_df = pd.read_csv(CAT_FILE)
    else:
        st.session_state.cat_df = pd.DataFrame({
            "항목명": ["입실료", "공과금", "식품", "비품", "임대료", "보증금", "인건비", "시설비", "기타"],
            "연결구분": ["수익", "비용", "비용", "비용", "비용", "-", "비용", "비용", "비용"]
        })

if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame(columns=["연도", "월", "날짜", "내용", "용도", "구분", "금액", "비고"])

# --- 보조 함수 ---
def clean_amt(x):
    try:
        s = "".join(filter(str.isdigit, str(x).split('.')[0]))
        return int(s) if s else 0
    except: return 0

def clean_date(date_val):
    try:
        d = str(date_val).strip().replace('.', '-').replace('/', '-')
        parts = d.split('-')
        if len(parts) >= 3: return parts[0], parts[1].zfill(2), f"{parts[1].zfill(2)}/{parts[2].zfill(2)}"
        return time.strftime("%Y"), time.strftime("%m"), time.strftime("%m/%d")
    except: return time.strftime("%Y"), time.strftime("%m"), time.strftime("%m/%d")

def smart_categorize(content, is_income):
    if is_income: return "입실료"
    text = str(content).upper()
    if any(k in text for k in ['보증금', '반환', '퇴실']): return "보증금"
    if any(k in text for k in ['전기', '수도', '가스', '한전', 'SKB', '인터넷', '보험', '세무']): return "공과금"
    if any(k in text for k in ['쌀', '라면', '햇반', '오뚜기']): return "식품"
    if any(k in text for k in ['다이소', '비품', '세제', '휴지', '건전지']): return "비품"
    if '월세' in text or '임대료' in text: return "임대료"
    return "기타"

# --- [2] 사이드바 (파일 업로드 및 통합 기능) ---
with st.sidebar:
    st.header("📂 데이터 통합")
    bank_f = st.file_uploader("우리은행 거래내역", type=['csv', 'xlsx', 'xls'])
    coupang_f = st.file_uploader("쿠팡 구매내역", type=['csv'])
    
    if st.button("📦 새 데이터 합치기"):
        if bank_f and coupang_f:
            try:
                c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
                if bank_f.name.endswith('.csv'): b_df = pd.read_csv(bank_f, encoding='cp949')
                else: b_df = pd.read_excel(bank_f)
                
                h_idx = 0
                for i in range(min(20, len(b_df))):
                    if '거래일시' in "".join(b_df.iloc[i].astype(str)): h_idx = i; break
                b_df.columns = b_df.iloc[h_idx]; b_df = b_df.iloc[h_idx+1:].reset_index(drop=True)
                
                new_rows = []
                for _, r in b_df.iterrows():
                    if pd.isna(r.get('거래일시')): continue
                    y, m, d_d = clean_date(r.get('거래일시'))
                    vi, vo = clean_amt(r.get('맡기신금액', 0)), clean_amt(r.get('찾으신금액', 0))
                    content = str(r.get('기재내용','')).strip()
                    yd = smart_categorize(content, vi > 0)
                    new_rows.append({"연도":y, "월":m, "날짜":d_d, "내용":content, "용도":yd, "구분":c_map.get(yd, "비용"), "금액":vi if vi>0 else vo, "비고":str(r.get('적요',''))})
                
                c_df = pd.read_csv(coupang_f)
                for _, r in c_df.iterrows():
                    amt = clean_amt(r.get('총결제금액(원)', 0))
                    if amt > 0:
                        y, m, d_d = clean_date(r.get('주문일',''))
                        p_name = str(r.get('상품명',''))
                        yd = smart_categorize(p_name, False)
                        new_rows.append({"연도":y, "월":m, "날짜":d_d, "내용":p_name, "용도":yd, "구분":c_map.get(yd, "비용"), "금액":amt, "비고":"쿠팡구매"})
                
                if new_rows:
                    st.session_state.master_df = pd.concat([st.session_state.master_df, pd.DataFrame(new_rows)]).drop_duplicates(subset=['날짜','내용','금액'], keep='first').reset_index(drop=True)
                    st.success("통합 성공!")
                    st.rerun()
            except Exception as e: st.error(f"오류: {e}")
    
    st.markdown("---")
    st.download_button("📥 통합 장부 다운로드", st.session_state.master_df.to_csv(index=False).encode('utf-8-sig'), "율곡고시원_장부.csv", "text/csv")

# --- [3] 메인 화면 ---
st.title("🏠 율곡고시원 통합 관리 시스템")
tabs = st.tabs(["📊 리포트", "📝 데이터 편집", "⚙️ 카테고리 설정"])

with tabs[1]: # 데이터 편집 탭
    st.subheader("📝 상세 데이터 편집")
    st.info("💡 용도를 수정해도 행이 튀어 오르지 않습니다. 수정을 마친 후 하단의 [저장] 버튼을 꼭 눌러주세요.")
    
    cat_list = st.session_state.cat_df["항목명"].tolist()
    
    # 튀어오름 방지를 위해 실시간
