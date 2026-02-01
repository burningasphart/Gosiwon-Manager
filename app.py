import streamlit as st
import pandas as pd
import plotly.express as px
import time
import re
import os

# [1] 페이지 설정 및 세션 초기화
st.set_page_config(page_title="율곡고시원 통합 관리 시스템", layout="wide")

if 'cat_df' not in st.session_state:
    st.session_state.cat_df = pd.DataFrame({
        "항목명": ["입실료", "공과금", "식품", "비품", "임대료", "보증금", "인건비", "시설비", "기타"],
        "연결구분": ["수익", "비용", "비용", "비용", "비용", "-", "비용", "비용", "비용"]
    })

if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame(columns=["연도", "월", "날짜", "내용", "용도", "구분", "금액", "비고"])

# --- [날짜 표준화 함수: 시간 제거 및 MM/DD 통일] ---
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
    bank_f = st.file_uploader("우리은행 (CSV/Excel)", type=['csv', 'xlsx'])
    coupang_f = st.file_uploader("쿠팡 (CSV)", type=['csv'])
    
    if st.button("📦 새 데이터 합치기", type="primary"):
        if bank_f and coupang_f:
            try:
                if bank_f.name.endswith('.csv'):
                    try: b_df = pd.read_csv(bank_f, encoding='cp949')
                    except: b_df = pd.read_csv(bank_f, encoding='utf-8-sig')
                else: b_df = pd.read_excel(bank_f)
                
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

# --- [탭 및 리포트 구성] ---
df = st.session_state.master_df
all_months = sorted(df['월'].unique().tolist()) if not df.empty else []
tabs = st.tabs(["📊 리포트", "📝 전체편집"] + [f"📅 {m}월" for m in all_months] + ["⚙️ 설정"])

with tabs[1]: # 편집 탭 (행 고정 핵심)
    st.subheader("📝 장부 통합 편집")
    st.info("💡 수정 후 하단의 [저장] 버튼을 누르면 모든 탭에 반영됩니다.")
    edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic", key="main_editor")
    if st.button("💾 변경사항 저장", use_container_width=True, type="primary"):
        c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
        edited_df['구분'] = edited_df['용도'].map(c_map).fillna(edited_df['구분'])
        st.session_state.master_df = edited_df
        st.success("저장 완료!")
        st.rerun()

for i, m in enumerate(all_months):
    with tabs[i+2]:
        st.dataframe(df[df['월'] == m], use_container_width=True)

with tabs[0]: # 리포트
    if not df.empty:
        st.metric("누적 수익", f"{df[df['구분']=='수익']['금액'].sum():,}원")
        st.plotly_chart(px.bar(df, x='월', y='금액', color='구분', barmode='group'), use_container_width=
