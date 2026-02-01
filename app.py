import streamlit as st
import pandas as pd
import plotly.express as px
import time

st.set_page_config(page_title="고시원 누적 정산 시스템", layout="wide")

# 숫자 정제 함수
def clean_amt(x):
    try:
        if pd.isna(x) or x == "": return 0
        s = "".join(filter(str.isdigit, str(x).split('.')[0]))
        return int(s) if s else 0
    except:
        return 0

# 자동 카테고리 로직
def auto_categorize(content, income, outcome):
    if income > 0: return "수익", "입실료"
    content = str(content)
    if any(k in content for k in ['전기', '수도', '예스코', '가스', '한전']): return "비용", "공과금"
    if any(k in content for k in ['쌀', '라면', '우유', '커피', '식료', '아몬드']): return "비용", "식품"
    if any(k in content for k in ['다이소', '비품', '세제', '휴지', '점보롤', '타월']): return "비용", "비품"
    if '임대료' in content: return "비용", "임대료"
    if '보증금' in content: return "비용", "보증금"
    return "비용", "기타"

st.title("🏠 고시원 누적 정산 시스템 (대표님 전용)")

# --- 세션 상태 보존 ---
if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame(columns=["연도", "월", "날짜", "내용", "용도", "구분", "금액", "비고"])
if 'needs_download' not in st.session_state:
    st.session_state.needs_download = False

# --- 사이드바: 데이터 업로드 ---
st.sidebar.header("📂 1. 기존 기록 (있을 때만)")
prev_master = st.sidebar.file_uploader("과거 장부 파일(.csv)", type=['csv'])

if st.sidebar.button("과거 기록 불러오기") and prev_master:
    st.session_state.master_df = pd.read_csv(prev_master)
    st.sidebar.success("과거 기록 로드 완료")

st.sidebar.divider()
st.sidebar.header("📂 2. 이번 달 새 데이터")
bank_file = st.sidebar.file_uploader("우리은행 거래내역", type=['csv', 'xls', 'xlsx'])
coupang_file = st.sidebar.file_uploader("쿠팡 구매내역", type=['csv'])

if st.sidebar.button("📦 새 데이터 정리/합치기"):
    if bank_file and coupang_file:
        try:
            # 은행 데이터 로직
            if bank_file.name.endswith('.csv'):
                bank_df = pd.read_csv(bank_file, skiprows=3)
            else:
                bank_file.seek(0)
                html_list = pd.read_html(bank_file)
                bank_df = max(html_list, key=len)
                header_row = 0
                for i in range(min(15, len(bank_df))):
                    if '거래일시' in str(bank_df.iloc[i].values):
                        header_row = i
                        break
                bank_df.columns = bank_df.iloc[header_row]
                bank_df = bank_df.iloc[header_row+1:].reset_index(drop=True)
            
            coupang_file.seek(0)
            coupang_df = pd.read_csv(coupang_file)
            
            new_rows = []
            # 은행 처리
            for _, row in bank_df.iterrows():
                v_in, v_out = clean_amt(row.get('맡기신금액', 0)), clean_amt(row.get('찾으신금액', 0))
                v_sum, v_memo, v_date = str(row.get('적요', '')), str(row.get('기재내용', '')), str(row.get('거래일시', ''))
                if "쿠팡" in v_sum or "쿠팡" in v_memo or pd.isna(row.get('거래일시')) or v_date == 'nan': continue
                content = (v_memo + " " + v_sum).strip()
                gubun, yongdo = auto_categorize(content, v_in, v_out)
                new_rows.append({"연도": v_date[:4], "월": v_date[5:7], "날짜": v_date[5:10], "내용": content, "용도": yongdo, "구분": gubun, "금액": v_in if gubun=="수익" else v_out, "비고": v_sum})
            
            # 쿠팡 처리
            for _, row in coupang_df.iterrows():
                price = clean_amt(row.get('총결제금액(원)', 0))
                if price == 0: continue
                _, yongdo = auto_categorize(row.get('상품명', ''), 0, price)
                new_rows.append({"연도": str(row.get('주문일', ''))[:4], "월": str(row.get('주문일', ''))[6:8], "날짜": str(row.get('주문일', ''))[6:11], "내용": row.get('상품명', ''), "용도": yongdo, "구분": "비용", "금액": price, "비고": "쿠팡구매"})
            
            new_df = pd.DataFrame(new_rows)
            
            # 기존 기록이 비어있으면 새 데이터만, 있으면 합치기
            if st.session_state.master_df.empty:
                st.session_state.master_df = new_df
            else:
                combined = pd.concat([st.session_state.master_df, new_df]).drop_duplicates(subset=['날짜', '내용', '금액'], keep='first')
                st.session_state.master_df = combined
            
            st.session_state.needs_download = True
            st.sidebar.success("정리가 완료되었습니다!")
        except Exception as e:
