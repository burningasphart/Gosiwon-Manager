import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="고시원 통합 관리 시스템", layout="wide")

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

st.title("🏠 고시원 통합 관리 시스템 (대표님 전용)")

# 세션 상태 초기화 (데이터가 날아가지 않게 보존)
if 'main_df' not in st.session_state:
    st.session_state.main_df = pd.DataFrame(columns=["연도", "월", "날짜", "내용", "용도", "구분", "금액", "비고"])

# 사이드바 설정
st.sidebar.header("📁 데이터 업로드")
bank_file = st.sidebar.file_uploader("우리은행 거래내역 (XLS/CSV)", type=['csv', 'xls', 'xlsx'])
coupang_file = st.sidebar.file_uploader("쿠팡 구매내역 (CSV)", type=['csv'])

if st.sidebar.button("데이터 새로 불러오기"):
    if bank_file and coupang_file:
        try:
            if bank_file.name.endswith('.csv'):
                bank_df = pd.read_csv(bank_file, skiprows=3)
            else:
                bank_file.seek(0)
                html_list = pd.read_html(bank_file)
                bank_df = max(html_list, key=len)
                header_row = 0
                for i in range(min(10, len(bank_df))):
                    if '거래일시' in str(bank_df.iloc[i].values):
                        header_row = i
                        break
                bank_df.columns = bank_df.iloc[header_row]
                bank_df = bank_df.iloc[header_row+1:].reset_index(drop=True)
            
            coupang_df = pd.read_csv(coupang_file)
            new_data = []

            # 은행 처리
            for _, row in bank_df.iterrows():
                v_in = clean_amt(row.get('맡기신금액', 0))
                v_out = clean_amt(row.get('찾으신금액', 0))
                v_sum = str(row.get('적요', ''))
                v_memo = str(row.get('기재내용', ''))
                v_date = str(row.get('거래일시', ''))
                if "쿠팡" in v_sum or "쿠팡" in v_memo or pd.isna(row.get('거래일시')): continue
                content = (v_memo + " " + v_sum).strip()
                gubun, yongdo = auto_categorize(content, v_in, v_out)
                new_data.append({"연도": v_date[:4], "월": v_date[5:7], "날짜": v_date[5:10], "내용": content, "용도": yongdo, "구분": gubun, "금액": v_in if gubun=="수익" else v_out, "비고": v_sum})
            
            # 쿠팡 처리
            for _, row in coupang_df.iterrows():
                price = clean_amt(row.get('총결제금액(원)', 0))
                _, yongdo = auto_categorize(row.get('상품명', ''), 0, price)
                new_data.append({"연도": str(row.get('주문일', ''))[:4], "월": str(row.get('주문일', ''))[6:8], "날짜": str(row.get('주문일', ''))[6:11], "내용": row.get('상품명', ''), "용도": yongdo, "구분": "비용", "금액": price, "비고": "쿠팡구매"})
            
            st.session_state.main_df = pd.DataFrame(new_data)
            st.success("데이터 로드 완료!")
        except Exception as e:
            st.error(f"파일을 읽는 중 오류가 발생했습니다: {e}")

st.sidebar.divider()
include_misc = st.sidebar.checkbox("사업 수익에 '기타' 지출 포함하기", value=False)

# 탭 구성
tab1, tab2 = st.tabs(["📊 월간 통합 대시보드", "📝 데이터 상세 정리 및 추가"])

with tab2:
    st.subheader("데이터 상세 내역")
    # 수동 추가 기능 (num_rows="dynamic")
    edited_df = st.data_editor(st.session_state.main_df, use_container_width=True, num_rows="dynamic", key="data_editor_key")
    if st.button("수정 내용 저장하기"):
        st.session_state.main_df = edited_df
        st.rerun()

with tab1:
    current_df = st.session_state.main_df
    if not current_df.empty:
        # 데이터 타입 보정
        current_df['금액'] = current_df['금액'].apply(clean_amt)
        
        # 필터링 (보증금 제외, 체크박스에 따른 기타 제외)
        plot_df = current_df[current_df['용도'] != '보증금'].copy()
        if not include_misc:
            plot_df = plot_df[plot_df['용도'] != '기타']
        
        if not plot_df.empty:
            # 월별 통계
            monthly_stats = plot_df.groupby(['월', '구분'])['금액'].sum().unstack(fill_value=0).reset_index()
            for col in ['수익', '비용']:
                if col not in monthly_stats: monthly_stats[col] = 0
            monthly_stats['순이익'] = monthly_stats['수익'] - monthly_stats['비용']

            # 지표
            c1, c2, c3 = st.columns(3)
            c1.metric("누적 총 수입", f"{monthly_stats['수익'].sum():,}원")
            c2.metric("누적 총 지출", f"{monthly_stats['비용'].sum():,}원")
            c3.metric("누적 순이익", f"{monthly_stats['순이익'].sum():,}원")

            # 그래프
            st.subheader("📅 월별 수입/지출 누적 추이")
            fig = px.bar(monthly_stats, x='월', y=['수익', '비용'], barmode='group', text_auto=',.0f', color_discrete_map={'수익': '#00CC96', '비용': '#EF553B'})
            st.plotly_chart(fig, use_container_width=True)

            # 요약표
            st.subheader("📑 월간 정산 요약표")
            st.table(monthly_stats.style.format("{:,}원", subset=['수익', '비용', '순이익']))
        else:
            st.info("분석할 데이터가 없습니다. (기타/보증금 제외됨)")
    else:
        st.info("왼쪽에서 파일을 먼저 업로드하고 [데이터 새로 불러오기] 버튼을 눌러주세요.")

# 저장 버튼
st.sidebar.download_button("💾 최종 데이터 저장(CSV)", current_df.to_csv(index=False).encode('utf-8-sig'), "고시원_통합장부.csv", "text/csv")
