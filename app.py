import streamlit as st
import pandas as pd
import plotly.express as px
import io

st.set_page_config(page_title="고시원 정산 시스템", layout="wide")

# 숫자 정리: 문자열에서 숫자만 추출
def clean_amt(x):
    try:
        if pd.isna(x): return 0
        s = str(x).replace(',', '').replace('₩', '').split('.')[0]
        s = "".join(filter(str.isdigit, s))
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
    if '인건비' in content: return "비용", "인건비"
    return "비용", "기타"

st.title("🏠 고시원 통합 정산 시스템 (대표님 전용)")

st.sidebar.header("📁 파일 업로드")
bank_file = st.sidebar.file_uploader("우리은행 거래내역 (XLS/CSV)", type=['csv', 'xls', 'xlsx'])
coupang_file = st.sidebar.file_uploader("쿠팡 구매내역 (CSV)", type=['csv'])

if bank_file and coupang_file:
    # --- 은행 데이터 읽기 ---
    try:
        if bank_file.name.endswith('.csv'):
            bank_df = pd.read_csv(bank_file, skiprows=3)
        else:
            bank_file.seek(0)
            # 우리은행 특수 XLS(HTML형식) 대응
            html_list = pd.read_html(bank_file)
            bank_df = html_list[0]
            
            # 실제 데이터가 시작되는 위치 찾기 (거래일시라는 글자가 있는 행 찾기)
            header_idx = 0
            for i, row in bank_df.iterrows():
                if row.astype(str).str.contains('거래일시').any():
                    header_idx = i
                    break
            bank_df.columns = bank_df.iloc[header_idx]
            bank_df = bank_df.iloc[header_idx+1:].reset_index(drop=True)
            
    except Exception as e:
        st.error(f"은행 파일 읽기 실패. 엑셀에서 CSV로 저장 후 다시 시도해 보세요. (에러: {e})")
        st.stop()

    # --- 쿠팡 데이터 읽기 ---
    coupang_df = pd.read_csv(coupang_file)
    combined_list = []

    # --- 은행 데이터 처리 (이름 대신 '위치'로 찾기) ---
    cols = bank_df.columns.tolist()
    
    # 각 데이터가 몇 번째 칸에 있는지 자동으로 확인
    idx_date = next((i for i, c in enumerate(cols) if '일시' in str(c)), 1)
    idx_summary = next((i for i, c in enumerate(cols) if '적요' in str(c)), 2)
    idx_memo = next((i for i, c in enumerate(cols) if '기재' in str(c)), 3)
    idx_out = next((i for i, c in enumerate(cols) if '찾으신' in str(c)), 4)
    idx_in = next((i for i, c in enumerate(cols) if '맡기신' in str(c)), 5)

    for _, row in bank_df.iterrows():
        val_in = clean_amt(row.iloc[idx_in])
        val_out = clean_amt(row.iloc[idx_out])
        val_summary = str(row.iloc[idx_summary])
        val_memo = str(row.iloc[idx_memo])
        val_date = str(row.iloc[idx_date])

        if "쿠팡" in val_summary: continue # 중복 방지
        
        content = (val_memo + " " + val_summary).strip()
        gubun, yongdo = auto_categorize(content, val_in, val_out)
        
        combined_list.append({
            "연도": val_date[:4] if len(val_date)>4 else "2026",
            "날짜": val_date[5:10].replace('.', '/') if len(val_date)>10 else "",
            "내용": content,
            "용도": yongdo,
            "구분": gubun,
            "금액": val_in if gubun == "수익" else val_out,
            "대구분": val_in if gubun == "수익" else -val_out,
            "비고": val_summary
        })

    # --- 쿠팡 데이터 처리 ---
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

    # --- 테이블 편집 및 차트 ---
    st.subheader("📋 통합 데이터 정리 및 수정")
    edited_df = st.data_editor(final_df, use_container_width=True, num_rows="dynamic")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📊 수입 vs 지출")
        st.plotly_chart(px.bar(edited_df.groupby('구분')['금액'].sum().reset_index(), x='구분', y='금액', color='구분', text_auto=',.0f'), use_container_width=True)
    with c2:
        st.subheader("🍕 지출 항목 비중")
        st.plotly_chart(px.pie(edited_df[edited_df['구분']=='비용'], values='금액', names='용도', hole=0.4), use_container_width=True)

    st.download_button("💾 최종 장부 저장(Excel용)", edited_df.to_csv(index=False).encode('utf-8-sig'), "고시원_정산_결과.csv", "text/csv")

else:
    st.info("대표님, 왼쪽 사이드바에서 파일을 업로드해 주세요.")
