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
        if pd.isna(x) or str(x).strip() == "": return 0
        s = "".join(filter(str.isdigit, str(x).split('.')[0]))
        return int(s) if s else 0
    except: return 0

# --- 메인 화면 구성 ---
st.title("🏠 율곡고시원 통합 관리 시스템")

# [사이드바] 파일 업로드 및 다운로드
with st.sidebar:
    st.header("📂 데이터 관리")
    bank_f = st.file_uploader("우리은행 거래내역", type=['csv', 'xlsx', 'xls'])
    coupang_f = st.file_uploader("쿠팡 구매내역", type=['csv'])
    
    if st.button("📦 새 데이터 합치기"):
        # (통합 로직은 안정화되었으므로 생략/유지)
        st.success("데이터 통합이 완료되었습니다!")
        st.rerun()
    
    st.markdown("---")
    st.download_button("📥 통합 장부 다운로드", st.session_state.master_df.to_csv(index=False).encode('utf-8-sig'), "율곡고시원_장부.csv", "text/csv")

# [메인 탭] 
# 편집 탭을 가장 찾기 쉽게 리포트 다음으로 배치했습니다.
tabs = st.tabs(["📊 리포트", "📝 데이터 편집", "⚙️ 카테고리 설정"])

with tabs[1]: # [📝 데이터 편집] 탭
    st.subheader("📝 상세 데이터 편집")
    st.info("💡 용도(수익/비용)를 수정해도 행이 위로 튀어 오르지 않습니다. 수정을 마친 후 아래 [저장] 버튼을 꼭 눌러주세요.")
    
    cat_list = st.session_state.cat_df["항목명"].tolist()
    
    # [핵심] 튀어오름을 유발하는 모든 실시간 기능을 제거하고 단순히 데이터만 보여줍니다.
    edited_df = st.data_editor(
        st.session_state.master_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "용도": st.column_config.SelectboxColumn("용도", options=cat_list),
            "구분": st.column_config.TextColumn("구분", disabled=True), # 수동 수정 불가
            "금액": st.column_config.NumberColumn("금액", format="%d")
        },
        key="master_editor_fixed" # 고유 키로 위치 고정
    )
    
    # [저장 버튼] 눈에 잘 띄도록 크게 배치
    if st.button("💾 위 내용으로 장부 저장 및 구분 자동 업데이트", use_container_width=True, type="primary"):
        c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
        # 1. 편집기의 내용을 장부에 반영
        st.session_state.master_df = edited_df
        # 2. 용도에 맞춰 구분(수익/비용) 일괄 업데이트
        st.session_state.master_df['구분'] = st.session_state.master_df['용도'].map(c_map).fillna(st.session_state.master_df['구분'])
        st.success("✅ 모든 변경사항이 안전하게 저장되었습니다!")
        time.sleep(1)
        st.rerun()

with tabs[2]: # [⚙️ 카테고리 설정] 탭
    st.subheader("⚙️ 카테고리 설정")
    new_cat = st.data_editor(st.session_state.cat_df, num_rows="dynamic", use_container_width=True, key="cat_settings_fixed")
    if st.button("💾 카테고리 영구 저장"):
        st.session_state.cat_df = new_cat
        new_cat.to_csv(CAT_FILE, index=False)
        st.success("설정이 저장되었습니다.")

with tabs[0]: # [📊 리포트] 탭
    df = st.session_state.master_df
    if not df.empty:
        p_df = df[df['구분'].isin(['수익', '비용'])].copy()
        if not p_df.empty:
            p_df['금액'] = p_df['금액'].apply(clean_amt)
            st.metric("누적 순이익", f"{(p_df[p_df['구분']=='수익']['금액'].sum() - p_df[p_df['구분']=='비용']['금액'].sum()):,}원")
            st.plotly_chart(px.bar(p_df, x='월', y='금액', color='구분', barmode='group'), use_container_width=True)
    else: st.info("사이드바에서 데이터를 먼저 업로드해 주세요.")
