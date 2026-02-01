import streamlit as st
import pandas as pd
import plotly.express as px
import io

st.set_page_config(page_title="고시원 통합 정산", layout="wide")

# 숫자 정제 함수 (모든 특수문자 제거)
def clean_amt(x):
    try:
        if pd.isna(x): return 0
        s = "".join(filter(str.isdigit, str(x).split('.')[0]))
        return int(s) if s else 0
    except:
        return 0

# 자동 카테고리 로직
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
    # --- 은행 데이터 읽기 (무적 버전) ---
    try:
        if bank_file.name.endswith('.csv'):
            bank_df = pd.read_csv(bank_file, skiprows=3)
        else:
            try:
                # 방법 1: HTML 방식 (우리은행 전용)
                bank_file.seek(0)
                dfs = pd.read_html(bank_file)
                # 데이터가 가장 많은 표 선택
                bank_df = max(dfs, key=len)
            except:
                # 방법 2: 일반 엑셀 방식
                bank_file.seek(0)
                bank_df = pd.read_excel(bank_file)

        # 헤더 자동 찾기: '거래일시' 또는 '일시'라는 글자가 있는 행을 헤더로 설정
        header_row = 0
        for i in range(len(bank_df)):
            row_str = bank_df.iloc[i].astype(str).values
            if any('거래일시' in s or '일시' in s for s in row_str):
                header_row = i
                break
        
        bank_df.columns = bank_df.iloc[header_row]
        bank_df = bank_df.iloc[header_row+1:].reset_index(drop=True)
        # 빈 줄 제거
        bank_df = bank_df.dropna(how='all', subset=[bank_df.columns[1]])

    except Exception as e:
        st.error(f"은행 파일 로딩 실패. 엑셀을 열어 CSV로 저장 후 올려보세요. (에러: {e})")
        st.stop()

    # --- 쿠팡 데이터 읽기 ---
    coupang_df = pd.read_csv(coupang_file)
    combined_list = []

    # --- 은행 처리 (열 위치 기반) ---
    cols = list(bank_df.columns)
    
    # 위치 찾기 (없으면 기본값 설정)
    def find_idx(keywords, default):
        for i, c in enumerate(cols):
            if any(k in str(c) for k in keywords): return i
        return default

    idx_date = find_idx(['일시'], 1)
    idx_summary = find_idx(['적요'], 2)
    idx_memo = find_idx(['기재', '내용'], 3)
    idx_out = find_idx(['찾으신', '지출'], 4)
    idx_in = find_idx(['맡기신', '수입'], 5)

    for _, row in bank_df.iterrows():
        try:
            v_in = clean_amt(row.iloc[idx_in])
            v_out = clean_amt(row.iloc[idx_out])
            v_sum = str(row.iloc[idx_summary])
            v_memo = str(row.iloc[idx_memo])
            v_date = str(row.iloc[idx_date])
            
            if "쿠팡" in v_sum or "쿠팡" in v_memo: continue
            
            content = (v_memo + " " + v_sum).strip()
            gubun, yongdo = auto_categorize(content, v_in, v_out)
            
            if v_in == 0 and v_out == 0: continue # 금액 없는 행 패스

            combined_list.append({
                "연도": v_date[:4] if len(v_date)>=4 else "2026",
                "날짜": v_date[5:10].replace('.', '/') if len(v_date)>=10 else "",
                "내용": content,
                "용도": yongdo,
                "구분": gubun,
                "금액": v_in if gubun == "수익" else v_out,
                "대구분": v_in if gubun == "수익" else -v_out,
                "비고": v_sum
            })
        except: continue

    # --- 쿠팡 처리 ---
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

    # --- 대시보드 출력 ---
    st.subheader("📋 통합 장부 정리 (수정 가능)")
    edited_df = st.data_editor(final_df, use_container_width=True, num_rows="dynamic")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📊 수입 vs 지출")
        st.plotly_chart(px.bar(edited_df.groupby('구분')['금액'].sum().reset_index(), x='구분', y='금액', color='구분', text_auto=',.0f'), use_container_width=True)
    with c2:
        st.subheader("🍕 항목별 지출 비중")
        st.plotly_chart(px.pie(edited_df[edited_df['구분']=='비용'], values='금액', names='용도', hole=0.4), use_container_width=True)

    st.download_button("💾 결과 저장(CSV)", edited_df.to_csv(index=False).encode('utf-8-sig'), "고시원_정산결과.csv", "text/csv")
else:
    st.info("대표님, 왼쪽 사이드바에 은행과 쿠팡 파일을 올려주세요.")
