import streamlit as st
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

VALUES_SMALL = [505000, 510000, 550000, 600000, 750000]
VALUES_LARGE = [5050000, 5100000, 5500000, 6000000, 7500000]

TASKS = [
    {"id": "t1_small_gain", "base": 500000, "vals": VALUES_SMALL, "type": "gain"},
    {"id": "t2_loss", "base": 500000, "vals": VALUES_SMALL, "type": "loss"},
    {"id": "t3_large_gain", "base": 5000000, "vals": VALUES_LARGE, "type": "gain"},
    {"id": "t4_present_bias", "base": 500000, "vals": VALUES_SMALL, "type": "pb"},
    {"id": "t5_subadditivity", "base": 500000, "vals": VALUES_SMALL, "type": "sub"},
    {"id": "t6_speedup", "base": 500000, "vals": VALUES_SMALL, "type": "speedup"},
]

TOTAL_QUESTIONS = 30
BREAK_DURATION = 600  # 10분 = 600초

def init_session():
    if 'responses' not in st.session_state:
        st.session_state.responses = []
    if 'current_phase' not in st.session_state:
        st.session_state.current_phase = 'intro'
    if 'task_idx' not in st.session_state:
        st.session_state.task_idx = 0
    if 'item_idx' not in st.session_state:
        st.session_state.item_idx = 0
    if 'participant_name' not in st.session_state:
        st.session_state.participant_name = ""
    if 'question_start_time' not in st.session_state:
        st.session_state.question_start_time = time.time()
    if 'processing' not in st.session_state:
        st.session_state.processing = False
    if 'break_start_time' not in st.session_state:
        st.session_state.break_start_time = None

# ==========================================
# 3. 헬퍼 함수
# ==========================================

def reset_timer():
    st.session_state.question_start_time = time.time()

def get_rt():
    return round(time.time() - st.session_state.question_start_time, 3)

def get_current_question_number():
    return st.session_state.task_idx * 5 + st.session_state.item_idx + 1

def get_question_text(task, item_idx):
    base = task['base']
    target = task['vals'][item_idx]
    task_type = task['type']

    if task_type == 'loss':
        question = f"**{base:,}원**을 내야 하는 상황입니다. 어떻게 하시겠습니까?"
        ss_txt = f"지금 {base:,}원 내기"
        ll_txt = f"1년 뒤 {target:,}원 내기"
    elif task_type == 'pb':
        question = "다음 중 어떤 옵션을 선택하시겠습니까?"
        ss_txt = f"12개월 후 {base:,}원 받기"
        ll_txt = f"24개월 후 {target:,}원 받기"
    elif task_type == 'sub':
        question = "다음 중 어떤 옵션을 선택하시겠습니까?"
        ss_txt = f"지금 {base:,}원 받기"
        ll_txt = f"24개월 후 {target:,}원 받기"
    elif task_type == 'speedup':
        question = "다음 중 어떤 옵션을 선택하시겠습니까?"
        ss_txt = f"1년 뒤 {target:,}원을 앞당겨 지금 {base:,}원 받기"
        ll_txt = f"원래대로 1년 뒤 {target:,}원 받기"
    else:
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
    if st.session_state.item_idx < 4:
        st.session_state.item_idx += 1
    elif st.session_state.task_idx < 5:
        st.session_state.task_idx += 1
        st.session_state.item_idx = 0
    else:
        save_to_sheets(st.session_state.responses, st.session_state.participant_name)
        st.session_state.break_start_time = time.time()
        st.session_state.current_phase = 'break'

# ==========================================
# 4. 스타일 설정
# ==========================================

def apply_custom_styles():
    st.markdown("""
    <style>
    .main .block-container {
        max-width: 800px;
        padding-top: 2rem;
    }
    .question-text {
        font-size: 1.8rem;
        font-weight: 500;
        text-align: center;
        margin: 2rem 0;
        line-height: 1.6;
    }
    .progress-counter {
        font-size: 1.4rem;
        font-weight: 700;
        text-align: center;
        color: #222222;
        margin-bottom: 0.5rem;
    }
    .stButton > button {
        font-size: 1.3rem !important;
        padding: 1rem 2rem !important;
        min-height: 80px !important;
        border-radius: 12px !important;
    }
    .stProgress > div > div {
        background-color: #f0f0f0 !important;
        border: 1px solid #ddd !important;
    }
    .stProgress > div > div > div {
        background-color: #222222 !important;
    }
    .intro-title {
        font-size: 2.5rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 1.5rem;
    }
    .intro-text {
        font-size: 1.3rem;
        text-align: center;
        line-height: 1.8;
    }
    .done-title {
        font-size: 2.5rem;
        font-weight: 700;
        text-align: center;
        color: #28a745;
        margin: 2rem 0;
    }
    .done-text {
        font-size: 1.5rem;
        text-align: center;
    }
    .break-title {
        font-size: 2.5rem;
        font-weight: 700;
        text-align: center;
        color: #007bff;
        margin: 2rem 0;
    }
    .break-text {
        font-size: 1.3rem;
        text-align: center;
        line-height: 1.8;
    }
    .timer-display {
        font-size: 4rem;
        font-weight: 700;
        text-align: center;
        color: #222222;
        margin: 2rem 0;
        font-family: monospace;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 5. 메인 함수
# ==========================================

def main():
    st.set_page_config(page_title="의사결정 실험", page_icon="📋", layout="centered")
    apply_custom_styles()
    init_session()

    phase = st.session_state.current_phase
    disabled = st.session_state.processing

    if phase == 'intro':
        st.markdown('<p class="intro-title">의사결정 실험</p>', unsafe_allow_html=True)
        st.markdown("""
        <p class="intro-text">
        <strong>안내사항:</strong><br>
        • 정답은 없습니다. 본인이 <strong>실제로 선호하는 옵션</strong>을 선택해주세요.<br>
        • 모든 금액은 가상의 상황이지만, 실제 상황이라 가정하고 응답해 주세요.
        </p>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            name = st.text_input("참여자 이름(또는 ID)을 입력해주세요:", label_visibility="visible")
            if st.button("시작하기", type="primary", use_container_width=True):
                if name.strip():
                    st.session_state.participant_name = name.strip()
                    st.session_state.current_phase = 'task'
                    reset_timer()
                    st.rerun()
                else:
                    st.warning("이름을 입력해주세요.")

    elif phase == 'task':
        t_idx = st.session_state.task_idx
        i_idx = st.session_state.item_idx
        task = TASKS[t_idx]
        
        current_q = get_current_question_number()
        progress = current_q / TOTAL_QUESTIONS
        
        st.markdown(f'<p class="progress-counter">{current_q} / {TOTAL_QUESTIONS}</p>', unsafe_allow_html=True)
        st.progress(progress)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        question, ss_txt, ll_txt, ss_val, ll_val = get_question_text(task, i_idx)
        st.markdown(f'<p class="question-text">{question.replace("**", "<strong>").replace("**", "</strong>")}</p>', unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        if c1.button(ss_txt, use_container_width=True, disabled=disabled, key="btn_ss"):
            st.session_state.processing = True
            record_response('SS', ss_val, ll_val, task['id'], i_idx + 1)
            next_question()
            st.session_state.processing = False
            st.rerun()
        if c2.button(ll_txt, use_container_width=True, disabled=disabled, key="btn_ll"):
            st.session_state.processing = True
            record_response('LL', ss_val, ll_val, task['id'], i_idx + 1)
            next_question()
            st.session_state.processing = False
            st.rerun()

    elif phase == 'break':
        elapsed = time.time() - st.session_state.break_start_time
        remaining = max(0, BREAK_DURATION - elapsed)
        
        if remaining > 0:
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            
            st.markdown('<p class="break-title">☕ 잠시 휴식 시간입니다</p>', unsafe_allow_html=True)
            st.markdown('<p class="break-text">실험이 완료되었습니다. 참여해 주셔서 감사합니다.<br>잠시 휴식을 취한 후 다음 실험으로 이동해 주세요.</p>', unsafe_allow_html=True)
            
            st.markdown(f'<p class="timer-display">{mins:02d}:{secs:02d}</p>', unsafe_allow_html=True)
            
            st.progress(1 - (remaining / BREAK_DURATION))
            
            time.sleep(1)
            st.rerun()
        else:
            st.session_state.current_phase = 'done'
            st.rerun()

    elif phase == 'done':
        st.balloons()
        
        st.markdown('<p class="done-title">✓ 휴식이 완료되었습니다</p>', unsafe_allow_html=True)
        st.markdown('<p class="done-text">아래 버튼을 눌러 다음 실험으로 이동해 주세요.</p>', unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.link_button(
                "▶ 다음 실험으로 이동",
                "https://free-recall2-k101.streamlit.app/",
                use_container_width=True
            )

if __name__ == "__main__":
    main()
