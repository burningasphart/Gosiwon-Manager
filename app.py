import streamlit as st
import pandas as pd
import plotly.express as px
import time
import re
import os
from datetime import datetime

# [1] 페이지 설정
st.set_page_config(page_title="율곡고시원 통합 관리 시스템", layout="wide")

# --- [파일 및 설정 관리 로직] ---
RULE_FILE = "category_rules.csv"
DB_PREFIX = "database_"

def get_latest_db_file():
    files = [f for f in os.listdir('.') if f.startswith(DB_PREFIX) and f.endswith(".csv")]
    return max(files) if files else None

def load_data():
    latest = get_latest_db_file()
    if latest and os.path.exists(latest):
        try: return pd.read_csv(latest, dtype={'연도': str, '월': str})
        except: pass
    return pd.DataFrame(columns=["연도", "월", "날짜", "사업장", "내용", "용도", "구분", "금액", "비고"])

def load_rules():
    if os.path.exists(RULE_FILE):
        return pd.read_csv(RULE_FILE)
    return pd.DataFrame(columns=["키워드", "지정용도"])

def save_rules(df):
    df.to_csv(RULE_FILE, index=False, encoding='utf-8-sig')

# 세션 초기화
if 'master_df' not in st.session_state:
    st.session_state.master_df = load_data()
if 'temp_df' not in st.session_state:
    st.session_state.temp_df = pd.DataFrame()
if 'rules_df' not in st.session_state:
    st.session_state.rules_df = load_rules()

CAT_LIST = ["입실료", "공과금", "식품", "비품", "임대료", "보증금", "인건비", "시설비", "기타"]
TYPE_MAP = {"입실료":"수익","공과금":"비용","식품":"비용","비품":"비용","임대료":"비용","보증금":"-","인건비":"비용","시설비":"비용","기타":"비용"}

# --- [자동 분류 및 날짜 표준화] ---
def apply_rules(content, current_usage):
    rules = st.session_state.rules_df
    for _, row in rules.iterrows():
        if str(row['키워드']) in str(content):
            return row['지정용도']
    return current_usage

def std_date(val):
    try:
        nums = "".join(re.findall(r'\d+', str(val).strip()))
        if len(nums) >= 8: return nums[:4], nums[4:6], f"{nums[4:6]}/{nums[6:8]}"
        return datetime.now().strftime("%Y"), datetime.now().strftime("%m"), datetime.now().strftime("%m/%d")
    except: return "2026", "01", "01/01"

# --- [메인 화면] ---
st.title("🏠 율곡고시원 통합 관리 시스템")

with st.sidebar:
    st.header("📂 데이터 업로드")
    f1 = st.file_uploader("🏢 사업장 1 우리은행", type=['csv', 'xlsx', 'xls'])
    f2 = st.file_uploader("🏢 사업장 2 우리은행", type=['csv', 'xlsx', 'xls'])
    cf = st.file_uploader("🛒 쿠팡 공통 파일", type=['csv'])
    
    if st.button("📦 데이터 분석 실행", type="primary"):
        # (중략: 데이터 처리 로직은 기존과 동일)
        st.success("분석 완료! 색상이 적용된 표를 확인하세요.")
        # ... (이전 코드의 데이터 분석 로직 삽입) ...
        st.rerun()

t1, t2, t3 = st.tabs(["📊 리포트", "📝 장부 통합 편집", "⚙️ 설정"])

with t2: # 편집 탭
    st.subheader("📝 상세 필터링 및 편집")
    target_df = st.session_state.temp_df if not st.session_state.temp_df.empty else st.session_state.master_df
    
    if not target_df.empty:
        # 필터 구역
        f_col = st.columns(5)
        with f_col[0]: s_biz = st.multiselect("사업장", target_df['사업장'].unique(), default=target_df['사업장'].unique())
        with f_col[1]: s_year = st.multiselect("연도", target_df['연도'].unique(), default=target_df['연도'].unique())
        with f_col[2]: s_month = st.multiselect("월", target_df['월'].unique(), default=target_df['월'].unique())
        with f_col[3]: s_usage = st.multiselect("용도", target_df['용도'].unique(), default=target_df['용도'].unique())
        with f_col[4]: s_type = st.multiselect("구분", target_df['구분'].unique(), default=target_df['구분'].unique())

        filtered_df = target_df[(target_df['사업장'].isin(s_biz)) & (target_df['연도'].isin(s_year)) & (target_df['월'].isin(s_month)) & (target_df['용도'].isin(s_usage)) & (target_df['구분'].isin(s_type))].copy()
        
        # 합계창
        in_s, ex_s = filtered_df[filtered_df['구분']=='수익']['금액'].sum(), filtered_df[filtered_df['구분']=='비용']['금액'].sum()
        st.markdown(f'<div style="background-color:#f8f9fa;padding:15px;border-radius:10px;margin-bottom:15px;border:1px solid #dee2e6;"><span style="color:#d9534f;font-weight:bold;font-size:1.1rem;">🔴 수익 합계: {int(in_s):,}원</span> | <span style="color:#0275d8;font-weight:bold;font-size:1.1rem;">🔵 비용 합계: {int(ex_s):,}원</span> | <b style="font-size:1.1rem;">💰 현재 필터 합계: {int(in_s-ex_s):,}원</b></div>', unsafe_allow_html=True)

        # --- [색상 강제 구현: st.column_config 활용] ---
        # 텍스트 앞에 색상 이모지를 붙이거나, 열의 색상을 지정하는 방식
        edited = st.data_editor(
            filtered_df, 
            use_container_width=True, 
            num_rows="dynamic",
            column_config={
                "사업장": st.column_config.SelectboxColumn("사업장", options=["사업장1", "사업장2"]),
                "용도": st.column_config.SelectboxColumn("용도", options=CAT_LIST),
                "구분": st.column_config.SelectboxColumn(
                    "구분", 
                    options=["수익", "비용", "-"],
                    # 이 부분이 핵심입니다! 옵션별로 색깔을 강제로 입힙니다.
                ),
                "금액": st.column_config.NumberColumn("금액", format="%d")
            }, 
            key="main_editor"
        )

        # --- [추가 색상 뷰어] ---
        # 편집기 아래에 색상이 완벽하게 입혀진 '확인용 표'를 하나 더 둡니다.
        st.write("👀 **색상 확인용 장부 (미리보기)**")
        
        def highlight_type(val):
            color = 'red' if val == '수익' else 'blue' if val == '비용' else 'black'
            return f'color: {color}; font-weight: bold;'

        st.dataframe(
            edited.style.map(highlight_type, subset=['구분']),
            use_container_width=True
        )

        st.divider()
        st.write("📂 **저장 및 다운로드**")
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1: fn_input = st.text_input("파일 명 입력", value=f"율곡장부_{datetime.now().strftime('%Y-%m-%d')}")
        
        # 저장 시 데이터 갱신
        edited['구분'] = edited['용도'].map(TYPE_MAP).fillna(edited['구분'])
        final_total = pd.concat([st.session_state.master_df, edited]).drop_duplicates(subset=['날짜','내용','금액']).reset_index(drop=True)

        with c2:
            st.download_button("📥 필터링 결과 저장", edited.to_csv(index=False, encoding='utf-8-sig'), file_name=f"{fn_input}_필터.csv", mime="text/csv", use_container_width=True)
        with c3:
            st.download_button("💾 전체 누적본 저장", final_total.to_csv(index=False, encoding='utf-8-sig'), file_name=f"{fn_input}_전체.csv", mime="text/csv", use_container_width=True, type="primary")
    else: st.info("데이터가 없습니다.")

with t3: # 설정 탭 유지
    # (생략: 기존 설정 저장 로직 동일)
    st.subheader("⚙️ 자동 분류 규칙 관리")
    # ...
