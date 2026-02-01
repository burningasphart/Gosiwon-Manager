import streamlit as st
import pandas as pd
import plotly.express as px
import time
import re
import os

# [설정] 페이지 레이아웃 및 세션 안정화
st.set_page_config(page_title="율곡고시원 통합 관리 시스템", layout="wide")

# --- [1] 세션 데이터 및 설정 로드 ---
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

# --- [2] 핵심 기술: 행 튀어오름 방지 콜백 ---
def handle_master_edit():
    """데이터 편집 시 즉시 실행되어 행 위치를 고정하고 데이터를 동기화함"""
    if "master_editor" in st.session_state:
        edits = st.session_state["master_editor"]
        c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
        
        # 1. 수정된 셀 반영
        for row_idx, edit_dict in edits["edited_rows"].items():
            idx = st.session_state.master_df.index[row_idx]
            for col, val in edit_dict.items():
                st.session_state.master_df.at[idx, col] = val
                if col == "용도":
                    st.session_state.master_df.at[idx, "구분"] = c_map.get(val, "비용")
        
        # 2. 추가/삭제 반영
        for row in edits["added_rows"]:
            new_row = {col: "" for col in st.session_state.master_df.columns}
            new_row.update(row)
            if not new_row.get("용도"): new_row["용도"] = "기타"
            new_row["구분"] = c_map.get(new_row["용도"], "비용")
            st.session_state.master_df = pd.concat([st.session_state.master_df, pd.DataFrame([new_row])], ignore_index=True)
            
        if edits["deleted_rows"]:
            st.session_state.master_df = st.session_state.master_df.drop(st.session_state.master_df.index[edits["deleted_rows"]]).reset_index(drop=True)

# --- [3] 보조 함수 ---
def clean_amt(x):
    try:
        if pd.isna(x) or str(x).strip() == "": return 0
        s = "".join(filter(str.isdigit, str(x).split('.')[0]))
        return int(s) if s else 0
    except: return 0

def clean_date(date_val):
    try:
        d = str(date_val).strip()
        d = re.sub(r'[^0-9./-]', ' ', d).split()[0]
        d = d.replace('.', '-').replace('/', '-')
        parts = d.split('-')
        if len(parts) >= 3:
            return parts[0], parts[1].zfill(2), f"{parts[1].zfill(2)}/{parts[2].zfill(2)}"
        return time.strftime("%Y"), time.strftime("%m"), time.strftime("%m/%d")
    except: return time.strftime("%Y"), time.strftime("%m"), time.strftime("%m/%d")

def smart_categorize(content, is_income):
    if is_income: return "입실료"
    text = str(content).upper()
    if any(k in text for k in ['보증금', '반환', '퇴실']): return "보증금"
    if any(k in text for k in ['전기', '수도', '가스', '한전', '인터넷', '보험', '세무']): return "공과금"
    if any(k in text for k in ['쌀', '라면', '진라면', '햇반', '오뚜기']): return "식품"
    if any(k in text for k in ['다이소', '비품', '세제', '휴지', '건전지', '형광등']): return "비품"
    if '월세' in text or '임대료' in text: return "임대료"
    return "기타"

# --- [4] 메인 화면 및 사이드바 ---
st.title("🏠 율곡고시원 통합 정산 시스템")

# [사이드바 복구] 데이터 업로드 창
with st.sidebar:
    st.header("📂 데이터 통합")
    bank_file = st.file_uploader("우리은행 거래내역", type=['csv', 'xls', 'xlsx'])
    coupang_file = st.file_uploader("쿠팡 구매내역", type=['csv'])

    if st.button("📦 새 데이터 합치기"):
        if bank_file and coupang_file:
            try:
                c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
                # 은행 파일 처리
                if bank_file.name.endswith('.csv'):
                    try: b_df = pd.read_csv(bank_file, encoding='utf-8-sig')
                    except: b_df = pd.read_csv(bank_file, encoding='cp949')
                else:
                    try: b_df = max(pd.read_html(bank_file), key=len)
                    except: b_df = pd.read_excel(bank_file)
                
                h_idx = 0
                for i in range(min(20, len(b_df))):
                    if '거래일시' in "".join(b_df.iloc[i].astype(str)): h_idx = i; break
                b_df.columns = b_df.iloc[h_idx]; b_df = b_df.iloc[h_idx+1:].reset_index(drop=True)
                
                new_rows = []
                for _, r in b_df.iterrows():
                    if pd.isna(r.get('거래일시')): continue
                    y, m, d_d = clean_date(r.get('거래일시'))
                    vi, vo = clean_amt(r.get('맡기신금액', 0)), clean_amt(r.get('찾으신금액', 0))
                    content = (str(r.get('기재내용','')) + " " + str(r.get('적요',''))).replace('nan','').strip()
                    if "쿠팡" in content: continue
                    yd = smart_categorize(content, vi > 0)
                    new_rows.append({"연도":y,"월":m,"날짜":d_d,"내용":content,"용도":yd,"구분":c_map.get(yd,"비용"),"금액":vi if vi>0 else vo,"비고":str(r.get('적요',''))})
                
                # 쿠팡 파일 처리
                c_df = pd.read_csv(coupang_file)
                for _, r in c_df.iterrows():
                    amt = clean_amt(r.get('총결제금액(원)', 0))
                    if amt > 0:
                        y, m, d_d = clean_date(r.get('주문일',''))
                        p_name = str(r.get('상품명',''))
                        yd = smart_categorize(p_name, False)
                        new_rows.append({"연도":y,"월":m,"날짜":d_d,"내용":p_name,"용도":yd,"구분":c_map.get(yd,"비용"),"금액":amt,"비고":"쿠팡구매"})
                
                if new_rows:
                    st.session_state.master_df = pd.concat([st.session_state.master_df, pd.DataFrame(new_rows)]).drop_duplicates(subset=['날짜','내용','금액'], keep='first').reset_index(drop=True)
                    st.success("통합 완료!")
                    st.rerun()
            except Exception as e: st.error(f"오류: {e}")
    
    st.markdown("---")
    st.download_button("📥 통합 장부 다운로드", st.session_state.master_df.to_csv(index=False).encode('utf-8-sig'), "율곡고시원_마스터.csv", "text/csv")

# 메인 탭
df = st.session_state.master_df
all_months = sorted(df['월'].unique()) if not df.empty else []
tabs = st.tabs(["📊 통합 리포트"] + [f"📅 {m}월 상세" for m in all_months] + ["📝 데이터 편집", "⚙️ 카테고리 설정"])

with tabs[-2]: # 데이터 편집
    st.subheader("📝 상세 데이터 편집")
    st.info("💡 수정 시 행 위치가 완벽히 고정됩니다.
