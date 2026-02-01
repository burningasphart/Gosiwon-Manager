import streamlit as st
import pandas as pd
import plotly.express as px
import io

st.set_page_config(page_title="고시원 정산 시스템", layout="wide")

# 숫자 정제: 문자열에서 숫자만 추출 (콤마, 원화기호 등 완벽 제거)
def clean_amt(x):
    try:
        if pd.isna(x): return 0
        s = "".join(filter(str.isdigit, str(x).split('.')[0]))
        return int(s) if s else 0
    except:
        return 0

# 자동 카테고리 로직 (대표님 분류 기준)
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
    # --- 1. 은행 데이터 읽기 (강력한 예외 처리) ---
    bank_df = None
    try:
        if bank_file.name.endswith('.csv'):
            # CSV의 경우 다양한 인코딩 시도
            try:
                bank_df = pd.read_csv(bank_file, encoding='utf-8-sig')
            except:
                bank_file.seek(0)
                bank_df = pd.read_csv(bank_file, encoding='cp949')
        else:
            # XLS/XLSX의 경우 (HTML 방식 포함)
            try:
                bank_file.seek(0)
                dfs = pd.read_html(bank_file)
                bank_df = max(dfs, key=len) # 가장 표다운 것을 선택
            except:
                bank_file.seek(0)
                bank_df = pd.read_excel(bank_file)

        # 진짜 제목 줄(Header) 찾기
        header_idx = None
        for i in range(len(bank_df)):
            row_str = bank_df.iloc[i].astype(str).tolist()
            if any('거래일시' in s or '적요' in s for s in row_str):
                header_idx = i
                break
        
        if header_idx is not None:
            bank_df.columns = bank_df.iloc[header_idx]
            bank_df = bank_df.iloc[header_idx+1:].reset_index(drop=True)
        
        # 열 이름 정리 (공백 제거)
        bank_df.columns = [str(c).strip() for c in bank_df.columns]
        # 데이터 없는 행 삭제
        bank_df = bank_df.dropna(subset=[bank_df.columns[1]]) 

    except Exception as e:
        st.error(f"은행 파일 분석 중 오류가 발생했습니다. (에러: {e})")
        st.stop()

    # --- 2. 쿠팡 데이터 읽기 ---
    try:
        coupang_file.seek(0)
        coupang_df = pd.read_csv(coupang_file, encoding='utf-8-sig')
    except:
        coupang_file.seek(0)
        coupang_df = pd.read_csv(coupang_file, encoding='cp949')
    
    combined_list = []

    # --- 3. 은행 데이터 처리 (위치 기반으로 더 안전하게) ---
    cols = list(bank_df.columns)
    def find_col(keywords):
        for i, c in enumerate(cols):
            if any(k in str(c) for k in keywords): return i
        return -1

    idx_date = find_col(['일시'])
    idx_sum = find_col(['적요'])
    idx_memo = find_col(['기재', '내용'])
    idx_out = find_col(['찾으신'])
    idx_in = find_col(['맡기신'])

    for _, row in bank_df.iterrows():
        # 필수 데이터가 없는 경우 건너뜀
        if idx_date == -1: continue
        
        v_in = clean_amt(row.iloc[idx_in]) if idx_in != -1 else 0
        v_out = clean_amt(row.iloc[idx_out]) if idx_out != -1 else 0
        v_sum = str(row.iloc[idx_sum]) if idx_sum != -1 else ""
        v_memo = str(row.iloc[idx_memo]) if idx_memo != -1 else ""
        v_date = str(row.iloc[idx_date])

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

    # --- 4. 쿠팡 데이터 처리 ---
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

    # --- 5. 결과 출력 및 대시보드 ---
    st.subheader("📋 통합 장부 정리 (대표님 전용)")
    edited_df = st.data_editor(final_df, use_container_width=True, num_rows="dynamic")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📊 수입 vs 비용")
        st.plotly_chart(px.bar(edited_df.groupby('구분')['금액'].sum().reset_index(), x='구분', y='금액', color='구분', text_auto=',.0f'), use_container_width=True)
    with c2:
        st.subheader("💸 항목별 지출 비중")
        st.plotly_chart(px.pie(edited_df[edited_df['구분']=='비용'], values='금액', names='용도', hole=0.4), use_container_width=True)

    st.download_button("💾 결과 저장(CSV)", edited_df.to_csv(index=False).encode('utf-8-sig'), "고시원_정산_결과.csv", "text/csv")

else:
    st.info("대표님, 왼쪽 사이드바에서 은행과 쿠팡 파일을 업로드해 주세요.")
