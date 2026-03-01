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

# --- [자동 분류 엔진] ---
def apply_rules(content, current_usage):
    rules = st.session_state.rules_df
    for _, row in rules.iterrows():
        if str(row['키워드']) in str(content):
            return row['지정용도']
    return current_usage

# --- [보조 함수] ---
def std_date(val):
    try:
        nums = "".join(re.findall(r'\d+', str(val).strip()))
        if len(nums) >= 8: return nums[:4], nums[4:6], f"{nums[4:6]}/{nums[6:8]}"
        return datetime.now().strftime("%Y"), datetime.now().strftime("%m"), datetime.now().strftime("%m/%d")
    except: return "2026", "01", "01/01"

def process_bank(file, biz_name):
    try:
        if file.name.lower().endswith('.csv'):
            try: df = pd.read_csv(file, encoding='cp949')
            except: df = pd.read_csv(file, encoding='utf-8-sig')
        else:
            try: df = pd.read_excel(file)
            except: df = pd.read_html(file)[0]
        h_idx = 0
        for i in range(min(20, len(df))):
            if '거래일시' in "".join(df.iloc[i].astype(str)): h_idx = i; break
        df.columns = df.iloc[h_idx]; df = df.iloc[h_idx+1:].reset_index(drop=True)
        rows = []
        for _, r in df.iterrows():
            if pd.isna(r.get('거래일시')): continue
            y, m, d = std_date(r.get('거래일시'))
            vi = int(str(r.get('맡기신금액',0)).replace(',','').strip() or 0)
            vo = int(str(r.get('찾으신금액',0)).replace(',','').strip() or 0)
            cont = str(r.get('기재내용','')).strip()
            init_usage = "입실료" if vi > 0 else "기타"
            final_usage = apply_rules(cont, init_usage)
            rows.append({
                "연도":y, "월":m, "날짜":d, "사업장":biz_name, "내용":cont, 
                "용도":final_usage, "구분":TYPE_MAP.get(final_usage, "비용"), 
                "금액":vi if vi>0 else vo, "비고":""
            })
        return rows
    except: return []

# --- [메인 화면] ---
st.title("🏠 율곡고시원 통합 관리 시스템")

with st.sidebar:
    st.header("📂 데이터 업로드")
    f1 = st.file_uploader("🏢 사업장 1 우리은행", type=['csv', 'xlsx', 'xls'])
    f2 = st.file_uploader("🏢 사업장 2 우리은행", type=['csv', 'xlsx', 'xls'])
    cf = st.file_uploader("🛒 쿠팡 공통 파일", type=['csv'])
    
    if st.button("📦 데이터 분석 실행", type="primary"):
        new_data = []
        if f1: new_data += process_bank(f1, "사업장1")
        if f2: new_data += process_bank(f2, "사업장2")
        if cf:
            try:
                cdf = pd.read_csv(cf, encoding='utf-8-sig')
                for _, r in cdf.iterrows():
                    y, m, d = std_date(r.get('주문일',''))
                    amt = int(str(r.get('총결제금액(원)',0)).replace(',','').strip() or 0)
                    cont = str(r.get('상품명',''))
                    final_usage = apply_rules(cont, "기타")
                    new_data.append({"연도":y,"월":m,"날짜":d,"사업장":"미분류(쿠팡)","내용":cont,"용도":final_usage,"구분":TYPE_MAP.get(final_usage, "비용"),"금액":amt,"비고":"쿠팡"})
            except: pass
        if new_data:
            st.session_state.temp_df = pd.DataFrame(new_data)
            st.success("분석 완료! 규칙이 적용되었습니다.")
            st.rerun()

t1, t2, t3 = st.tabs(["📊 리포트", "📝 장부 통합 편집", "⚙️ 설정"])

with t3: # 설정 탭
    st.subheader("⚙️ 자동 분류 규칙 설정")
    st.write("내용(기재내용)에 특정 단어가 포함되면 해당 용도로 자동 분류합니다.")
    
    with st.expander("➕ 새로운 규칙 추가", expanded=True):
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1: new_kw = st.text_input("찾을 키워드 (예: 전기요금, 삼다수)")
        with c2: new_cat = st.selectbox("지정할 용도", options=CAT_LIST)
        with c3:
            if st.button("규칙 추가", use_container_width=True):
                if new_kw:
                    new_row = pd.DataFrame([{"키워드": new_kw, "지정용도": new_cat}])
                    st.session_state.rules_df = pd.concat([st.session_state.rules_df, new_row]).drop_duplicates().reset_index(drop=True)
                    save_rules(st.session_state.rules_df)
                    st.success(f"'{new_kw}' 규칙이 서버에 저장되었습니다!")
                    st.rerun()

    st.write("### 📋 현재 저장된 규칙 목록")
    if not st.session_state.rules_df.empty:
        edited_rules = st.data_editor(st.session_state.rules_df, num_rows="dynamic", use_container_width=True, key="rule_editor")
        if st.button("🔄 수정사항 서버에 저장"):
            st.session_state.rules_df = edited_rules
            save_rules(edited_rules)
            st.toast("규칙이 서버에 업데이트되었습니다!")

with t2: # 편집 탭
    st.subheader("📝 상세 필터링 및 편집")
    target_df = st.session_state.temp_df if not st.session_state.temp_df.empty else st.session_state.master_df
    
    if not target_df.empty:
        # 필터 UI
        f_col = st.columns(5)
        with f_col[0]: s_biz = st.multiselect("사업장", target_df['사업장'].unique(), default=target_df['사업장'].unique())
        with f_col[1]: s_year = st.multiselect("연도", target_df['연도'].unique(), default=target_df['연도'].unique())
        with f_col[2]: s_month = st.multiselect("월", target_df['월'].unique(), default=target_df['월'].unique())
        with f_col[3]: s_usage = st.multiselect("용도", target_df['용도'].unique(), default=target_df['용도'].unique())
        with f_col[4]: s_type = st.multiselect("구분", target_df['구분'].unique(), default=target_df['구분'].unique())

        filtered_df = target_df[(target_df['사업장'].isin(s_biz)) & (target_df['연도'].isin(s_year)) & (target_df['월'].isin(s_month)) & (target_df['용도'].isin(s_usage)) & (target_df['구분'].isin(s_type))].copy()

        # 장부 편집기 ('-' 포함 Selectbox 적용)
        edited = st.data_editor(filtered_df, use_container_width=True, num_rows="dynamic",
            column_config={
                "사업장": st.column_config.SelectboxColumn("사업장", options=["사업장1", "사업장2"]),
                "용도": st.column_config.SelectboxColumn("용도", options=CAT_LIST),
                "구분": st.column_config.SelectboxColumn("구분", options=["수익", "비용", "-"]),
                "금액": st.column_config.NumberColumn("금액", format="%d")
            }, key="main_editor")

        # [핵심 수정] 편집된 데이터(edited)를 기준으로 실시간 합계 계산
        in_s = edited[edited['구분']=='수익']['금액'].astype(float).sum()
        ex_s = edited[edited['구분']=='비용']['금액'].astype(float).sum()
        
        # 합계창을 편집기 아래 혹은 위에 배치하여 실시간 확인 가능하게 함
        st.info(f"🔴 수익: {int(in_s):,}원 | 🔵 비용: {int(ex_s):,}원 | 💰 합계: {int(in_s-ex_s):,}원")

        st.divider()
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1: fn_input = st.text_input("파일 명 입력", value=f"율곡장부_{datetime.now().strftime('%Y-%m-%d')}")
        
        final_total = pd.concat([st.session_state.master_df, edited]).drop_duplicates(subset=['날짜','내용','금액']).reset_index(drop=True)

        with c2:
            st.download_button("📥 현재 필터 결과 저장", edited.to_csv(index=False, encoding='utf-8-sig'), file_name=f"{fn_input}_필터링.csv", mime="text/csv", use_container_width=True)
        with c3:
            st.download_button("💾 누적 전체장부 저장", final_total.to_csv(index=False, encoding='utf-8-sig'), file_name=f"{fn_input}_전체누적.csv", mime="text/csv", use_container_width=True, type="primary")
    else: st.info("데이터가 없습니다.")

with t1: # 리포트 탭
    m_df = st.session_state.master_df
    if not m_df.empty:
        years = sorted(m_df['연도'].unique().tolist(), reverse=True)
        y_tabs = st.tabs([f"📅 {y}년" for y in years])
        for i, y in enumerate(years):
            with y_tabs[i]:
                curr = m_df[m_df['연_도'] == y] if '연_도' in m_df.columns else m_df[m_df['연도'] == y]
                st.plotly_chart(px.bar(curr, x='월', y='금액', color='구분', barmode='group', color_discrete_map={'수익':'red','비용':'blue', '-':'gray'}))
