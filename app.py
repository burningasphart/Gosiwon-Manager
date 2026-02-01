import streamlit as st
import pandas as pd
import plotly.express as px
import time
import re
import os

# [1] 페이지 설정 및 세션 초기화
st.set_page_config(page_title="율곡고시원 정산 시스템", layout="wide")

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

# [2] 핵심: 행 튀어오름 방지용 실시간 동기화 함수
def sync_edit():
    if "master_editor" in st.session_state:
        edits = st.session_state["master_editor"]
        c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
        
        for row_idx, edit_dict in edits["edited_rows"].items():
            idx = st.session_state.master_df.index[row_idx]
            for col, val in edit_dict.items():
                st.session_state.master_df.at[idx, col] = val
                if col == "용도":
                    st.session_state.master_df.at[idx, "구분"] = c_map.get(val, "비용")
        
        for row in edits["added_rows"]:
            new_row = {col: "" for col in st.session_state.master_df.columns}
            new_row.update(row)
            if not new_row.get("용도"): new_row["용도"] = "기타"
            new_row["구분"] = c_map.get(new_row["용도"], "비용")
            st.session_state.master_df = pd.concat([st.session_state.master_df, pd.DataFrame([new_row])], ignore_index=True)
            
        if edits["deleted_rows"]:
            st.session_state.master_df = st.session_state.master_df.drop(st.session_state.master_df.index[edits["deleted_rows"]]).reset_index(drop=True)

# [3] 보조 함수
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
    if any(k in text for k in ['전기', '수도', '가스', '한전', 'SKB', '인터넷', '보험', '세무']): return "공과금"
    if any(k in text for k in ['쌀', '라면', '햇반', '오뚜기']): return "식품"
    if any(k in text for k in ['다이소', '비품', '세제', '휴지', '건전지']): return "비품"
    if '월세' in text or '임대료' in text: return "임대료"
    return "기타"

# [4] 메인 화면 및 사이드바
st.title("🏠 율곡고시원 통합 정산 시스템")

with st.sidebar:
    st.header("📂 데이터 통합")
    bank_f = st.file_uploader("우리은행", type=['csv', 'xlsx', 'xls'])
    coupang_f = st.file_uploader("쿠팡", type=['csv'])
    
    if st.button("📦 새 데이터 합치기"):
        if bank_f and coupang_f:
            try:
                c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
                if bank_f.name.endswith('.csv'): b_df = pd.read_csv(bank_f, encoding='cp949')
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
                    st.rerun()
            except Exception as e: st.error(f"오류: {e}")
    
    st.markdown("---")
    st.download_button("📥 장부 다운로드", st.session_state.master_df.to_csv(index=False).encode('utf-8-sig'), "율곡고시원_장부.csv", "text/csv")

# 메인 탭
df = st.session_state.master_df
all_months = sorted(df['월'].unique()) if not df.empty else []
tabs = st.tabs(["📊 리포트"] + [f"📅 {m}월" for m in all_months] + ["📝 편집", "⚙️ 설정"])

with tabs[-2]:
    st.subheader("📝 상세 데이터 편집")
    cat_list = st.session_state.cat_df["항목명"].tolist()
    st.data_editor(st.session_state.master_df, use_container_width=True, num_rows="dynamic",
        column_config={
            "용도": st.column_config.SelectboxColumn("용도", options=cat_list, required=True),
            "구분": st.column_config.TextColumn("구분(자동)", disabled=True),
            "금액": st.column_config.NumberColumn("금액", format="%d")
        }, key="master_editor", on_change=sync_edit)

with tabs[-1]:
    st.subheader("⚙️ 설정 저장")
    e_cat = st.data_editor(st.session_state.cat_df, num_rows="dynamic", use_container_width=True, key="cat_editor")
    if st.button("💾 설정 저장"):
        st.session_state.cat_df = e_cat
        e_cat.to_csv(CAT_FILE, index=False)
        st.success("설정이 저장되었습니다!")
        st.rerun()

with tabs[0]:
    if not df.empty:
        p_df = df[df['구분'] != '-'].copy()
        if not p_df.empty:
            p_df['금액'] = p_df['금액'].apply(clean_amt)
            st.metric("누적 순이익", f"{(p_df[p_df['구분']=='수익']['금액'].sum() - p_df[p_df['구분']=='비용']['금액'].sum()):,}원")
            st.plotly_chart(px.bar(p_df.groupby(['월', '구분'])['금액'].sum().reset_index(), x='월', y='금액', color='구분', barmode='group'), use_container_width=True)
    else: st.info("파일을 업로드해 주세요.")

for i, m in enumerate(all_months):
    with tabs[i+1]: st.dataframe(df[df['월'] == m], use_container_
