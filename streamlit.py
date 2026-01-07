import streamlit as st
import pandas as pd
from datetime import datetime
import time
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. Google Sheets 설정
# ==========================================

def get_google_sheet():
    """Google Sheet 연결"""
    try:
        creds_dict = st.secrets["gcp_service_account"]
        sheet_id = st.secrets["sheet_id"]

        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id).sheet1
        return sheet
    except Exception as e:
        st.error(f"Google Sheets 연결 실패: {e}")
        return None

def save_to_sheets(responses, participant_name):
    """Google Sheets에 결과 저장 (한 번에 모든 행 추가)"""
    sheet = get_google_sheet()
    if sheet is None:
        return False

    try:
        existing = sheet.get_all_values()
        if len(existing) == 0:
            headers = ["participant", "task", "item", "choice", "ss_amount", "ll_amount", "rt_sec", "submitted_at"]
            sheet.append_row(headers)

        submitted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = []
        for r in responses:
            row = [
                participant_name,
                r.get("task", ""),
                r.get("item", ""),
                r.get("choice", ""),
                r.get("ss_amount", ""),
                r.get("ll_amount", ""),
                r.get("rt_sec", ""),
                submitted_at
            ]
            rows.append(row)

        sheet.append_rows(rows)
        return True
    except Exception as e:
        st.error(f"저장 실패: {e}")
        return False

# ==========================================
# 2. 초기화 및 설정
# ==========================================

# 금액 리스트 (101%, 102%, 110%, 120%, 150%)
VALUES_SMALL = [505000, 510000, 550000, 600000, 750000]
VALUES_LARGE = [5050000, 5100000, 5500000, 6000000, 7500000]

# 6개 과제 블록 정의
TASKS = [
    {"id": "t1_small_gain", "base": 500000, "vals": VALUES_SMALL, "type": "gain"},
    {"id": "t2_loss", "base": 500000, "vals": VALUES_SMALL, "type": "loss"},
    {"id": "t3_large_gain", "base": 5000000, "vals": VALUES_LARGE, "type": "gain"},
    {"id": "t4_present_bias", "base": 500000, "vals": VALUES_SMALL, "type": "pb"},
    {"id": "t5_subadditivity", "base": 500000, "vals": VALUES_SMALL, "type": "sub"},
    {"id": "t6_speedup", "base": 500000, "vals": VALUES_SMALL, "type": "speedup"},
]

# 설문 데이터
SURVEY_DATA = [
    {"id": "age", "type": "number", "q": "귀하의 연령(만 나이)은?", "min": 18, "max": 100},
    {"id": "gender", "type": "select", "q": "성별은?", "opts": ["남성", "여성", "기타"]},
    {"id": "edu", "type": "select", "q": "최종 학력은?",
     "opts": ["초등학교 졸업 이하", "중학교 졸업", "고등학교 졸업", "대학교 졸업 (학사)", "대학원 졸업 (석/박사 이상)"]},
    {"id": "job", "type": "select", "q": "현재 고용 상태는?",
     "opts": ["전일제 근무", "파트타임 근무", "자영업/프리랜서", "구직 중", "미취업", "학생", "은퇴"]},
    {"id": "income", "type": "number", "q": "세전 연간 총 소득(원)은?", "min": 0, "max": 10000000000},
    {"id": "debt", "type": "number", "q": "현재 총 부채(주택 대출 제외, 원)는?", "min": 0, "max": 10000000000},
    {"id": "asset", "type": "number", "q": "현재 총 자산(부동산/예금 포함, 원)은?", "min": 0, "max": 10000000000},
    {"id": "risk", "type": "slider", "q": "평소 위험을 감수하는 편입니까? (0: 전혀 아님 ~ 10: 매우 그렇다)", "min": 0, "max": 10},
    {"id": "outlook_nat", "type": "select", "q": "향후 1년 국가 경제 전망", "opts": ["좋아질 것이다", "비슷할 것이다", "나빠질 것이다"]},
    {"id": "outlook_per", "type": "select", "q": "향후 1년 개인 재정 전망", "opts": ["좋아질 것이다", "비슷할 것이다", "나빠질 것이다"]}
]

def init_session():
    if 'responses' not in st.session_state:
        st.session_state.responses = []
    if 'current_phase' not in st.session_state:
        st.session_state.current_phase = 'intro'
    if 'task_idx' not in st.session_state:
        st.session_state.task_idx = 0
    if 'item_idx' not in st.session_state:
        st.session_state.item_idx = 0
    if 'survey_idx' not in st.session_state:
        st.session_state.survey_idx = 0
    if 'participant_name' not in st.session_state:
        st.session_state.participant_name = ""
    if 'question_start_time' not in st.session_state:
        st.session_state.question_start_time = time.time()
    if 'processing' not in st.session_state:
        st.session_state.processing = False

# ==========================================
# 3. 헬퍼 함수
# ==========================================

def reset_timer():
    st.session_state.question_start_time = time.time()

def get_rt():
    return round(time.time() - st.session_state.question_start_time, 3)

def get_question_text(task, item_idx):
    """과제 유형에 따른 질문 텍스트 생성"""
    base = task['base']
    target = task['vals'][item_idx]
    task_type = task['type']

    if task_type == 'loss':
        question = f"**{base:,}원**을 내야 하는 상황입니다. 어떻게 하시겠습니까?"
        ss_txt = f"지금 {base:,}원 내기"
        ll_txt = f"1년 뒤 {target:,}원 내기"
    elif task_type == 'pb':  # Present Bias (12mo vs 24mo)
        question = "다음 중 어떤 옵션을 선택하시겠습니까?"
        ss_txt = f"12개월 후 {base:,}원 받기"
        ll_txt = f"24개월 후 {target:,}원 받기"
    elif task_type == 'sub':  # Subadditivity (Now vs 24mo)
        question = "다음 중 어떤 옵션을 선택하시겠습니까?"
        ss_txt = f"지금 {base:,}원 받기"
        ll_txt = f"24개월 후 {target:,}원 받기"
    elif task_type == 'speedup':  # Speedup frame
        question = "다음 중 어떤 옵션을 선택하시겠습니까?"
        ss_txt = f"1년 뒤 {target:,}원을 앞당겨 지금 {base:,}원 받기"
        ll_txt = f"원래대로 1년 뒤 {target:,}원 받기"
    else:  # gain (small & large)
        question = f"**{base:,}원**을 받을 수 있습니다. 어떻게 하시겠습니까?"
        ss_txt = f"지금 {base:,}원 받기"
        ll_txt = f"1년 뒤 {target:,}원 받기"

    return question, ss_txt, ll_txt, base, target

def record_response(choice, ss_val, ll_val, task_id, item_num):
    rt = get_rt()
    st.session_state.responses.append({
        "task": task_id,
        "item": item_num,
        "choice": choice,
        "ss_amount": ss_val,
        "ll_amount": ll_val,
        "rt_sec": rt
    })
    reset_timer()

def next_question():
    """다음 문항으로 이동"""
    if st.session_state.item_idx < 4:
        st.session_state.item_idx += 1
    elif st.session_state.task_idx < 5:
        st.session_state.task_idx += 1
        st.session_state.item_idx = 0
    else:
        st.session_state.current_phase = 'survey'
        st.session_state.survey_idx = 0

# ==========================================
# 4. 메인 함수
# ==========================================

def main():
    st.set_page_config(page_title="의사결정 실험", page_icon="📋")
    init_session()

    phase = st.session_state.current_phase
    disabled = st.session_state.processing

    # ===== INTRO =====
    if phase == 'intro':
        st.title("의사결정 실험")
        st.markdown("""
        **안내사항:**
        * 정답은 없습니다. 본인이 **실제로 선호하는 옵션**을 선택해주세요.
        * 모든 금액은 가상의 상황이지만, 실제 상황이라 가정하고 응답해 주세요.
        """)

        name = st.text_input("참여자 이름(또는 ID)을 입력해주세요:")
        if st.button("시작하기", type="primary"):
            if name.strip():
                st.session_state.participant_name = name.strip()
                st.session_state.current_phase = 'task'
                reset_timer()
                st.rerun()
            else:
                st.warning("이름을 입력해주세요.")

    # ===== TASK (30문항: 6블록 × 5문항) =====
    elif phase == 'task':
        t_idx = st.session_state.task_idx
        i_idx = st.session_state.item_idx
        task = TASKS[t_idx]

        question, ss_txt, ll_txt, ss_val, ll_val = get_question_text(task, i_idx)
        st.markdown(question)

        c1, c2 = st.columns(2)
        if c1.button(ss_txt, use_container_width=True, disabled=disabled):
            st.session_state.processing = True
            record_response('SS', ss_val, ll_val, task['id'], i_idx + 1)
            next_question()
            st.session_state.processing = False
            st.rerun()
        if c2.button(ll_txt, use_container_width=True, disabled=disabled):
            st.session_state.processing = True
            record_response('LL', ss_val, ll_val, task['id'], i_idx + 1)
            next_question()
            st.session_state.processing = False
            st.rerun()

    # ===== SURVEY (10문항) =====
    elif phase == 'survey':
        s_idx = st.session_state.survey_idx
        item = SURVEY_DATA[s_idx]
        st.markdown(f"**{item['q']}**")

        if item['type'] == 'number':
            ans = st.number_input("입력", min_value=item['min'], max_value=item['max'], key=f"s_{s_idx}", label_visibility="collapsed")
            if st.button("다음", disabled=disabled):
                st.session_state.processing = True
                record_response(ans, item['q'], "-", "survey", s_idx + 1)
                if s_idx < 9:
                    st.session_state.survey_idx += 1
                    st.session_state.processing = False
                    st.rerun()
                else:
                    save_to_sheets(st.session_state.responses, st.session_state.participant_name)
                    st.session_state.current_phase = 'done'
                    st.session_state.processing = False
                    st.rerun()

        elif item['type'] == 'select':
            ans = st.radio("선택", item['opts'], key=f"s_{s_idx}", label_visibility="collapsed")
            if st.button("다음", disabled=disabled):
                st.session_state.processing = True
                record_response(ans, item['q'], "-", "survey", s_idx + 1)
                if s_idx < 9:
                    st.session_state.survey_idx += 1
                    st.session_state.processing = False
                    st.rerun()
                else:
                    save_to_sheets(st.session_state.responses, st.session_state.participant_name)
                    st.session_state.current_phase = 'done'
                    st.session_state.processing = False
                    st.rerun()

        elif item['type'] == 'slider':
            ans = st.slider("선택", item['min'], item['max'], 5, key=f"s_{s_idx}", label_visibility="collapsed")
            if st.button("다음", disabled=disabled):
                st.session_state.processing = True
                record_response(ans, item['q'], "-", "survey", s_idx + 1)
                if s_idx < 9:
                    st.session_state.survey_idx += 1
                    st.session_state.processing = False
                    st.rerun()
                else:
                    save_to_sheets(st.session_state.responses, st.session_state.participant_name)
                    st.session_state.current_phase = 'done'
                    st.session_state.processing = False
                    st.rerun()

    # ===== DONE =====
    elif phase == 'done':
        st.title("실험이 완료되었습니다")
        st.markdown("참여해 주셔서 감사합니다.")
        st.markdown("창을 닫아주세요.")

if __name__ == "__main__":
    main()
