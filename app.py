import streamlit as st
import pandas as pd
import plotly.express as px
import time
import re

# [1] 페이지 설정 및 세션 초기화
st.set_page_config(page_title="율곡고시원 통합 관리 시스템", layout="wide")

if 'cat_df' not in st.session_state:
    st.session_state.cat_df = pd.DataFrame({
        "항목명": ["입실료", "공과금", "식품", "비품", "임대료", "보증금", "인건비", "시설비", "기타"],
        "연결구분": ["수익", "비용", "비용", "비용", "비용", "-", "비용", "비용", "비용"]
    })

if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame(columns=["연도", "월", "날짜", "사업장", "내용", "용도", "구분", "금액", "비고"])

# --- [보조 함수] ---
def standardize_date(date_val):
    try:
        d_str = str(date_val).strip()
        nums = "".join(re.findall(r'\d+', d_str))
        if len(nums) >= 8:
            return nums[:4], nums[4:6], f"{nums[4:6]}/{nums[6:8]}"
        return time.strftime("%Y"), time.strftime("%m"), time.strftime("%m/%d")
    except:
        return time.strftime("%Y"), time.strftime("%m"), time.strftime("%m/%d")

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
            y, m, d = standardize_date(r.get('거래일시'))
            vi = int(str(r.get('맡기신금액',0)).replace(',','').split('.')[0] or 0)
            vo = int(str(r.get('찾으신금액',0)).replace(',','').split('.')[0] or 0)
            yd = "입실료" if vi > 0 else "기타"
            rows.append({"연도":y, "월":m, "날짜":d, "사업장":biz_name, "내용":str(r.get('기재내용','')).strip(), "용도":yd, "구분":c_map.get(yd, "비용"), "금액":vi if vi>0 else vo, "비고":""})
        return rows
    except: return []

# --- [메인 화면] ---
st.title("🏠 율곡고시원 1·2호점 통합 관리")

with st.sidebar:
    st.header("📂 데이터 업로드")
    bank_f1 = st.file_uploader("🏢 사업장 1 우리은행 파일", type=['csv', 'xlsx', 'xls'])
    bank_f2 = st.file_uploader("🏢 사업장 2 우리은행 파일", type=['csv', 'xlsx', 'xls'])
    coupang_f = st.file_uploader("🛒 쿠팡 공통 파일", type=['csv'])
    
    if st.button("📦 모든 데이터 합치기", type="primary"):
        c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
        all_new = []
        if bank_f1: all_new += process_bank(bank_f1, "사업장1", c_map)
        if bank_f2: all_new += process_bank(bank_f2, "사업장2", c_map)
        if coupang_f:
            try:
                c_df = pd.read_csv(coupang_f, encoding='utf-8-sig')
                for _, r in c_df.iterrows():
                    y, m, d = standardize_date(r.get('주문일',''))
                    amt = int(str(r.get('총결제금액(원)',0)).replace(',','').split('.')[0] or 0)
                    all_new.append({"연도":y, "월":m, "날짜":d, "사업장":"미분류(쿠팡)", "내용":str(r.get('상품명','')), "용도":"기타", "구분":"비용", "금액":amt, "비고":"쿠팡"})
            except: pass
        
        if all_new:
            st.session_state.master_df = pd.concat([st.session_state.master_df, pd.DataFrame(all_new)]).drop_duplicates(subset=['날짜','내용','금액']).reset_index(drop=True)
            st.success("통합 완료!")
            st.rerun()

# --- [데이터 처리 및 레이아웃] ---
df = st.session_state.master_df
main_tabs = st.tabs(["📊 사업장별 리포트", "📝 장부 통합 편집", "⚙️ 설정"])

with main_tabs[1]: # 편집 탭
    if not df.empty:
        # [1] 상단 고정 합계창
        in_sum = df[df['구분']=='수익']['금액'].astype(float).sum()
        ex_sum = df[df['구분']=='비용']['금액'].astype(float).sum()
        
        st.markdown(f"""
            <div style="position: sticky; top: 0; background-color: #ffffff; padding: 15px; border: 2px solid #f0f2f6; border-radius: 10px; z-index: 1000; margin-bottom: 20px;">
                <span style="color: #ff4b4b; font-weight: bold; font-size: 1.1rem; margin-right: 25px;">🔴 전체 수익: {int(in_sum):,}원</span>
                <span style="color: #1c83e1; font-weight: bold; font-size: 1.1rem; margin-right: 25px;">🔵 전체 비용: {int(ex_sum):,}원</span>
                <span style="color: #31333F; font-weight: bold; font-size: 1.1rem;">💰 전체 잔액: {int(in_sum - ex_sum):,}원</span>
            </div>
        """, unsafe_allow_html=True)

        # [2] 색상 적용 함수
        def color_row(row):
            color = 'red' if row['구분'] == '수익' else ('blue' if row['구분'] == '비용' else 'black')
            return [f'color: {color}; font-weight: bold' if name == '구분' else '' for name in row.index]

        # [3] 편집창 (사업장 태그 포함)
        cat_list = st.session_state.cat_df["항목명"].tolist()
        edited_df = st.data_editor(
            df.style.apply(color_row, axis=1),
            use_container_width=True, 
            num_rows="dynamic",
            column_config={
                "사업장": st.column_config.SelectboxColumn("사업장", options=["사업장1", "사업장2", "미분류(쿠팡)"], required=True),
                "용도": st.column_config.SelectboxColumn("용도", options=cat_list),
                "구분": st.column_config.TextColumn("구분(자동)", disabled=True),
                "금액": st.column_config.NumberColumn("금액", format="%d")
            },
            key="master_editor_vFinal"
        )
        
        if st.button("💾 변경사항 저장", use_container_width=True, type="primary"):
            c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
            # 데이터 동기화
            st.session_state.master_df = edited_df
            st.session_state.master_df['구분'] = st.session_state.master_df['용도'].map(c_map).fillna(st.session_state.master_df['구분'])
            st.success("저장 완료!")
            st.rerun()
    else:
        st.info("데이터를 먼저 업로드해 주세요.")

with main_tabs[0]: # 리포트 탭
    if not df.empty:
        biz_sel = st.radio("조회 사업장", ["전체", "사업장1", "사업장2"], horizontal=True)
        r_df = df if biz_sel == "전체" else df[df['사업장'] == biz_sel]
        
        all_years = sorted(r_df['연도'].unique().tolist(), reverse=True)
        y_tabs = st.tabs([f"📅 {y}년" for y in all_years])
        for i, y in enumerate(all_years):
            with y_tabs[i]:
                curr = r_df[r_df['연도'] == y]
                st.plotly_chart(px.bar(curr, x='월', y='금액', color='구분', barmode='group', title=f"{biz_sel} {y}년 현황", color_discrete_map={'수익': 'red', '비용': 'blue'}))
                st.dataframe(curr, use_container_width=True)
