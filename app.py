import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="고시원 정산 프로그램", layout="wide")

# 금액 정리 함수
def clean_amt(x):
    try:
        if pd.isna(x): return 0
        if isinstance(x, str):
            return int(x.replace(',', '').split('.')[0])
        return int(x)
    except:
        return 0

# 자동 카테고리 함수
def auto_categorize(content, income, outcome):
    if income > 0: return "수익", "입실료"
    content = str(content)
    if any(k in content for k in ['전기', '수도', '예스코', '가스', '한전']): return "비용", "공과금"
    if any(k in content for k in ['쌀', '라면', '우유', '커피', '식료']): return "비용", "식품"
    if any(k in content for k in ['다이소', '비품', '세제', '휴지', '점보롤']): return "비용", "비품"
    if '임대료' in content: return "비용", "임대료"
    return "비용", "기타"

st.title("🏠 고시원 월별 통합 정산 시스템")

# 사이드바 파일 업로드 (xls 추가)
st.sidebar.header("파일 업로드")
bank_file = st.sidebar.file_uploader("우리은행 거래내역 (XLS 또는 CSV)", type=['csv', 'xls', 'xlsx'])
coupang_file = st.sidebar.file_uploader("쿠팡 구매내역 (CSV)", type=['csv'])

if bank_file and coupang_file:
    # 은행 데이터 읽기 (파일 확장자에 따라 다르게 처리)
    try:
        if bank_file.name.endswith('.csv'):
            bank_df = pd.read_csv(bank_file, skiprows=3)
        else:
            # 우리은행 XLS 파일은 보통 4번째 줄부터 데이터가 시작됩니다.
            bank_df = pd.read_excel(bank_file, skiprows=3)
    except Exception as e:
        st.error(f"은행 파일을 읽는 중 오류가 발생했습니다: {e}")
        st.stop()

    # 쿠팡 데이터 읽기
    coupang_df = pd.read_csv(coupang_file)
    
    combined_list = []

    # 은행 데이터 처리
    for _, row in bank_df.iterrows():
        # 우리은행 열 이름에 맞춰서 데이터 추출
        in_amt = clean_amt(row.get('맡기신금액', 0))
        out_amt = clean_amt(row.get('찾으신금액', 0))
        
        if "쿠팡" in str(row.get('적요', '')): continue
        
        content = str(row.get('기재내용', '')) + " " + str(row.get('적요', ''))
        gubun, yongdo = auto_categorize(content, in_amt, out_amt)
        
        combined_list.append({
            "연도": str(row.get('거래일시', ''))[:4],
            "날짜": str(row.get('거래일시', ''))[5:10].replace('.', '/'),
            "내용": content.strip(),
            "용도": yongdo,
            "구분": gubun,
            "금액": in_amt if gubun == "수익" else out_amt,
            "대구분": in_amt if gubun == "수익" else -out_amt,
            "비고": row.get('적요', '')
        })

    # 쿠팡 데이터 처리
    for _, row in coupang_df.iterrows():
        price = clean_amt(row.get('총결제금액(원)', 0))
        _, yongdo = auto_categorize(row.get('상품명', ''), 0, price)
        
        combined_list.append({
            "연도": str(row.get('주문일', ''))[:4],
            "날짜": str(row.get('주문일', ''))[6:11].replace('. ', '/'),
            "내용": row.get('상품명', ''),
            "용도": yongdo,
            "구분": "비용",
            "금액": price,
            "대구분": -price,
            "비고": "쿠팡구매"
        })

    final_df = pd.DataFrame(combined_list)

    # 데이터 수정 및 차트 출력 부분 (기존과 동일)
    st.subheader("📋 전체 데이터 정리 및 수정")
    edited_df = st.data_editor(final_df, use_container_width=True, num_rows="dynamic")

    col1, col2 = st.columns(2)
    with col1:
        summary = edited_df.groupby('구분')['금액'].sum().reset_index()
        st.plotly_chart(px.bar(summary, x='구분', y='금액', color='구분', text_auto=',.0f'), use_container_width=True)
    with col2:
        exp_df = edited_df[edited_df['구분'] == '비용']
        st.plotly_chart(px.pie(exp_df, values='금액', names='용도', hole=0.4), use_container_width=True)

    csv = edited_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("💾 최종 장부 저장", csv, "고시원_최종장부.csv", "text/csv")
