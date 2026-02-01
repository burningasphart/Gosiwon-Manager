import streamlit as st
import pandas as pd
import plotly.express as px
import time
import re
import os

# 페이지 설정
st.set_page_config(page_title="율곡고시원 통합 관리 시스템", layout="wide")

# --- [1] 세구 설정 및 데이터 로드 ---
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

if 'needs_download' not in st.session_state:
    st.session_state.needs_download = False

# --- [2] 보조 함수 (날짜 및 금액 정제) ---
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
        return "2026", "01", "01/01"
    except: return "2026", "01", "01/01"

# --- [3] 메인 화면 구성 ---
st.title("🏠 율곡고시원 통합 정산 시스템")

# 사이드바 데이터 통합 로직
st.sidebar.header("📂 데이터 통합")
bank_file = st.sidebar.file_uploader("우리은행 거래내역", type=['csv', 'xls', 'xlsx'])
coupang_file = st.sidebar.file_uploader("쿠팡 구매내역", type=['csv'])

if st.sidebar.button("📦 새 데이터 합치기"):
    if bank_file and coupang_file:
        # (합치기 로직 생략 - 기존과 동일)
        st.session_state.needs_download = True
        st.sidebar.success("통합 완료!")
        st.rerun()

# 탭 구성
df = st.session_state.master_df
all_months = sorted(df['월'].unique()) if not df.empty else []
tabs = st.tabs(["📊 통합 리포트"] + [f"📅 {m}월 상세" for m in all_months] + ["📝 데이터 편집", "⚙️ 카테고리 설정"])

with tabs[-2]: # [중요] 데이터 편집 탭
    st.subheader("📝 상세 데이터 편집")
    st.info("💡 수정 후 다른 칸을 클릭하면 자동 저장됩니다. 행이 튀어 오르지 않도록 설계되었습니다.")
    
    cat_list = st.session_state.cat_df["항목명"].tolist()
    c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))

    # 1. 에디터에서 발생한 변경사항을 감지
    edited_df = st.data_editor(
        st.session_state.master_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "용도": st.column_config.SelectboxColumn("용도", options=cat_list, required=True),
            "구분": st.column_config.TextColumn("구분(자동)", disabled=True),
            "금액": st.column_config.NumberColumn("금액", format="%d")
        },
        key="master_editor_fixed" # 고정 키 사용
    )

    # 2. 화면 이동 없이 내부 데이터만 업데이트 (행 튀어오름 방지 핵심)
    if not edited_df.equals(st.session_state.master_df):
        # 용도 변경 시 구분값 자동 매핑
        edited_df['구분'] = edited_df['용도'].map(c_map).fillna(edited_df['구분'])
        st.session_state.master_df = edited_df
        st.session_state.needs_download = True
        # st.rerun()을 호출하지 않음으로써 스크롤 위치 유지

with tabs[-1]: # 카테고리 설정 탭
    st.subheader("⚙️ 카테고리 영구 저장")
    edited_cat = st.data_editor(st.session_state.cat_df, num_rows="dynamic", use_container_width=True)
    if st.button("설정 저장"):
        st.session_state.cat_df = edited_cat
        edited_cat.to_csv(CAT_FILE, index=False)
        st.success("설정이 저장되었습니다!")
        st.rerun()

with tabs[0]: # 리포트 탭
    if not df.empty:
        # (리포트 시각화 로직 동일)
        plot_df = df[df['구분'] != '-'].copy()
        if not plot_df.empty:
            plot_df['금액'] = plot_df['금액'].apply(clean_amt)
            stats = plot_df.groupby(['월', '구분'])['금액'].sum().unstack(fill_value=0).reset_index()
            for c in ['수익', '비용']: 
                if c not in stats: stats[c] = 0
            st.metric("누적 순이익", f"{(stats['수익'].sum()-stats['비용'].sum()):,}원")
            st.plotly_chart(px.bar(stats, x='월', y=['수익', '비용'], barmode='group', color_discrete_map={'수익': '#00CC96', '비용': '#EF553B'}), use_container_width=True)
    else: st.info("데이터를 업로드해주세요.")

for i, m in enumerate(all_months):
    with tabs[i+1]: st.dataframe(df[df['월'] == m], use_container_width=True)

st.sidebar.download_button("📥 통합 장부 다운로드", st.session_state.master_df.to_csv(index=False).encode('utf-8-sig'), "율곡고시원_마스터.csv", "text/csv")
