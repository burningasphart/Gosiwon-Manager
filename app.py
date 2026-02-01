import streamlit as st
import pandas as pd
import plotly.express as px
import io

st.set_page_config(page_title="고시원 정산 프로그램", layout="wide")

# 숫자 정리 함수
def clean_amt(x):
    try:
        if pd.isna(x): return 0
        if isinstance(x, str):
            # 숫자 외의 문자 제거 (원화기호, 콤마 등)
            s = "".join(filter(str.isdigit, x.split('.')[0]))
            return int(s) if s else 0
        return int(x)
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
    if '인건비' in content: return "비용", "인건비"
    return "비용", "기타"

st.title("🏠 고시원 통합 정산 시스템 (대표님 전용)")

st.sidebar.header("📁 파일 업로드")
bank_file = st.sidebar.file_uploader("우리은행 거래내역 (XLS/CSV)", type=['csv', 'xls', 'xlsx'])
coupang_file = st.sidebar.file_uploader("쿠팡 구매내역 (CSV)", type=['csv'])

if bank_file and coupang_file:
    # --- 은행 데이터 읽기 (강화된 방식) ---
    try:
        if bank_file.name.endswith('.csv'):
            bank_df = pd.read_csv(bank_file, skiprows=3)
        else:
            try:
                # 1안: 일반 엑셀 방식
                bank_df = pd.read_excel(bank_file, skiprows=3)
            except:
                # 2안: 우리은행 특유의 HTML형식 XLS 방식
                bank_file.seek(0)
                html_data = pd.read_html(bank_file)
                bank_df = html_data[0]
                # 헤더가 밀린 경우 보정
                if '거래일시' not in bank_df.columns:
                    bank_df.columns = bank_df.iloc[3]
                    bank_df = bank_df.iloc[4:]
    except Exception as e:
        st.error(f"은행 파일 구조 분석 실패. 엑셀을 열어서 'CSV'로 저장 후 올려주세요. 에러: {e}")
        st.stop()

    # --- 쿠팡 데이터 읽기 ---
    coupang_df = pd.read_csv(coupang_file)
    
    combined_list = []

    # 은행 내역 처리
    for _, row in bank_df.iterrows():
        row_dict = row.to_dict()
        # 열 이름에 공백이 있거나 미세하게 다를 경우를 대비
        def get_val(keywords):
            for k in row_dict.keys():
                if any(kw in str(k) for kw in keywords): return row_dict[k]
            return 0

        in_amt = clean_amt(get_val(['맡기신']))
        out_amt = clean_amt(get_val(['찾으신']))
        summary = str(get_val(['적요']))
        memo = str(get_val(['기재내용']))
        date_val = str(get_val(['거래일시']))

        if "쿠팡" in summary: continue
        
        content = (memo + " " + summary).strip()
        gubun, yongdo = auto_categorize(content, in_amt, out_amt)
        
        combined_list.append({
            "연도": date_val[:4] if len(date_val)>4 else "2026",
            "날짜": date_val[5:10].replace('.', '/') if len(date_val)>10 else "",
            "내용": content,
            "용도": yongdo,
            "구분": gubun,
            "금액": in_amt if gubun == "수익" else out_amt,
            "대구분": in_amt if gubun == "수익" else -out_amt,
            "비고": summary
        })

    # 쿠팡 내역 처리
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

    # --- 화면 출력 및 수정 ---
    st.subheader("📋 통합 데이터 정리 및 수정")
    st.info("💡 표의 칸을 클릭해 내용을 수정할 수 있습니다.")
    edited_df = st.data_editor(final_df, use_container_width=True, num_rows="dynamic")

    # --- 분석 대시보드 ---
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📊 수입 vs 지출")
        st.plotly_chart(px.bar(edited_df.groupby('구분')['금액'].sum().reset_index(), x='구분', y='금액', color='구분'), use_container_width=True)
    with c2:
        st.subheader("🍕 지출 항목 비중")
        st.plotly_chart(px.pie(edited_df[edited_df['구분']=='비용'], values='금액', names='용도', hole=0.4), use_container_width=True)

    # --- 저장 버튼 ---
    st.download_button("💾 최종 장부 저장(CSV)", edited_df.to_csv(index=False).encode('utf-8-sig'), "고시원_정산_결과.csv", "text/csv")

else:
    st.warning("왼쪽 사이드바에서 파일을 업로드해 주세요.")
