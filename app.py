import streamlit as st
import pandas as pd
import plotly.express as px
import time
import re

st.set_page_config(page_title="고시원 누적 정산 시스템", layout="wide")

# 숫자 정제 함수
def clean_amt(x):
    try:
        if pd.isna(x) or str(x).strip() == "": return 0
        s = "".join(filter(str.isdigit, str(x).split('.')[0]))
        return int(s) if s else 0
    except:
        return 0

# 날짜 정제 함수 (대표님 요청 사항: 날짜 이상한 것 수정)
def clean_date(date_val):
    try:
        d = str(date_val).strip()
        # 숫자와 구분자(. / -)만 남기기
        d = re.sub(r'[^0-9./-]', ' ', d).split()[0] 
        # 구분자 통일
        d = d.replace('.', '-').replace('/', '-')
        
        # 연도-월-일 추출
        parts = d.split('-')
        if len(parts) >= 3:
            year = parts[0]
            month = parts[1].zfill(2)
            day = parts[2].zfill(2)
            return f"{year}", f"{month}", f"{month}-{day}"
        return "0000", "00", "00-00"
    except:
        return "0000", "00", "00-00"

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

if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame(columns=["연도", "월", "날짜", "내용", "용도", "구분", "금액", "비고"])
if 'needs_download' not in st.session_state:
    st.session_state.needs_download = False

# --- 사이드바 ---
st.sidebar.header("📂 1. 기존 기록 불러오기")
prev_master = st.sidebar.file_uploader("과거 장부 파일(.csv)", type=['csv'])

if st.sidebar.button("과거 기록 불러오기") and prev_master:
    try:
        st.session_state.master_df = pd.read_csv(prev_master)
        st.sidebar.success("과거 기록 로드 완료")
    except Exception as e:
        st.sidebar.error(f"파일 읽기 오류: {e}")

st.sidebar.divider()
st.sidebar.header("📂 2. 이번 달 새 데이터")
bank_file = st.sidebar.file_uploader("우리은행 거래내역", type=['csv', 'xls', 'xlsx'])
coupang_file = st.sidebar.file_uploader("쿠팡 구매내역", type=['csv'])

if st.sidebar.button("📦 새 데이터 정리/합치기"):
    if bank_file and coupang_file:
        try:
            if bank_file.name.endswith('.csv'):
                bank_df = pd.read_csv(bank_file, skiprows=3)
            else:
                bank_file.seek(0)
                try:
                    html_list = pd.read_html(bank_file)
                    bank_df = max(html_list, key=len)
                except:
                    bank_file.seek(0)
                    bank_df = pd.read_excel(bank_file)

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
            for _, row in bank_df.iterrows():
                raw_date = row.get('거래일시')
                if pd.isna(raw_date): continue
                
                year, month, day_str = clean_date(raw_date) # 날짜 보정 적용
                if year == "0000": continue

                v_in, v_out = clean_amt(row.get('맡기신금액', 0)), clean_amt(row.get('찾으신금액', 0))
                v_sum, v_memo = str(row.get('적요', '')), str(row.get('기재내용', ''))
                
                if "쿠팡" in v_sum or "쿠팡" in v_memo: continue
                content = (v_memo + " " + v_sum).strip()
                gubun, yongdo = auto_categorize(content, v_in, v_out)
                if v_in == 0 and v_out == 0: continue
                
                new_rows.append({"연도": year, "월": month, "날짜": day_str, "내용": content, "용도": yongdo, "구분": gubun, "금액": v_in if gubun=="수익" else v_out, "비고": v_sum})
            
            for _, row in coupang_df.iterrows():
                price = clean_amt(row.get('총결제금액(원)', 0))
                if price == 0: continue
                _, yongdo = auto_categorize(row.get('상품명', ''), 0, price)
                year, month, day_str = clean_date(row.get('주문일', '')) # 날짜 보정 적용
                new_rows.append({"연도": year, "월": month, "날짜": day_str, "내용": row.get('상품명', ''), "용도": yongdo, "구분": "비용", "금액": price, "비고": "쿠팡구매"})
            
            new_df = pd.DataFrame(new_rows)
            if st.session_state.master_df.empty:
                st.session_state.master_df = new_df
            else:
                st.session_state.master_df = pd.concat([st.session_state.master_df, new_df]).drop_duplicates(subset=['날짜', '내용', '금액'], keep='first')
            
            st.session_state.needs_download = True
            st.sidebar.success("날짜 보정 및 정리 완료!")
        except Exception as e:
            st.sidebar.error(f"오류: {e}")
    else:
        st.sidebar.warning("파일을 먼저 올려주세요.")

# (이후 저장 알림 및 대시보드 코드는 이전과 동일)
if st.session_state.needs_download:
    st.warning("⚠️ 장부에 변경사항이 있습니다. 저장하시겠습니까?")
    st.download_button(label="✅ 지금 파일로 저장", data=st.session_state.master_df.to_csv(index=False).encode('utf-8-sig'), file_name=f"고시원_장부_{time.strftime('%Y%m%d')}.csv", mime="text/csv", on_click=lambda: st.session_state.update({"needs_download": False}))

df = st.session_state.master_df
if not df.empty:
    all_months = sorted(df['월'].unique())
    tabs = st.tabs(["📊 통합 리포트"] + [f"📅 {m}월 상세" for m
