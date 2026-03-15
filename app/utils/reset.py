import streamlit as st
import time

def reset_project():
    for key in [
        "acceptance_id", "step", "stt_done", "audio_upload_key", "uploaded_audio",
        "uploaded_keywords_path", "uploaded_keywords",
        "log_keywords_path",

        "log_header_written",
        "clone_initialized",
        "clone_file_objs",
        "remove_clone_indices",
        "run_remove_clone",

        "clone_kw_initialized",
        "clone_kw_initialized_for",
        "clone_keyword_files",
        "remove_clone_kw_indices",
        "run_remove_clone_kw",

        "clone_prefilled",
        # step4
        "df_results_query_triggered",
        "last_df_filters",
        "success_msg",
        "df_results_info",
        "show_results",
        "log_result_path",
        "history",
        "df_results",
        "keywords_dict",
        "unit_code",
        "df_results_filter_confirmed",
        "excel_bytes_filtered",
        "export_filename_filtered",
        "export_path_filtered",
        "filtered_df_results_info",
        "show_filter",     # ← 必加

        # QA 相關變數清理
        "qa_audioitem_path",
        "qa_question_path",
        "qa_audioitem_path_temp",
        "qa_question_path_temp",
        "qa_clone_initialized",
        "qa_settings_confirmed",
        "qa_show_filter",
        "qa_report_path",
    ]:
        st.session_state.pop(key, None)

    # ✅ 重新初始化必要變數
    # st.session_state.project_type = "開新專案"
    st.session_state.last_project_type = None
    st.session_state.step = 0
    st.session_state.stt_done = False
    st.session_state.audio_upload_key = f"audio_upload_{time.time()}"
