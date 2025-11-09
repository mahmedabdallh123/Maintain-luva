import streamlit as st
import pandas as pd
import json
import os
import io
import requests
import shutil
import re
import base64
from datetime import datetime, timedelta
from base64 import b64decode

# محاولة استيراد PyGithub (لرفع التعديلات)
try:
    from github import Github
    GITHUB_AVAILABLE = True
except Exception:
    GITHUB_AVAILABLE = False

# ===============================
# ⚙ إعدادات التطبيق - نظام إدارة محطات الإنتاج
# ===============================
APP_CONFIG = {
    # إعدادات التطبيق العامة
    "APP_TITLE": "نظام إدارة محطات الإنتاج",
    "APP_ICON": "🏭",
    
    # إعدادات GitHub
    "REPO_NAME": "mahmedabdallh123/Maintain-luva",
    "BRANCH": "main",
    "PRODUCTION_FILE_PATH": "station.xlsx",
    "LOCAL_PRODUCTION_FILE": "station.xlsx",
    
    # إعدادات الأمان
    "MAX_ACTIVE_USERS": 10,
    "SESSION_DURATION_MINUTES": 240,
    
    # إعدادات الواجهة
    "SHOW_TECH_SUPPORT_TO_ALL": True,
    "CUSTOM_TABS": ["📊 عرض المحطات", "✏ تعديل البيانات", "👥 إدارة المستخدمين", "📞 الدعم الفني"],
    
    # إعدادات الحفظ التلقائي
    "AUTO_SAVE": True  # تفعيل الحفظ التلقائي افتراضياً
}

# ===============================
# 🗂 إعدادات الملفات
# ===============================
USERS_FILE = "users.json"
STATE_FILE = "state.json"
SESSION_DURATION = timedelta(minutes=APP_CONFIG["SESSION_DURATION_MINUTES"])
MAX_ACTIVE_USERS = APP_CONFIG["MAX_ACTIVE_USERS"]

# -------------------------------
# 🧩 دوال مساعدة للملفات والحالة
# -------------------------------
def load_users():
    """تحميل بيانات المستخدمين من ملف JSON"""
    if not os.path.exists(USERS_FILE):
        default_users = {
            "admin": {
                "password": "1111", 
                "role": "admin", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"],
                "full_name": "المسؤول الرئيسي"
            },
            "user1": {
                "password": "12345", 
                "role": "admin",
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"],
                "full_name": "مستخدم تجريبي"
            }
        }
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_users, f, indent=4, ensure_ascii=False)
        return default_users
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
            for username, info in users.items():
                info["role"] = "admin"
                info["permissions"] = ["all"]
                if "full_name" not in info:
                    info["full_name"] = username
            return users
    except Exception as e:
        st.error(f"❌ خطأ في ملف users.json: {e}")
        return {
            "admin": {
                "password": "1111", 
                "role": "admin", 
                "permissions": ["all"], 
                "created_at": datetime.now().isoformat(),
                "full_name": "المسؤول الرئيسي"
            }
        }

def save_users(users):
    """حفظ بيانات المستخدمين إلى ملف JSON"""
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"❌ خطأ في حفظ ملف users.json: {e}")
        return False

def load_state():
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4, ensure_ascii=False)
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4, ensure_ascii=False)

def cleanup_sessions(state):
    now = datetime.now()
    changed = False
    for user, info in list(state.items()):
        if info.get("active") and "login_time" in info:
            try:
                login_time = datetime.fromisoformat(info["login_time"])
                if now - login_time > SESSION_DURATION:
                    info["active"] = False
                    info.pop("login_time", None)
                    changed = True
            except:
                info["active"] = False
                changed = True
    if changed:
        save_state(state)
    return state

def remaining_time(state, username):
    if not username or username not in state:
        return None
    info = state.get(username)
    if not info or not info.get("active"):
        return None
    try:
        lt = datetime.fromisoformat(info["login_time"])
        remaining = SESSION_DURATION - (datetime.now() - lt)
        if remaining.total_seconds() <= 0:
            return None
        return remaining
    except:
        return None

# -------------------------------
# 🔐 تسجيل الخروج
# -------------------------------
def logout_action():
    state = load_state()
    username = st.session_state.get("username")
    if username and username in state:
        state[username]["active"] = False
        state[username].pop("login_time", None)
        save_state(state)
    keys = list(st.session_state.keys())
    for k in keys:
        st.session_state.pop(k, None)
    st.rerun()

# -------------------------------
# 🧠 واجهة تسجيل الدخول
# -------------------------------
def login_ui():
    users = load_users()
    state = cleanup_sessions(load_state())
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.user_role = None
        st.session_state.user_permissions = []
        st.session_state.user_fullname = None

    st.title(f"{APP_CONFIG['APP_ICON']} تسجيل الدخول - {APP_CONFIG['APP_TITLE']}")

    username_input = st.selectbox("👤 اختر المستخدم", list(users.keys()))
    password = st.text_input("🔑 كلمة المرور", type="password")

    active_users = [u for u, v in state.items() if v.get("active")]
    active_count = len(active_users)
    st.caption(f"🔒 المستخدمون النشطون الآن: {active_count} / {MAX_ACTIVE_USERS}")

    if not st.session_state.logged_in:
        if st.button("تسجيل الدخول", type="primary"):
            if username_input in users and users[username_input]["password"] == password:
                if username_input == "admin":
                    pass
                elif username_input in active_users:
                    st.warning("⚠ هذا المستخدم مسجل دخول بالفعل.")
                    return False
                elif active_count >= MAX_ACTIVE_USERS:
                    st.error("🚫 الحد الأقصى للمستخدمين المتصلين حالياً.")
                    return False
                state[username_input] = {"active": True, "login_time": datetime.now().isoformat()}
                save_state(state)
                st.session_state.logged_in = True
                st.session_state.username = username_input
                st.session_state.user_role = "admin"
                st.session_state.user_permissions = ["all"]
                st.session_state.user_fullname = users[username_input].get("full_name", username_input)
                st.success(f"✅ تم تسجيل الدخول: {st.session_state.user_fullname} (مدير النظام)")
                st.rerun()
            else:
                st.error("❌ كلمة المرور غير صحيحة.")
        return False
    else:
        username = st.session_state.username
        user_fullname = st.session_state.user_fullname
        st.success(f"✅ مسجل الدخول كـ: {user_fullname} (مدير النظام)")
        rem = remaining_time(state, username)
        if rem:
            mins, secs = divmod(int(rem.total_seconds()), 60)
            st.info(f"⏳ الوقت المتبقي: {mins:02d}:{secs:02d}")
        else:
            st.warning("⏰ انتهت الجلسة، سيتم تسجيل الخروج.")
            logout_action()
        if st.button("🚪 تسجيل الخروج"):
            logout_action()
        return True

# -------------------------------
# 🔄 دوال جلب وحفظ الملف من/إلى GitHub
# -------------------------------
def get_file_from_github():
    """جلب ملف Excel من GitHub"""
    try:
        repo_parts = APP_CONFIG["REPO_NAME"].split('/')
        if len(repo_parts) != 2:
            st.error("❌ تنسيق REPO_NAME غير صحيح.")
            return None, None, None
            
        repo_owner, repo_name = repo_parts
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{APP_CONFIG['PRODUCTION_FILE_PATH']}?ref={APP_CONFIG['BRANCH']}"
        
        github_token = os.getenv('GITHUB_TOKEN')
        headers = {}
        if github_token:
            headers = {"Authorization": f"token {github_token}"}
        
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            content = response.json()['content']
            file_content = base64.b64decode(content)
            return file_content, response.json()['sha'], response.json().get('html_url')
        else:
            st.error(f"خطأ في جلب الملف: {response.status_code}")
            return None, None, None
    except Exception as e:
        st.error(f"خطأ: {str(e)}")
        return None, None, None

def save_file_to_github(df_dict, sha, commit_message):
    """حفظ الملف إلى GitHub"""
    try:
        repo_parts = APP_CONFIG["REPO_NAME"].split('/')
        if len(repo_parts) != 2:
            st.error("❌ تنسيق REPO_NAME غير صحيح.")
            return False, None
            
        repo_owner, repo_name = repo_parts
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{APP_CONFIG['PRODUCTION_FILE_PATH']}"
        
        # تحويل جميع DataFrames إلى Excel في الذاكرة
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            for sheet_name, df in df_dict.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        content_base64 = base64.b64encode(output.getvalue()).decode()
        
        github_token = os.getenv('GITHUB_TOKEN')
        
        data = {
            "message": commit_message,
            "content": content_base64,
            "sha": sha,
            "branch": APP_CONFIG["BRANCH"]
        }
        
        headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        if github_token:
            headers["Authorization"] = f"token {github_token}"
        
        response = requests.put(url, json=data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            return True, response.json()['commit']['html_url']
        else:
            st.error(f"خطأ في الحفظ: {response.status_code}")
            return False, None
            
    except Exception as e:
        st.error(f"خطأ في الحفظ: {str(e)}")
        return False, None

def fetch_production_from_github():
    """تحميل ملف الإنتاج من GitHub"""
    try:
        with st.spinner("جاري تحميل البيانات من GitHub..."):
            file_content, file_sha, file_url = get_file_from_github()
            
            if file_content:
                with open(APP_CONFIG["LOCAL_PRODUCTION_FILE"], "wb") as f:
                    f.write(file_content)
                
                st.session_state.file_sha = file_sha
                st.session_state.file_url = file_url
                
                try:
                    st.cache_data.clear()
                except:
                    pass
                    
                return True
        return False
    except Exception as e:
        st.error(f"⚠ فشل التحديث من GitHub: {e}")
        return False

# -------------------------------
# 📂 تحميل البيانات
# -------------------------------
@st.cache_data(show_spinner=False)
def load_production_data():
    """تحميل بيانات محطات الإنتاج"""
    if not os.path.exists(APP_CONFIG["LOCAL_PRODUCTION_FILE"]):
        st.warning("⚠ لم يتم العثور على ملف الإنتاج. سيتم إنشاء ملف جديد عند أول حفظ.")
        return {}
    
    try:
        excel_file = pd.ExcelFile(APP_CONFIG["LOCAL_PRODUCTION_FILE"])
        sheets_data = {}
        
        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(APP_CONFIG["LOCAL_PRODUCTION_FILE"], sheet_name=sheet_name)
            sheets_data[sheet_name] = df
        
        return sheets_data
    except Exception as e:
        st.error(f"❌ خطأ في تحميل بيانات الإنتاج: {e}")
        return {}

def get_all_sheets():
    """الحصول على قائمة جميع الشيتات المتاحة"""
    sheets_data = load_production_data()
    return list(sheets_data.keys())

def get_sheet_columns(sheet_name):
    """الحصول على أعمدة شيت معين"""
    sheets_data = load_production_data()
    if sheet_name in sheets_data:
        return list(sheets_data[sheet_name].columns)
    return []

# -------------------------------
# 🔁 حفظ البيانات
# -------------------------------
def save_production_data(sheets_data, commit_message="تحديث بيانات محطات الإنتاج"):
    """حفظ بيانات الإنتاج إلى ملف Excel محلياً وإلى GitHub"""
    try:
        # الحفظ المحلي أولاً
        with pd.ExcelWriter(APP_CONFIG["LOCAL_PRODUCTION_FILE"], engine='openpyxl') as writer:
            for sheet_name, df in sheets_data.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        # امسح الكاش
        try:
            st.cache_data.clear()
        except:
            pass

        # الحفظ على GitHub إذا كان هناك token
        github_token = os.getenv('GITHUB_TOKEN')
        if github_token and 'file_sha' in st.session_state:
            success, commit_url = save_file_to_github(
                sheets_data,
                st.session_state.file_sha,
                commit_message
            )
            if success:
                # تحديث SHA بعد الحفظ
                file_content, new_sha, file_url = get_file_from_github()
                if new_sha:
                    st.session_state.file_sha = new_sha
                return True, commit_url
            else:
                return False, None
        
        return True, None
        
    except Exception as e:
        st.error(f"❌ خطأ في حفظ البيانات: {e}")
        return False, None

def update_sheet_data(sheet_name, updated_df):
    """تحديث بيانات شيت معين مع الحفظ التلقائي على GitHub"""
    sheets_data = load_production_data()
    sheets_data[sheet_name] = updated_df
    
    # حفظ تلقائي مع رسالة مخصصة
    commit_message = f"تحديث تلقائي: {sheet_name} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    return save_production_data(sheets_data, commit_message)

# -------------------------------
# 🧮 دوال مساعدة للنظام
# -------------------------------
def get_user_permissions(user_role, user_permissions):
    """الحصول على صلاحيات المستخدم - جميع المستخدمين لديهم جميع الصلاحيات"""
    return {
        "can_input": True,
        "can_view_stats": True,
        "can_manage_users": True,
        "can_see_tech_support": True
    }

def create_backup():
    """إنشاء نسخة احتياطية من الملف"""
    try:
        if os.path.exists(APP_CONFIG["LOCAL_PRODUCTION_FILE"]):
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            shutil.copy2(APP_CONFIG["LOCAL_PRODUCTION_FILE"], backup_name)
            return backup_name
        return None
    except Exception as e:
        st.error(f"❌ خطأ في إنشاء النسخة الاحتياطية: {e}")
        return None

# -------------------------------
# 🖥 الواجهة الرئيسية
# -------------------------------
st.set_page_config(page_title=APP_CONFIG["APP_TITLE"], layout="wide")

# شريط تسجيل الدخول
with st.sidebar:
    st.header("👤 الجلسة")
    if not st.session_state.get("logged_in"):
        if not login_ui():
            st.stop()
    else:
        state = cleanup_sessions(load_state())
        username = st.session_state.username
        user_fullname = st.session_state.user_fullname
        rem = remaining_time(state, username)
        if rem:
            mins, secs = divmod(int(rem.total_seconds()), 60)
            st.success(f"👋 {user_fullname} | الدور: مدير النظام | ⏳ {mins:02d}:{secs:02d}")
        else:
            logout_action()

    st.markdown("---")
    st.header("🔧 أدوات النظام")
    
    # إعدادات الحفظ التلقائي (مفعّل دائماً)
    st.subheader("💾 إعدادات الحفظ")
    st.success("✅ الحفظ التلقائي مفعّل - سيتم حفظ جميع التغييرات تلقائياً على GitHub")
    
    if st.button("🔄 تحديث الملف من GitHub", use_container_width=True):
        if fetch_production_from_github():
            st.success("✅ تم تحديث البيانات بنجاح")
            st.rerun()
        else:
            st.error("❌ فشل في تحديث البيانات")
    
    if st.button("💾 إنشاء نسخة احتياطية", use_container_width=True):
        backup_file = create_backup()
        if backup_file:
            st.success(f"✅ تم إنشاء النسخة الاحتياطية: {backup_file}")
        else:
            st.error("❌ فشل في إنشاء النسخة الاحتياطية")
    
    if st.button("🗑 مسح الكاش", use_container_width=True):
        try:
            st.cache_data.clear()
            st.success("✅ تم مسح الكاش بنجاح")
            st.rerun()
        except Exception as e:
            st.error(f"❌ خطأ في مسح الكاش: {e}")
    
    st.markdown("---")
    
    # معلومات النظام
    st.header("ℹ معلومات النظام")
    production_data = load_production_data()
    if production_data:
        total_sheets = len(production_data)
        total_rows = sum(len(df) for df in production_data.values())
        st.info(f"📊 إحصائيات:\n- الأوراق: {total_sheets}\n- الصفوف: {total_rows}")
    
    st.markdown("---")
    
    if st.button("🚪 تسجيل الخروج", use_container_width=True, type="primary"):
        logout_action()

# تحميل البيانات
production_data = load_production_data()

# واجهة التبويبات الرئيسية
st.title(f"{APP_CONFIG['APP_ICON']} {APP_CONFIG['APP_TITLE']}")

# جميع المستخدمين لديهم جميع الصلاحيات
permissions = get_user_permissions(None, None)

# عرض جميع التبويبات لكل المستخدمين
tabs = st.tabs(APP_CONFIG["CUSTOM_TABS"])

# -------------------------------
# Tab 1: عرض المحطات مع تخصيص الأعمدة
# -------------------------------
with tabs[0]:
    st.header("📊 عرض بيانات المحطات")
    
    if not production_data:
        st.warning("⚠ لا توجد بيانات متاحة. يرجى تحديث الملف من GitHub أو إضافة بيانات جديدة.")
    else:
        available_sheets = get_all_sheets()
        selected_sheet = st.selectbox(
            "📋 اختر المحطة أو القسم:",
            available_sheets,
            key="view_sheet_select"
        )
        
        if selected_sheet:
            df = production_data[selected_sheet]
            
            st.subheader(f"بيانات {selected_sheet}")
            
            # قسم تخصيص الأعمدة
            st.subheader("🎛 تخصيص الأعمدة المعروضة")
            
            # الحصول على جميع الأعمدة المتاحة
            all_columns = list(df.columns)
            
            # خيارات التخصيص
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # خيار عرض جميع الأعمدة
                show_all_columns = st.checkbox("عرض جميع الأعمدة", value=True, key="show_all_cols")
            
            with col2:
                # خيار تخصيص الأعمدة يدوياً
                custom_columns = st.checkbox("تخصيص الأعمدة المحددة", value=False, key="custom_cols")
            
            with col3:
                # خيار إعادة التعيين
                if st.button("🔄 إعادة تعيين", use_container_width=True):
                    if 'selected_columns' in st.session_state:
                        del st.session_state.selected_columns
                    st.rerun()
            
            # تحديد الأعمدة المطلوبة للعرض
            if show_all_columns:
                display_columns = all_columns
                st.info("🔍 يتم عرض جميع الأعمدة")
            elif custom_columns:
                # اختيار الأعمدة المطلوبة
                selected_columns = st.multiselect(
                    "📋 اختر الأعمدة للعرض:",
                    options=all_columns,
                    default=all_columns[:min(5, len(all_columns))] if 'selected_columns' not in st.session_state else st.session_state.selected_columns,
                    key="column_selector"
                )
                display_columns = selected_columns
                st.session_state.selected_columns = selected_columns
                
                if not display_columns:
                    st.warning("⚠ لم تختر أي أعمدة للعرض. سيتم عرض جميع الأعمدة.")
                    display_columns = all_columns
                else:
                    st.success(f"✅ سيتم عرض {len(display_columns)} عمود من أصل {len(all_columns)}")
            else:
                display_columns = all_columns
            
            # عرض معلومات عن الشيت
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("عدد الصفوف", len(df))
            with col2:
                st.metric("عدد الأعمدة", len(display_columns))
            with col3:
                st.metric("إجمالي البيانات", df[display_columns].count().sum() if display_columns else 0)
            
            # عرض البيانات مع الأعمدة المحددة فقط
            if display_columns:
                st.dataframe(df[display_columns], use_container_width=True, height=400)
            else:
                st.warning("⚠ لا توجد أعمدة محددة للعرض.")

# -------------------------------
# Tab 2: تعديل البيانات مع الحفظ التلقائي الفوري
# -------------------------------
with tabs[1]:
    st.header("✏ تعديل بيانات المحطات")
    
    if not production_data:
        st.warning("⚠ لا توجد بيانات متاحة. يرجى تحديث الملف من GitHub.")
    else:
        available_sheets = get_all_sheets()
        selected_sheet = st.selectbox(
            "📋 اختر المحطة أو القسم للتعديل:",
            available_sheets,
            key="edit_sheet_select"
        )
        
        if selected_sheet:
            df = production_data[selected_sheet]
            
            st.subheader(f"تعديل بيانات {selected_sheet}")
            
            # عرض حالة الحفظ التلقائي
            st.success("💾 الحفظ التلقائي مفعّل - سيتم حفظ جميع التغييرات تلقائياً على GitHub")
            
            # استخدام محرر البيانات مع الحفظ التلقائي الفوري
            st.info("💡 أي تغيير تقوم به سيتم حفظه تلقائياً على GitHub")
            
            # تحويل جميع الأعمدة إلى نص لضمان قبول جميع أنواع المدخلات
            df_for_edit = df.astype(str)
            
            # محرر البيانات مع الحفظ التلقائي
            edited_df = st.data_editor(
                df_for_edit,
                use_container_width=True,
                height=500,
                num_rows="dynamic",
                key=f"editor_{selected_sheet}",
                column_config={
                    col: st.column_config.TextColumn(
                        col,
                        help=f"يمكنك إدخال أي نوع من البيانات في عمود {col}"
                    ) for col in df_for_edit.columns
                }
            )
            
            # التحقق إذا كانت هناك تغييرات وحفظها تلقائياً
            if not edited_df.equals(df_for_edit):
                with st.spinner("جاري الحفظ التلقائي على GitHub..."):
                    success, commit_url = update_sheet_data(selected_sheet, edited_df)
                    if success:
                        st.success("✅ تم الحفظ التلقائي بنجاح على GitHub")
                        if commit_url:
                            st.markdown(f"[📎 عرض التعديل على GitHub]({commit_url})")
                        # تحديث البيانات المعروضة
                        st.rerun()
                    else:
                        st.error("❌ فشل في الحفظ التلقائي")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🔄 إعادة تحميل البيانات", use_container_width=True):
                    st.rerun()
            
            with col2:
                if st.button("📥 تصدير البيانات", use_container_width=True):
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        edited_df.to_excel(writer, sheet_name=selected_sheet, index=False)
                    
                    st.download_button(
                        label="تحميل كملف Excel",
                        data=buffer.getvalue(),
                        file_name=f"{selected_sheet}_{datetime.now().date()}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
            
            # إضافة صف جديد مع الحفظ التلقائي
            st.subheader("➕ إضافة بيانات جديدة")
            with st.form(f"add_row_form_{selected_sheet}"):
                st.write("املأ البيانات الجديدة (سيتم الحفظ تلقائياً):")
                new_row_data = {}
                cols = st.columns(min(4, len(df.columns)))
                
                for i, column in enumerate(df.columns):
                    col_idx = i % 4
                    with cols[col_idx]:
                        # استخدام حقل نصي لجميع الأعمدة للسماح بجميع أنواع المدخلات
                        new_row_data[column] = st.text_input(
                            f"{column}:",
                            value="",
                            key=f"new_{column}_{selected_sheet}",
                            help=f"أدخل أي قيمة لـ {column}"
                        )
                
                if st.form_submit_button("إضافة صف جديد", use_container_width=True):
                    if any(new_row_data.values()):
                        new_df = pd.concat([edited_df, pd.DataFrame([new_row_data])], ignore_index=True)
                        with st.spinner("جاري إضافة الصف والحفظ على GitHub..."):
                            success, commit_url = update_sheet_data(selected_sheet, new_df)
                            if success:
                                st.success("✅ تم إضافة الصف الجديد والحفظ بنجاح")
                                if commit_url:
                                    st.markdown(f"[📎 عرض التعديل على GitHub]({commit_url})")
                                st.rerun()
                    else:
                        st.warning("⚠ يرجى إدخال بيانات في الحقول")

# -------------------------------
# Tab 3: إدارة المستخدمين
# -------------------------------
with tabs[2]:
    st.header("👥 إدارة المستخدمين")
    
    users = load_users()
    
    st.subheader("📋 المستخدمين الحاليين")
    if users:
        user_data = []
        for username, info in users.items():
            user_data.append({
                "اسم المستخدم": username,
                "الاسم الكامل": info.get("full_name", username),
                "الدور": "مدير النظام",
                "الصلاحيات": "جميع الصلاحيات",
                "تاريخ الإنشاء": info.get("created_at", "غير معروف")
            })
        
        users_df = pd.DataFrame(user_data)
        st.dataframe(users_df, use_container_width=True)
    
    st.subheader("➕ إضافة مستخدم جديد")
    
    col1, col2 = st.columns(2)
    with col1:
        new_username = st.text_input("اسم المستخدم الجديد:", placeholder="أدخل اسم المستخدم")
        new_fullname = st.text_input("الاسم الكامل:", placeholder="أدخل الاسم الكامل")
    with col2:
        new_password = st.text_input("كلمة المرور:", type="password", placeholder="أدخل كلمة المرور")
        confirm_password = st.text_input("تأكيد كلمة المرور:", type="password", placeholder="أكد كلمة المرور")
    
    if st.button("إضافة مستخدم", type="primary", use_container_width=True):
        if not new_username.strip():
            st.warning("⚠ يرجى إدخال اسم المستخدم.")
        elif not new_password.strip():
            st.warning("⚠ يرجى إدخال كلمة المرور.")
        elif new_password != confirm_password:
            st.warning("⚠ كلمتا المرور غير متطابقتين.")
        elif new_username in users:
            st.warning("⚠ هذا المستخدم موجود بالفعل.")
        else:
            users[new_username] = {
                "password": new_password,
                "role": "admin",
                "permissions": ["all"],
                "created_at": datetime.now().isoformat(),
                "full_name": new_fullname or new_username
            }
            if save_users(users):
                st.success(f"✅ تم إضافة المستخدم '{new_username}' بنجاح.")
                st.rerun()

# -------------------------------
# Tab 4: الدعم الفني
# -------------------------------
with tabs[3]:
    st.header("📞 الدعم الفني")
    
    st.markdown("## 🛠 معلومات التطوير والدعم")
    st.markdown("تم تطوير هذا التطبيق بواسطة:")
    st.markdown("### م. محمد عبدالله")
    st.markdown("### رئيس قسم الكرد والمحطات")
    st.markdown("### مصنع بيل يارن للغزل")
    
    st.markdown("---")
    st.markdown("### معلومات الاتصال:")
    st.markdown("- 📧 البريد الإلكتروني: m.abdallah@bailyarn.com")
    st.markdown("- 📞 هاتف المصنع: 01000000000")
    
    st.markdown("---")
    st.markdown("### إصدار النظام:")
    st.markdown("- الإصدار: 3.0")
    st.markdown("- آخر تحديث: 2024")
    st.markdown("- النظام: نظام إدارة محطات الإنتاج")
    
    st.markdown("---")
    st.success("""
    *مميزات النظام:*
    - ✅ الحفظ التلقائي الفوري على GitHub
    - ✅ عرض وتعديل البيانات من أي مكان
    - ✅ دعم كامل للغة العربية
    - ✅ إدارة مستخدمين متعددة
    - ✅ نسخ احتياطي تلقائي
    """)
    
    # أزرار فنية
    st.markdown("### 🔧 أدوات فنية")
    
    if st.button("فحص اتصال GitHub", use_container_width=True):
        if fetch_production_from_github():
            st.success("✅ الاتصال مع GitHub يعمل بشكل صحيح")
        else:
            st.error("❌ هناك مشكلة في الاتصال مع GitHub")

# -------------------------------
# تذييل الصفحة
# -------------------------------
st.markdown("---")
footer_col1, footer_col2, footer_col3 = st.columns(3)
with footer_col1:
    st.caption(f"👤 {st.session_state.get('user_fullname', 'زائر')}")
with footer_col2:
    st.caption(f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
with footer_col3:
    st.caption("مصنع بيل يارن للغزل © 2024")

# تهيئة session state إذا لزم الأمر
if 'file_sha' not in st.session_state:
    st.session_state.file_sha = None
if 'file_url' not in st.session_state:
    st.session_state.file_url = None
