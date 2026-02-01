import streamlit as st
import pandas as pd
import plotly.express as px
import time
import re

st.set_page_config(page_title="고시원 누적 정산 시스템", layout="wide")

# --- 세션 초기화 ---
def init_session():
    if 'cat_df' not in st.session_state:
        st.session_state.cat_df = pd.DataFrame({
            "항목명": ["입실료", "공과금", "식품", "비품", "임대료", "보증금", "인건비", "기타"],
            "연결구분": ["수익", "비용", "비용", "비용", "비용", "-", "비용", "비용"]
        })
    if 'master_df' not in st.session_state:
        st.session_state.master_df = pd.DataFrame(columns=["연도", "월", "날짜", "내용", "용도", "구분", "금액", "비고"])
    if 'history' not in st.session_state:
        st.session_state.history = [st.session_state.master_df.copy()]
    if 'history_ptr' not in st.session_state:
        st.session_state.history_ptr = 0
    if 'needs_download' not in st.session_state:
        st.session_state.needs_download = False

init_session()

# 자동 분류 로직 보강 (복구용)
def get_auto_yongdo(content, income):
    content = str(content)
    if income > 0: return "입실료"
    if any(k in content for k in ['전기', '수도', '예스코', '가스', '한전', '공과금']): return "공과금"
    if any(k in content for k in ['쌀', '라면', '우유', '커피', '식료', '아몬드']): return "식품"
    if any(k in content for k in ['다이소', '비품', '세제', '휴지', '점보롤', '타월']): return "비품"
    if '임대료' in content: return "임대료"
    if '보증금' in content: return "보증금"
    if '인건비' in content: return "인건비"
    return "기타"

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

def save_history(df):
    st.session_state.history = st.session_state.history[:st.session_state.history_ptr + 1]
    st.session_state.history.append(df.copy())
    st.session_state.history_ptr += 1

st.title("🏠 고시원 누적 정산 시스템")

# --- 사이드바 ---
st.sidebar.header("📂 데이터 관리")
if st.sidebar.button("🛠 잘못된 '기타' 항목 자동 복구"):
    # 현재 데이터 중 '기타'로 되어있는 것들만 다시 분류 시도
    df_fix = st.session_state.master_df.copy()
    cat_map = st.session_state.cat_df.set_index("항목명")["연결구분"].to_dict()
    
    for idx, row in df_fix.iterrows():
        if row['용도'] == "기타":
            income_val = row['금액'] if row['구분'] == "수익" else 0
            new_yongdo = get_auto_yongdo(row['내용'], income_val)
            df_fix.at[idx, '용도'] = new_yongdo
            df_fix.at[idx, '구분'] = cat_map.get(new_yongdo, "비용")
            
    st.session_state.master_df = df_fix
    save_history(df_fix)
    st.sidebar.success("자동 복구 완료! 내용을 확인해주세요.")

st.sidebar.divider()
bank_file = st.sidebar.file_uploader("우리은행 거래내역", type=['csv', 'xls', 'xlsx'])
coupang_file = st.sidebar.file_uploader("쿠팡 구매내역", type=['csv'])

if st.sidebar.button("📦 새 데이터 합치기"):
    if bank_file and coupang_file:
        try:
            cat_map = st.session_state.cat_df.set_index("항목명")["연결구분"].to_dict()
            # 파일 읽기 로직 (생략 없이 유지)
            if bank_file.name.endswith('.csv'): bank_df = pd.read_csv(bank_file, skiprows=3)
            else:
                bank_file.seek(0)
                html_list = pd.read_html(bank_file); bank_df = max(html_list, key=len)
                header_row = 0
                for i in range(min(15, len(bank_df))):
                    if '거래일시' in str(bank_df.iloc[i].values): header_row = i; break
                bank_df.columns = bank_df.iloc[header_row]; bank_df = bank_df.iloc[header_row+1:].reset_index(drop=True)
            
            coupang_df = pd.read_csv(coupang_file)
            new_rows = []
            
            for _, r in bank_df.iterrows():
                if pd.isna(r.get('거래일시')): continue
                y, m, d_d = clean_date(r.get('거래일시'))
                vi, vo = clean_amt(r.get('맡기신금액', 0)), clean_amt(r.get('찾으신금액', 0))
                content = (str(r.get('기재내용', '')) + " " + str(r.get('적요', ''))).strip()
                # 새 데이터는 로드 시점에 자동 분류 적용
                auto_y = get_auto_yongdo(content, vi)
                new_rows.append({"연도": y, "월": m, "날짜": d_d, "내용": content, "용도": auto_y, "구분": cat_map.get(auto_y, "비용"), "금액": vi if vi > 0 else vo, "비고": str(r.get('적요', ''))})
            
            for _, r in coupang_df.iterrows():
                price = clean_amt(r.get('총결제금액(원)', 0))
                if price > 0:
                    y, m, d_d = clean_date(r.get('주문일', ''))
                    auto_y = get_auto_yongdo(r.get('상품명', ''), 0)
                    new_rows.append({"연도": y, "월": m, "날짜": d_d, "내용": str(r.get('상품명', '')), "용도": auto_y, "구분": cat_map.get(auto_y, "비용"), "금액": price, "비고": "쿠팡구매"})
            
            new_df = pd.DataFrame(new_rows)
            # 기존 데이터와 합치되, 중복 시 기존에 대표님이 수정한 데이터(용도)를 유지함
            combined = pd.concat([st.session_state.master_df, new_df]).drop_duplicates(subset=['날짜', '내용', '금액'], keep='first')
            st.session_state.master_df = combined
            save_history(combined); st.session_state.needs_download = True
            st.sidebar.success("통합 완료!")
        except Exception as e: st.sidebar.error(f"오류: {e}")

# (이후 리포트/편집/카테고리 탭 코드는 이전과 동일)
df = st.session_state.master_df
all_months = sorted(df['월'].unique()) if not df.empty else []
tabs = st.tabs(["📊 통합 리포트"] + [f"📅 {m}월 상세" for m in all_months] + ["📝 데이터 편집", "⚙️ 카테고리 설정"])

with tabs[-2]: # 데이터 편집
    st.subheader("📝 데이터 편집")
    cat_map = st.session_state.cat_df.set_index("항목명")["연결구분"].to_dict()
    # 이전/이후 버튼 생략(코드 동일)
    edited = st.data_editor(st.session_state.master_df, use_container_width=True, num_rows="dynamic",
        column_config={
            "용도": st.column_config.SelectboxColumn("용도", options=st.session_state.cat_df["항목명"].tolist(), required=True),
            "구분": st.column_config.TextColumn("구분 (자동)", disabled=True),
            "금액": st.column_config.NumberColumn("금액", format="%d")
        })
    if st.button("💾 편집 내용 저장"):
        edited['구분'] = edited['용도'].map(cat_map).fillna(edited['구분'])
        st.session_state.master_df = edited
        save_history(edited); st.session_state.needs_download = True; st.rerun()

with tabs[-1]: # 카테고리 설정
    st.subheader("⚙️ 용도 및 계산 방식 설정")
    edited_cat = st.data_editor(st.session_state.cat_df, num_rows="dynamic", use_container_width=True,
        column_config={"연결구분": st.column_config.SelectboxColumn("구분 방식", options=["수익", "비용", "-"], required=True)})
    if st.button("🛠 설정 반영하기"):
        st.session_state.cat_df = edited_cat
        cat_map = edited_cat.set_index("항목명")["연결구분"].to_dict()
        st.session_state.master_df['구분'] = st.session_state.master_df['용도'].map(cat_map).fillna(st.session_state.master_df['구분'])
        st.success("카테고리 설정 및 기존 데이터 업데이트 완료!"); st.rerun()

# 리포트 및 상세 탭 생략(기존 로직 유지)
