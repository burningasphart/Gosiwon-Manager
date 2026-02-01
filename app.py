import streamlit as st
import pandas as pd
import plotly.express as px
import time
import re

st.set_page_config(page_title="고시원 누적 정산 시스템", layout="wide")

# --- 세션 상태 보존 ---
if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame(columns=["연도", "월", "날짜", "내용", "용도", "구분", "금액", "비고"])
if 'cat_df' not in st.session_state:
    st.session_state.cat_df = pd.DataFrame({
        "항목명": ["입실료", "공과금", "식품", "비품", "임대료", "보증금", "인건비", "기타"],
        "연결구분": ["수익", "비용", "비용", "비용", "비용", "-", "비용", "비용"]
    })
if 'history' not in st.session_state:
    st.session_state.history = [st.session_state.master_df.copy()]
if 'history_ptr' not in st.session_state:
    st.session_state.history_ptr = 0
if 'needs_download' not in st.session_state:
    st.session_state.needs_download = False

def save_history(df):
    st.session_state.history = st.session_state.history[:st.session_state.history_ptr + 1]
    st.session_state.history.append(df.copy())
    st.session_state.history_ptr += 1
    if len(st.session_state.history) > 20:
        st.session_state.history.pop(0)
        st.session_state.history_ptr -= 1

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
            y, m, dv = parts[0], parts[1].zfill(2), parts[2].zfill(2)
            return y, m, f"{m}/{dv}"
        return "2026", "01", "01/01"
    except: return "2026", "01", "01/01"

st.title("🏠 고시원 누적 정산 시스템 (대표님 전용)")

# --- 사이드바 ---
st.sidebar.header("📂 데이터 관리")
prev_master = st.sidebar.file_uploader("과거 장부(.csv)", type=['csv'])
if st.sidebar.button("과거 기록 불러오기") and prev_master:
    st.session_state.master_df = pd.read_csv(prev_master)
    save_history(st.session_state.master_df)
    st.sidebar.success("로드 완료")

st.sidebar.divider()
bank_file = st.sidebar.file_uploader("우리은행 거래내역", type=['csv', 'xls', 'xlsx'])
coupang_file = st.sidebar.file_uploader("쿠팡 구매내역", type=['csv'])

if st.sidebar.button("📦 새 데이터 합치기"):
    if bank_file and coupang_file:
        try:
            # 은행/쿠팡 로딩 로직 (생략 없이 유지)
            if bank_file.name.endswith('.csv'): bank_df = pd.read_csv(bank_file, skiprows=3)
            else:
                bank_file.seek(0)
                html_list = pd.read_html(bank_file)
                bank_df = max(html_list, key=len)
                header_row = 0
                for i in range(min(15, len(bank_df))):
                    if '거래일시' in str(bank_df.iloc[i].values): header_row = i; break
                bank_df.columns = bank_df.iloc[header_row]
                bank_df = bank_df.iloc[header_row+1:].reset_index(drop=True)
            
            coupang_df = pd.read_csv(coupang_file)
            cat_map = st.session_state.cat_df.set_index("항목명")["연결구분"].to_dict()
            
            new_rows = []
            for _, r in bank_df.iterrows():
                if pd.isna(r.get('거래일시')): continue
                y, m, d_d = clean_date(r.get('거래일시'))
                vi, vo = clean_amt(r.get('맡기신금액', 0)), clean_amt(r.get('찾으신금액', 0))
                content = (str(r.get('기재내용', '')) + " " + str(r.get('적요', ''))).strip()
                # 새 데이터를 가져올 때 '기타'로 일단 분류
                new_rows.append({"연도": y, "월": m, "날짜": d_d, "내용": content, "용도": "기타", "구분": cat_map.get("기타", "비용"), "금액": vi if vi > 0 else vo, "비고": str(r.get('적요', ''))})
            for _, r in coupang_df.iterrows():
                price = clean_amt(r.get('총결제금액(원)', 0))
                if price > 0:
                    y, m, d_d = clean_date(r.get('주문일', ''))
                    new_rows.append({"연도": y, "월": m, "날짜": d_d, "내용": str(r.get('상품명', '')), "용도": "기타", "구분": cat_map.get("기타", "비용"), "금액": price, "비고": "쿠팡구매"})
            
            new_df = pd.DataFrame(new_rows)
            combined = pd.concat([st.session_state.master_df, new_df]).drop_duplicates(subset=['날짜', '내용', '금액'], keep='first')
            st.session_state.master_df = combined
            save_history(combined)
            st.session_state.needs_download = True
            st.sidebar.success("통합 완료")
        except Exception as e: st.sidebar.error(f"오류: {e}")

st.sidebar.divider()
include_misc = st.sidebar.checkbox("사업 수익에 '기타' 지출 포함하기", value=False)

if st.session_state.needs_download:
    st.warning("⚠️ 데이터가 변경되었습니다. 저장하시겠습니까?")
    st.download_button("✅ 지금 파일로 저장", st.session_state.master_df.to_csv(index=False).encode('utf-8-sig'), f"고시원_장부_{time.strftime('%Y%m%d')}.csv", "text/csv", on_click=lambda: st.session_state.update({"needs_download": False}))

# --- 메인 탭 ---
df = st.session_state.master_df
all_months = sorted(df['월'].unique()) if not df.empty else []
tabs = st.tabs(["📊 통합 리포트"] + [f"📅 {m}월 상세" for m in all_months] + ["📝 데이터 편집", "⚙️ 카테고리 설정"])

with tabs[-1]: # 카테고리 설정
    st.subheader("⚙️ 용도 및 계산 방식 설정")
    st.info("💡 여기서 연결구분을 바꾸면 편집 화면의 '구분'도 자동으로 따라갑니다.")
    edited_cat = st.data_editor(st.session_state.cat_df, num_rows="dynamic", use_container_width=True,
        column_config={"연결구분": st.column_config.SelectboxColumn("구분 방식", options=["수익", "비용", "-"], required=True)})
    if st.button("🛠 설정 반영하기"):
        st.session_state.cat_df = edited_cat
        # 마스터 데이터의 구분값도 카테고리 설정에 맞춰 강제 업데이트
        cat_map = edited_cat.set_index("항목명")["연결구분"].to_dict()
        st.session_state.master_df['구분'] = st.session_state.master_df['용도'].map(cat_map).fillna(st.session_state.master_df['구분'])
        st.success("카테고리 설정이 저장되었으며, 기존 데이터의 '구분'도 모두 업데이트되었습니다!")
        st.rerun()

with tabs[-2]: # 데이터 편집
    st.subheader("📝 데이터 상세 편집")
    # 카테고리 맵핑 정보 (실시간 반영용)
    cat_map = st.session_state.cat_df.set_index("항목명")["연결구분"].to_dict()
    
    col1, col2, _ = st.columns([1, 1, 5])
    with col1:
        if st.button("⬅️ 이전"):
            if st.session_state.history_ptr > 0:
                st.session_state.history_ptr -= 1
                st.session_state.master_df = st.session_state.history[st.session_state.history_ptr].copy()
                st.rerun()
    with col2:
        if st.button("이후 ➡️"):
            if st.session_state.history_ptr < len(st.session_state.history) - 1:
                st.session_state.history_ptr += 1
                st.session_state.master_df = st.session_state.history[st.session_state.history_ptr].copy()
                st.rerun()
    
    # 편집 중 용도를 바꾸면 구분이 자동으로 바뀌게 로직 강화
    temp_df = st.session_state.master_df.copy()
    edited = st.data_editor(temp_df, use_container_width=True, num_rows="dynamic",
        column_config={
            "용도": st.column_config.SelectboxColumn("용도", options=st.session_state.cat_df["항목명"].tolist(), required=True),
            "구분": st.column_config.TextColumn("구분 (자동)", disabled=True), # 구분을 수동으로 못 고치게 막고 자동화
            "금액": st.column_config.NumberColumn("금액", format="%d")
        })
    
    # 용도에 따라 구분을 강제로 다시 매칭 (사용자 실수 방지)
    edited['구분'] = edited['용도'].map(cat_map).fillna(edited['구분'])

    if st.button("💾 편집 내용 저장"):
        st.session_state.master_df = edited
        save_history(edited)
        st.session_state.needs_download = True
