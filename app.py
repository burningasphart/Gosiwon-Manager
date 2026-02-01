import streamlit as st
import pandas as pd
import plotly.express as px
import time
import re
import os

# [1] 페이지 설정 및 세션 초기화
st.set_page_config(page_title="율곡고시원 통합 관리 시스템", layout="wide")

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

# --- [2] 보조 함수 (날짜/금액 정제) ---
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
    if any(k in text for k in ['전기', '수도', '가스', '한전', '인터넷', '보험', '세무']): return "공과금"
    if any(k in text for k in ['쌀', '라면', '햇반', '오뚜기']): return "식품"
    if any(k in text for k in ['다이소', '비품', '세제', '휴지', '건전지']): return "비품"
    if '월세' in text or '임대료' in text: return "임대료"
    return "기타"

# --- [3] 사이드바 (파일 업로드 기능 복구) ---
with st.sidebar:
    st.header("📂 데이터 통합")
    bank_f = st.file_uploader("우리은행 거래내역 (CSV/Excel)", type=['csv', 'xlsx', 'xls'])
    coupang_f = st.file_uploader("쿠팡 구매내역 (CSV)", type=['csv'])
    
    if st.button("📦 새 데이터 합치기"):
        if bank_f and coupang_f:
            try:
                c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
                # 은행 파일 로드
                if bank_f.name.endswith('.csv'):
                    try: b_df = pd.read_csv(bank_f, encoding='utf-8-sig')
                    except: b_df = pd.read_csv(bank_f, encoding='cp949')
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
                
                # 쿠팡 파일 로드
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
                    st.success("데이터 통합 완료!")
                    st.rerun()
            except Exception as e: st.error(f"오류: {e}")
    
    st.markdown("---")
    st.download_button("📥 통합 장부 다운로드", st.session_state.master_df.to_csv(index=False).encode('utf-8-sig'), "율곡고시원_장부.csv", "text/csv")
    if st.button("🗑️ 장부 전체 초기화"):
        st.session_state.master_df = pd.DataFrame(columns=["연도", "월", "날짜", "내용", "용도", "구분", "금액", "비고"])
        st.rerun()

# --- [4] 메인 화면 ---
st.title("🏠 율곡고시원 통합 관리 시스템")
df = st.session_state.master_df
all_months = sorted(df['월'].unique()) if not df.empty else []
tabs = st.tabs(["📊 리포트", "📝 데이터 편집", "⚙️ 카테고리 설정"])

with tabs[1]: # 데이터 편집 (튀어오름 방지 혁신 구조)
    st.subheader("📝 스마트 데이터 편집")
    if not df.empty:
        st.info("▼ 아래 목록에서 수정할 항목을 선택하세요. 선택하면 우측에서 즉시 수정 가능합니다.")
        col_list, col_edit = st.columns([2, 1])
        
        with col_list:
            # 체크박스로 수정할 행 선택 (이 방식은 절대 튀지 않습니다)
            selected_rows = st.multiselect("수정할 내역 선택", df.index, format_func=lambda x: f"[{df.at[x,'날짜']}] {df.at[x,'내용']} ({df.at[x,'금액']:,}원)")
            st.dataframe(df, use_container_width=True, height=500)

        with col_edit:
            if selected_rows:
                st.markdown("### 🛠️ 선택 항목 일괄 수정")
                target_yongdo = st.selectbox("변경할 용도", st.session_state.cat_df["항목명"].tolist())
                if st.button("✅ 선택한 항목 모두 변경"):
                    c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
                    for idx in selected_rows:
                        st.session_state.master_df.at[idx, "용도"] = target_yongdo
                        st.session_state.master_df.at[idx, "구분"] = c_map.get(target_yongdo, "비용")
                    st.success(f"{len(selected_rows)}건 수정 완료!")
                    st.rerun()
                
                if st.button("🗑️ 선택한 항목 삭제"):
                    st.session_state.master_df = st.session_state.master_df.drop(selected_rows).reset_index(drop=True)
                    st.success("삭제 완료!")
                    st.rerun()
            else:
                st.write("👈 왼쪽에서 수정할 내역을 선택해 주세요.")
    else:
        st.info("데이터가 없습니다. 사이드바에서 파일을 업로드해 주세요.")

with tabs[2]: # 설정
    st.subheader("⚙️ 카테고리 설정")
    new_cat = st.data_editor(st.session_state.cat_df, num_rows="dynamic", use_container_width=True)
    if st.button("💾 설정 영구 저장"):
        st.session_state.cat_df = new_cat
        new_cat.to_csv(CAT_FILE, index=False)
        st.success("설정이 저장되었습니다.")

with tabs[0]: # 리포트
    if not df.empty:
        p_df = df[df['구분'] != '-'].copy()
        if not p_df.empty:
            p_df['금액'] = p_df['금액'].apply(clean_amt)
            st.metric("누적 순이익", f"{(p_df[p_df['구분']=='수익']['금액'].sum() - p_df[p_df['구분']=='비용']['금액'].sum()):,}원")
            st.plotly_chart(px.bar(p_df.groupby(['월', '구분'])['금액'].sum().reset_index(), x='월', y='금액', color='구분',
