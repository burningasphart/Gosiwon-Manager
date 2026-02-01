import streamlit as st
import pandas as pd
import plotly.express as px
import io

st.set_page_config(page_title="고시원 통합 정산", layout="wide")

# 숫자 정제 함수: 콤마와 문자 제거 후 숫자로 변환
def clean_amt(x):
    try:
        if pd.isna(x): return 0
        s = str(x).replace(',', '').replace('₩', '').split('.')[0]
        s = "".join(filter(str.isdigit, s))
        return int(s) if s else 0
    except:
        return 0

# 자동 카테고리 로직 (대표님 맞춤형)
def auto_categorize(content, income, outcome):
    if income > 0: return "수익", "입실료"
    content = str(content)
    if any(k in content for k in ['전기', '수도', '예스코', '가스', '한전', '공과금']): return "비용", "공과금"
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
    # --- 1. 우리은행 데이터 읽기 (대표님 양식 맞춤형) ---
    try:
        if bank_file.name.endswith('.csv'):
            bank_df = pd.read_csv(bank_file, skiprows=3)
        else:
            bank_file.seek(0)
            try:
                # 우리은행 전용 HTML-XLS 방식 시도
                html_list = pd.read_html(bank_file)
                bank_df = html_list[0]
            except:
                # 일반 엑셀 방식 시도
                bank_file.seek(0)
                bank_df = pd.read_excel(bank_file)

        # '거래일시' 글자가 들어있는 줄을 찾아서 헤더로 설정
        header_row = 0
        for i in range(len(bank_df)):
            if '거래일시' in str(bank_df.iloc[i].values):
                header_row = i
                break
        
        bank_df.columns = bank_df.iloc[header_row]
        bank_df = bank_df.iloc[header_row+1:].reset_index(drop=True)
        # 데이터가 없는 빈 줄 삭제
        bank_df = bank_df.dropna(subset=['거래일시'])

    except Exception as e:
        st.error(f"은행 파일을 읽지 못했습니다. 에러: {e}")
        st.stop()

    # --- 2. 쿠팡 데이터 읽기 ---
    coupang_df = pd.read_csv(coupang_file)
    combined_list = []

    # --- 3. 은행 데이터 정리 ---
    for _, row in bank_df.iterrows():
        # 열 이름을 정확히 매칭 (앞뒤 공백 제거)
        row.index = row.index.str.strip()
        
        v_in = clean_amt(row.get('맡기신금액', 0))
        v_out = clean_amt(row.get('찾으신금액', 0))
        v_sum = str(row.get('적요', ''))
        v_memo = str(row.get('기재내용', ''))
        v_date = str(row.get('거래일시', ''))

        if "쿠팡" in v_sum or "쿠팡" in v_memo: continue
        
        content = (v_memo + " " + v_sum).strip()
        gubun, yongdo = auto_categorize(content, v_in, v_out)
        
        if v_in == 0 and v_out == 0: continue

        combined_list.append({
            "연도": v_date[:4] if len(v_date)>=4 else "2026",
            "날짜": v_date[5:10].replace('.', '/'),
            "내용": content,
            "용도": yongdo,
            "구분": gubun,
            "금액": v_in if gubun == "수익" else v_out,
            "대구분": v_in if gubun == "수익" else -v_out,
            "비고": v_sum
        })

    # --- 4. 쿠팡 데이터 정리 ---
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

    # --- 5. 화면 출력 (테이블 및 차트) ---
    st.subheader("📋 통합 장부 정리 (대표님 전용)")
    st.info("💡 대표님, 수정이 필요한 내용은 표에서 바로 클릭하여 고칠 수 있습니다.")
    edited_df = st.data_editor(final_df, use_container_width=True, num_rows="dynamic")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📊 수익 vs 비용 현황")
        st.plotly_chart(px.bar(edited_df.groupby('구분')['금액'].sum().reset_index(), x='구분', y='금액', color='구분', text_auto=',.0f'), use_container_width=True)
    with c2:
        st.subheader("💸 항목별 지출 비중")
        st.plotly_chart(px.pie(edited_df[edited_df['구분']=='비용'], values='금액', names='용도', hole=0.4), use_container_width=True)

    st.download_button("💾 최종 결과 저장(CSV)", edited_df.to_csv(index=False).encode('utf-8-sig'), "고시원_정산_결과.csv", "text/csv")
else:
    st.info("대표님, 왼쪽에서 은행 파일과 쿠팡 파일을 업로드해 주세요.")
