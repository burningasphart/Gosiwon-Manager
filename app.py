import streamlit as st
import pandas as pd
import plotly.express as px
import time
import re
import os
from datetime import datetime

# [1] 페이지 설정
st.set_page_config(page_title="율곡고시원 통합 관리 시스템", layout="wide")

# --- [파일 관리 로직] ---
def get_latest_db_file():
    files = [f for f in os.listdir('.') if f.startswith("database_") and f.endswith(".csv")]
    return max(files) if files else None

def load_data():
    latest = get_latest_db_file()
    if latest and os.path.exists(latest):
        try: return pd.read_csv(latest, dtype={'연도': str, '월': str})
        except: pass
    return pd.DataFrame(columns=["연도", "월", "날짜", "사업장", "내용", "용도", "구분", "금액", "비고"])

# 세션 초기화
if 'master_df' not in st.session_state:
    st.session_state.master_df = load_data()
if 'temp_df' not in st.session_state:
    st.session_state.temp_df = pd.DataFrame()
if 'cat_df' not in st.session_state:
    st.session_state.cat_df = pd.DataFrame({
        "항목명": ["입실료", "공과금", "식품", "비품", "임대료", "보증금", "인건비", "시설비", "기타"],
        "연결구분": ["수익", "비용", "비용", "비용", "비용", "-", "비용", "비용", "비용"]
    })

# --- [보조 함수] ---
def std_date(val):
    try:
        nums = "".join(re.findall(r'\d+', str(val).strip()))
        if len(nums) >= 8: return nums[:4], nums[4:6], f"{nums[4:6]}/{nums[6:8]}"
        return datetime.now().strftime("%Y"), datetime.now().strftime("%m"), datetime.now().strftime("%m/%d")
    except: return "2026", "01", "01/01"

def process_bank(file, biz_name, c_map):
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
            vi = int(str(r.get('맡기신금액',0)).replace(',','').split('.')[0] or 0)
            vo = int(str(r.get('찾으신금액',0)).replace(',','').split('.')[0] or 0)
            yd = "입실료" if vi > 0 else "기타"
            rows.append({"연도":y, "월":m, "날짜":d, "사업장":biz_name, "내용":str(r.get('기재내용','')).strip(), "용도":yd, "구분":c_map.get(yd, "비용"), "금액":vi if vi>0 else vo, "비고":""})
        return rows
    except: return []

# --- [메인 화면] ---
st.title("🏠 율곡고시원 통합 관리 시스템")
with st.sidebar:
    st.header("📂 데이터 업로드")
    bank_f1 = st.file_uploader("🏢 사업장 1 우리은행", type=['csv', 'xlsx', 'xls'])
    bank_f2 = st.file_uploader("🏢 사업장 2 우리은행", type=['csv', 'xlsx', 'xls'])
    coupang_f = st.file_uploader("🛒 쿠팡 공통 파일", type=['csv'])
    
    if st.button("📦 업로드 파일 분석 실행", type="primary"):
        c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
        all_new = []
        if bank_f1: all_new += process_bank(bank_f1, "사업장1", c_map)
        if bank_f2: all_new += process_bank(bank_f2, "사업장2", c_map)
        if coupang_f:
            try:
                c_df = pd.read_csv(coupang_f, encoding='utf-8-sig')
                for _, r in c_df.iterrows():
                    y, m, d = std_date(r.get('주문일',''))
                    amt = int(str(r.get('총결제금액(원)',0)).replace(',','').split('.')[0] or 0)
                    all_new.append({"연도":y,"월":m,"날짜":d,"사업장":"미분류(쿠팡)","내용":str(r.get('상품명','')),"용도":"기타","구분":"비용","금액":amt,"비고":"쿠팡"})
            except: pass
        if all_new:
            st.session_state.temp_df = pd.DataFrame(all_new)
            st.success("분석 완료! 편집 탭에서 확인하세요.")
            st.rerun()

main_tabs = st.tabs(["📊 리포트", "📝 장부 통합 편집", "⚙️ 설정"])

with main_tabs[1]: # 편집 탭
    st.subheader("📝 상세 필터링 및 편집")
    work_df = st.session_state.temp_df if not st.session_state.temp_df.empty else st.session_state.master_df
    
    if not work_df.empty:
        # --- [필터링 구역 강화] ---
        f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns(5)
        with f_col1:
            sel_biz = st.multiselect("🏢 사업장", options=sorted(work_df['사업장'].unique()), default=list(work_df['사업장'].unique()))
        with f_col2:
            sel_year = st.multiselect("📅 연도", options=sorted(work_df['연도'].unique()), default=list(work_df['연도'].unique()))
        with f_col3:
            sel_month = st.multiselect("📆 월", options=sorted(work_df['월'].unique()), default=list(work_df['월'].unique()))
        with f_col4:
            sel_usage = st.multiselect("💡 용도", options=sorted(work_df['용도'].unique()), default=list(work_df['용도'].unique()))
        with f_col5:
            sel_type = st.multiselect("🏷️ 구분", options=sorted(work_df['구분'].unique()), default=list(work_df['구분'].unique()))

        # 필터 적용
        disp_df = work_df[
            (work_df['사업장'].isin(sel_biz)) & 
            (work_df['연도'].isin(sel_year)) & 
            (work_df['월'].isin(sel_month)) &
            (work_df['용도'].isin(sel_usage)) &
            (work_df['구분'].isin(sel_type))
        ].copy()
        
        # 실시간 합계
        inc = disp_df[disp_df['구분']=='수익']['금액'].astype(float).sum()
        exp = disp_df[disp_df['구분']=='비용']['금액'].astype(float).sum()
        st.markdown(f'<div style="position: sticky; top: 0; background-color: #ffffff; padding: 10px; border: 2px solid #f0f2f6; border-radius: 10px; z-index: 1000; margin-bottom: 10px;"><span style="color:red; font-weight:bold;">🔴 수익 합계: {int(inc):,}원</span> | <span style="color:blue; font-weight:bold;">🔵 비용 합계: {int(exp):,}원</span> | <b>💰 현재 필터 합계: {int(inc-exp):,}원</b></div>', unsafe_allow_html=True)

        # 표 편집기
        cat_list = st.session_state.cat_df["항목명"].tolist()
        edited_df = st.data_editor(disp_df, use_container_width=True, num_rows="dynamic",
            column_config={"사업장": st.column_config.SelectboxColumn("사업장", options=["사업장1", "사업장2"], required=True),
                           "용도": st.column_config.SelectboxColumn("용도", options=cat_list),
                           "금액": st.column_config.NumberColumn("금액", format="%d")}, key="ed_v6")
        
        st.divider()
        
        # --- [저장 및 다운로드 구역] ---
        st.write("📂 **결과 내보내기 및 영구 저장**")
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1: custom_fn = st.text_input("저장 파일 이름", value=f"율곡장부_{datetime.now().strftime('%Y-%m-%d')}")
        with c2:
            # 필터링 결과만 CSV로 다운로드 (구글 스프레드시트용)
            csv_data = edited_df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 필터 결과 다운로드",
                data=csv_data,
                file_name=f"{custom_fn}_필터결과.csv",
                mime="text/csv",
                use_container_width=True
            )
        with c3:
            if st.button("💾 장부에 최종 저장", use_container_width=True, type="primary"):
                c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
                edited_df['구분'] = edited_df['용도'].map(c_map).fillna(edited_df['구분'])
                final = pd.concat([st.session_state.master_df, edited_df]).drop_duplicates(subset=['날짜','내용','금액']).reset_index(drop=True)
                st.session_state.master_df = final
                st.session_state.temp_df = pd.DataFrame()
                fn = f"database_{custom_fn}.csv" if not custom_fn.startswith("database_") else f"{custom_fn}.csv"
                final.to_csv(fn, index=False, encoding='utf-8-sig')
                st.success("✅ 장부에 성공적으로 누적되었습니다!")
                time.sleep(1); st.rerun()
    else: st.info("사이드바에서 파일을 업로드해 주세요.")

with main_tabs[0]: # 리포트 탭
    m_df = st.session_state.master_df
    if not m_df.empty:
        years = sorted(m_df['연도'].unique().tolist(), reverse=True)
        y_tabs = st.tabs([f"📅 {y}년" for y in years])
        for i, y in enumerate(years):
            with y_tabs[i]:
                curr = m_df[m_df['연도'] == y]
                st.plotly_chart(px.bar(curr, x='월', y='금액', color='구분', barmode='group', color_discrete_map={'수익':'red','비용':'blue'}))
                st.dataframe(curr, use_container_width=True)
