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
    st.session_state.master_df = pd.DataFrame(columns=["연도", "월", "날짜", "내용", "용도", "구분", "금액", "비고"])

# --- [날짜 표준화 함수] ---
def standardize_date(date_val):
    try:
        d_str = str(date_val).strip()
        nums = "".join(re.findall(r'\d+', d_str))
        if len(nums) >= 8:
            return nums[:4], nums[4:6], f"{nums[4:6]}/{nums[6:8]}"
        return time.strftime("%Y"), time.strftime("%m"), time.strftime("%m/%d")
    except:
        return time.strftime("%Y"), time.strftime("%m"), time.strftime("%m/%d")

# --- [메인 화면] ---
st.title("🏠 율곡고시원 통합 관리 시스템")

with st.sidebar:
    st.header("📂 데이터 통합")
    bank_f = st.file_uploader("우리은행 (CSV/Excel)", type=['csv', 'xlsx', 'xls'])
    coupang_f = st.file_uploader("쿠팡 (CSV)", type=['csv'])
    
    if st.button("📦 새 데이터 합치기", type="primary"):
        if bank_f and coupang_f:
            try:
                if bank_f.name.lower().endswith('.csv'):
                    try: b_df = pd.read_csv(bank_f, encoding='cp949')
                    except: b_df = pd.read_csv(bank_f, encoding='utf-8-sig')
                else:
                    try: b_df = pd.read_excel(bank_f)
                    except: b_df = pd.read_html(bank_f)[0]
                
                h_idx = 0
                for i in range(min(20, len(b_df))):
                    if '거래일시' in "".join(b_df.iloc[i].astype(str)): h_idx = i; break
                b_df.columns = b_df.iloc[h_idx]; b_df = b_df.iloc[h_idx+1:].reset_index(drop=True)
                
                new_rows = []
                c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
                
                for _, r in b_df.iterrows():
                    d_val = r.get('거래일시')
                    if pd.isna(d_val): continue
                    y, m, d_std = standardize_date(d_val)
                    vi = int(str(r.get('맡기신금액',0)).replace(',','').split('.')[0] or 0)
                    vo = int(str(r.get('찾으신금액',0)).replace(',','').split('.')[0] or 0)
                    content = str(r.get('기재내용','')).strip()
                    yd = "입실료" if vi > 0 else "기타"
                    new_rows.append({"연도":y, "월":m, "날짜":d_std, "내용":content, "용도":yd, "구분":c_map.get(yd, "비용"), "금액":vi if vi>0 else vo, "비고":""})

                c_df = pd.read_csv(coupang_f, encoding='utf-8-sig')
                for _, r in c_df.iterrows():
                    y, m, d_std = standardize_date(r.get('주문일',''))
                    amt = int(str(r.get('총결제금액(원)',0)).replace(',','').split('.')[0] or 0)
                    p_name = str(r.get('상품명',''))
                    new_rows.append({"연도":y, "월":m, "날짜":d_std, "내용":p_name, "용도":"기타", "구분":"비용", "금액":amt, "비고":"쿠팡"})

                if new_rows:
                    st.session_state.master_df = pd.concat([st.session_state.master_df, pd.DataFrame(new_rows)]).drop_duplicates(subset=['날짜','내용','금액']).reset_index(drop=True)
                    st.success("데이터 통합 완료!")
                    st.rerun()
            except Exception as e:
                st.error(f"오류: {e}")

# --- [메인 레이아웃] ---
df = st.session_state.master_df
main_tabs = st.tabs(["📊 연도별 리포트", "📝 전체편집", "⚙️ 설정"])

with main_tabs[1]: # 전체편집 탭
    st.subheader("📝 장부 통합 편집")
    
    if not df.empty:
        # [상단 고정 합계 표시창]
        income_sum = df[df['구분']=='수익']['금액'].astype(float).sum()
        expense_sum = df[df['구분']=='비용']['금액'].astype(float).sum()
        total_balance = income_sum - expense_sum
        
        # 합계 항목을 상단에 고정 표시
        st.markdown(f"""
            <div style="position: sticky; top: 0; background-color: white; padding: 10px; border: 1px solid #ddd; border-radius: 5px; z-index: 1000; margin-bottom: 20px;">
                <span style="color: red; font-weight: bold; font-size: 1.2rem; margin-right: 20px;">🔴 수익 합계: {int(income_sum):,}원</span>
                <span style="color: blue; font-weight: bold; font-size: 1.2rem; margin-right: 20px;">🔵 비용 합계: {int(expense_sum):,}원</span>
                <span style="color: black; font-weight: bold; font-size: 1.2rem;">💰 총 합계: {int(total_balance):,}원</span>
            </div>
        """, unsafe_allow_html=True)

        # [수익/비용 색상 구분 적용]
        def color_df(val):
            if val == '수익': color = 'red'
            elif val == '비용': color = 'blue'
            else: color = 'black'
            return f'color: {color}; font-weight: bold;'

        # 편집창 구성
        cat_list = st.session_state.cat_df["항목명"].tolist()
        edited_df = st.data_editor(
            df.style.applymap(color_df, subset=['구분']), # 구분에 색상 적용
            use_container_width=True, 
            num_rows="dynamic", 
            key="main_editor",
            column_config={
                "용도": st.column_config.SelectboxColumn("용도", options=cat_list, required=True),
                "구분": st.column_config.TextColumn("구분(자동)", disabled=True),
                "금액": st.column_config.NumberColumn("금액", format="%d")
            }
        )
        
        if st.button("💾 변경사항 저장", use_container_width=True, type="primary"):
            c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
            edited_df['구분'] = edited_df['용도'].map(c_map).fillna(edited_df['구분'])
            st.session_state.master_df = edited_df
            st.success("저장 완료!")
            st.rerun()
    else:
        st.info("데이터를 업로드해 주세요.")

with main_tabs[0]: # 리포트 탭
    if not df.empty:
        all_years = sorted(df['연도'].unique().tolist(), reverse=True)
        year_tabs = st.tabs([f"📅 {y}년" for y in all_years])
        for i, y in enumerate(all_years):
            with year_tabs[i]:
                y_df = df[df['연도'] == y].copy()
                y_df['금액'] = pd.to_numeric(y_df['금액'], errors='coerce').fillna(0)
                income = y_df[y_df['구분']=='수익']['금액'].sum()
                expense = y_df[y_df['구분']=='비용']['금액'].sum()
                
                st.subheader(f"✨ {y}년 총결산")
                c1, c2, c3 = st.columns(3)
                c1.metric("총 수익", f"{int(income):,}원")
                c2.metric("총 비용", f"{int(expense):,}원")
                c3.metric("순이익", f"{int(income - expense):,}원")
                
                chart_df = y_df.groupby(['월', '구분'])['금액'].sum().reset_index()
                st.plotly_chart(px.bar(chart_df, x='월', y='금액', color='구분', barmode='group', color_discrete_map={'수익': 'red', '비용': 'blue'}), use_container_width=True)
