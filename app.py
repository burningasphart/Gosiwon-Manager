import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="고시원 정산 프로그램", layout="wide")

# 1. 원장님 기존 카테고리 로직 함수
def auto_categorize(content, income, outcome):
    if income > 0: return "수익", "입실료"
    content = str(content)
    if any(k in content for k in ['전기', '수도', '예스코', '가스', '한전']): return "비용", "공과금"
    if any(k in content for k in ['쌀', '라면', '우유', '커피', '식사']): return "비용", "식품"
    if any(k in content for k in ['다이소', '비품', '세제', '휴지', '점보롤']): return "비용", "비품"
    if '임대료' in content: return "비용", "임대료"
    if '인건비' in content: return "비용", "인건비"
    return "비용", "기타"

# 2. 메인 화면
st.title("🏠 고시원 월별 통합 정산 시스템")
st.markdown("우리은행 엑셀과 쿠팡 내역을 올리면 자동으로 장부를 정리합니다.")

# 사이드바 파일 업로드
st.sidebar.header("파일 업로드")
bank_file = st.sidebar.file_uploader("우리은행 거래내역 (CSV)", type=['csv'])
coupang_file = st.sidebar.file_uploader("쿠팡 구매내역 (CSV)", type=['csv'])

if bank_file and coupang_file:
    # 데이터 로딩
    bank_df = pd.read_csv(bank_file, skiprows=3)
    coupang_df = pd.read_csv(coupang_file)
    
    combined_list = []

    # 은행 데이터 변환
    for _, row in bank_df.iterrows():
        in_amt = int(str(row['맡기신금액']).replace(',', '').split('.')[0]) if pd.notna(row['맡기신금액']) else 0
        out_amt = int(str(row['찾으신금액']).replace(',', '').split('.')[0]) if pd.notna(row['찾으신금액']) else 0
        
        # 쿠팡 결제액은 중복 방지를 위해 제외
        if "쿠팡" in str(row['적요']): continue
        
        gubun, yongdo = auto_categorize(str(row['적요'])+str(row['기재내용']), in_amt, out_amt)
        
        combined_list.append({
            "연도": str(row['거래일시'])[:4],
            "날짜": str(row['거래일시'])[5:10].replace('.', '/'),
            "내용": row['기재내용'] if pd.notna(row['기재내용']) else row['적요'],
            "용도": yongdo,
            "구분": gubun,
            "금액": in_amt if in_amt > 0 else out_amt,
            "대구분": in_amt if in_amt > 0 else -out_amt,
            "비고": row['적요']
        })

    # 쿠팡 데이터 변환
    for _, row in coupang_df.iterrows():
        price = int(str(row['총결제금액(원)']).replace(',', ''))
        _, yongdo = auto_categorize(row['상품명'], 0, price)
        
        combined_list.append({
            "연도": str(row['주문일'])[:4],
            "날짜": str(row['주문일'])[6:11].replace('. ', '/'),
            "내용": row['상품명'],
            "용도": yongdo,
            "구분": "비용",
            "금액": price,
            "대구분": -price,
            "비고": "쿠팡구매"
        })

    final_df = pd.DataFrame(combined_list)

    # 3. 데이터 수정 및 정리 (Table)
    st.subheader("📋 전체 데이터 정리 및 수정")
    st.caption("표의 칸을 클릭해서 내용을 직접 수정할 수 있습니다. 수정한 내용은 아래 차트에 바로 반영됩니다.")
    edited_df = st.data_editor(final_df, use_container_width=True, num_rows="dynamic")

    # 4. 분석 리포트 (Dashboard)
    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("💰 수익 및 지출 현황")
        summary = edited_df.groupby('구분')['금액'].sum().reset_index()
        fig_bar = px.bar(summary, x='구분', y='금액', color='구분', text_auto=',.0f')
        st.plotly_chart(fig_bar, use_container_width=True)

    with col2:
        st.subheader("💸 지출 카테고리 분석")
        exp_df = edited_df[edited_df['구분'] == '비용']
        fig_pie = px.pie(exp_df, values='금액', names='용도', hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

    # 엑셀 다운로드
    csv = edited_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("💾 최종 장부 엑셀로 저장하기", csv, "고시원_정산_최종.csv", "text/csv")