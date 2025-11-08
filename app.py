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
    GITHUB_AVAILABLE = True

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
    "MAX_ACTIVE_USERS": 5,
    "SESSION_DURATION_MINUTES": 11,
    
    # إعدادات الواجهة
    "SHOW_TECH_SUPPORT_TO_ALL": False,
    "CUSTOM_TABS": ["📊 عرض المحطات", "✏ تعديل البيانات", "📈 الإحصائيات", "👥 إدارة المستخدمين", "📞 الدعم الفني"]
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
                "permissions": ["all"]
            },
            "user1": {
                "password": "12345", 
                "role": "data_entry", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["data_entry"]
            }
        }
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_users, f, indent=4, ensure_ascii=False)
        return default_users
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"❌ خطأ في ملف users.json: {e}")
        return {
            "admin": {"password": "1111", "role": "admin", "permissions": ["all"], "created_at": datetime.now().isoformat()},
            "user1": {"password": "12345", "role": "data_entry", "permissions": ["data_entry"], "created_at": datetime.now().isoformat()}
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

    st.title(f"{APP_CONFIG['APP_ICON']} تسجيل الدخول - {APP_CONFIG['APP_TITLE']}")

    username_input = st.selectbox("👤 اختر المستخدم", list(users.keys()))
    password = st.text_input("🔑 كلمة المرور", type="password")

    active_users = [u for u, v in state.items() if v.get("active")]
    active_count = len(active_users)
    st.caption(f"🔒 المستخدمون النشطون الآن: {active_count} / {MAX_ACTIVE_USERS}")

    if not st.session_state.logged_in:
        if st.button("تسجيل الدخول"):
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
                st.session_state.user_role = users[username_input].get("role", "viewer")
                st.session_state.user_permissions = users[username_input].get("permissions", ["view_stats"])
                st.success(f"✅ تم تسجيل الدخول: {username_input} ({st.session_state.user_role})")
                st.rerun()
            else:
                st.error("❌ كلمة المرور غير صحيحة.")
        return False
    else:
        username = st.session_state.username
        user_role = st.session_state.user_role
        st.success(f"✅ مسجل الدخول كـ: {username} ({user_role})")
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
        
        response = requests.get(url, headers=headers)
        
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
        
        response = requests.put(url, json=data, headers=headers)
        
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
                # حفظ الملف محلياً
                with open(APP_CONFIG["LOCAL_PRODUCTION_FILE"], "wb") as f:
                    f.write(file_content)
                
                # تحديث session state
                st.session_state.file_sha = file_sha
                st.session_state.file_url = file_url
                
                # مسح الكاش
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
        # قراءة جميع الشيتات في ملف Excel
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
    """تحديث بيانات شيت معين"""
    sheets_data = load_production_data()
    sheets_data[sheet_name] = updated_df
    return save_production_data(sheets_data, f"تحديث بيانات {sheet_name}")

# -------------------------------
# 🧮 دوال مساعدة للنظام
# -------------------------------
def get_user_permissions(user_role, user_permissions):
    """الحصول على صلاحيات المستخدم"""
    if "all" in user_permissions:
        return {
            "can_input": True,
            "can_view_stats": True,
            "can_manage_users": True,
            "can_see_tech_support": True
        }
    elif "data_entry" in user_permissions:
        return {
            "can_input": True,
            "can_view_stats": True,
            "can_manage_users": False,
            "can_see_tech_support": False
        }
    elif "view_stats" in user_permissions:
        return {
            "can_input": False,
            "can_view_stats": True,
            "can_manage_users": False,
            "can_see_tech_support": False
        }
    else:
        return {
            "can_input": False,
            "can_view_stats": True,
            "can_manage_users": False,
            "can_see_tech_support": False
        }

def generate_sheet_statistics(df, sheet_name):
    """توليد إحصائيات للشيت المحدد"""
    if df.empty:
        return pd.DataFrame()
    
    stats = {
        'المعيار': ['عدد الصفوف', 'عدد الأعمدة', 'البيانات غير الفارغة'],
        'القيمة': [len(df), len(df.columns), df.count().sum()]
    }
    
    # إحصائيات عددية للأعمدة الرقمية
    numeric_columns = df.select_dtypes(include=['number']).columns
    if len(numeric_columns) > 0:
        for col in numeric_columns:
            stats['المعيار'].extend([f'متوسط {col}', f'أقل {col}', f'أعلى {col}', f'مجموع {col}'])
            stats['القيمة'].extend([
                df[col].mean().round(2),
                df[col].min(),
                df[col].max(),
                df[col].sum()
            ])
    
    return pd.DataFrame(stats)

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
        user_role = st.session_state.user_role
        rem = remaining_time(state, username)
        if rem:
            mins, secs = divmod(int(rem.total_seconds()), 60)
            st.success(f"👋 {username} | الدور: {user_role} | ⏳ {mins:02d}:{secs:02d}")
        else:
            logout_action()

    st.markdown("---")
    st.write("🔧 أدوات النظام:")
    
    if st.button("🔄 تحديث الملف من GitHub"):
        if fetch_production_from_github():
            st.success("✅ تم تحديث البيانات بنجاح")
            st.rerun()
        else:
            st.error("❌ فشل في تحديث البيانات")
    
    if st.button("🗑 مسح الكاش"):
        try:
            st.cache_data.clear()
            st.success("✅ تم مسح الكاش بنجاح")
            st.rerun()
        except Exception as e:
            st.error(f"❌ خطأ في مسح الكاش: {e}")
    
    st.markdown("---")
    if st.button("🚪 تسجيل الخروج"):
        logout_action()

# تحميل البيانات
production_data = load_production_data()

# واجهة التبويبات الرئيسية
st.title(f"{APP_CONFIG['APP_ICON']} {APP_CONFIG['APP_TITLE']}")

# التحقق من الصلاحيات
username = st.session_state.get("username")
user_role = st.session_state.get("user_role", "viewer")
user_permissions = st.session_state.get("user_permissions", ["view_stats"])
permissions = get_user_permissions(user_role, user_permissions)

# تحديد التبويبات بناءً على الصلاحيات
if permissions["can_manage_users"]:
    tabs = st.tabs(APP_CONFIG["CUSTOM_TABS"])
elif permissions["can_input"]:
    tabs = st.tabs(["📊 عرض المحطات", "✏ تعديل البيانات", "📈 الإحصائيات"])
else:
    tabs = st.tabs(["📊 عرض المحطات", "📈 الإحصائيات"])

# -------------------------------
# Tab 1: عرض المحطات
# -------------------------------
if len(tabs) > 0:
    with tabs[0]:
        st.header("📊 عرض بيانات المحطات")
        
        if not production_data:
            st.warning("⚠ لا توجد بيانات متاحة. يرجى تحديث الملف من GitHub أو إضافة بيانات جديدة.")
        else:
            # اختيار الشيت المطلوب
            available_sheets = get_all_sheets()
            selected_sheet = st.selectbox(
                "📋 اختر المحطة أو القسم:",
                available_sheets,
                key="view_sheet_select"
            )
            
            if selected_sheet:
                df = production_data[selected_sheet]
                
                st.subheader(f"بيانات {selected_sheet}")
                
                # عرض معلومات عن الشيت
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("عدد الصفوف", len(df))
                with col2:
                    st.metric("عدد الأعمدة", len(df.columns))
                with col3:
                    st.metric("إجمالي البيانات", df.count().sum())
                
                # عرض البيانات
                st.dataframe(df, use_container_width=True, height=400)
                
                # خيارات التصفية النصية فقط
                st.subheader("🔍 تصفية البيانات")
                text_columns = df.select_dtypes(include=['object']).columns
                if len(text_columns) > 0:
                    filter_column = st.selectbox("اختر عمود للتصفية:", text_columns)
                    unique_values = df[filter_column].unique()
                    selected_value = st.selectbox("اختر قيمة:", unique_values)
                    
                    if st.button("تطبيق التصفية"):
                        filtered_df = df[df[filter_column] == selected_value]
                        st.dataframe(filtered_df, use_container_width=True)

# -------------------------------
# Tab 2: تعديل البيانات (للمستخدمين الذين لديهم صلاحية التعديل)
# -------------------------------
if permissions["can_input"] and len(tabs) > 1:
    with tabs[1]:
        st.header("✏ تعديل بيانات المحطات")
        
        if not production_data:
            st.warning("⚠ لا توجد بيانات متاحة. يرجى تحديث الملف من GitHub.")
        else:
            # اختيار الشيت للتعديل
            available_sheets = get_all_sheets()
            selected_sheet = st.selectbox(
                "📋 اختر المحطة أو القسم للتعديل:",
                available_sheets,
                key="edit_sheet_select"
            )
            
            if selected_sheet:
                df = production_data[selected_sheet]
                
                st.subheader(f"تعديل بيانات {selected_sheet}")
                st.info("💡 يمكنك تعديل البيانات مباشرة في الجدول أدناه، ثم حفظ التغييرات")
                
                # عرض محرر البيانات
                edited_df = st.data_editor(
                    df,
                    use_container_width=True,
                    height=500,
                    num_rows="dynamic",
                    key=f"editor_{selected_sheet}"
                )
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    commit_message = st.text_input("رسالة الحفظ", value=f"تحديث {selected_sheet}")
                    
                    if st.button("💾 حفظ التغييرات", type="primary"):
                        success, commit_url = update_sheet_data(selected_sheet, edited_df)
                        if success:
                            st.success("✅ تم حفظ التغييرات بنجاح")
                            if commit_url:
                                st.markdown(f"[📎 عرض التعديل على GitHub]({commit_url})")
                            st.rerun()
                        else:
                            st.error("❌ فشل في حفظ التغييرات")
                
                with col2:
                    if st.button("🔄 إعادة تحميل"):
                        st.rerun()
                
                with col3:
                    if st.button("📥 تصدير البيانات"):
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                            edited_df.to_excel(writer, sheet_name=selected_sheet, index=False)
                        
                        st.download_button(
                            label="تحميل كملف Excel",
                            data=buffer.getvalue(),
                            file_name=f"{selected_sheet}_{datetime.now().date()}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                
                # إضافة صف جديد
                st.subheader("➕ إضافة بيانات جديدة")
                with st.form(f"add_row_form_{selected_sheet}"):
                    new_row_data = {}
                    cols = st.columns(min(4, len(df.columns)))
                    
                    for i, column in enumerate(df.columns):
                        col_idx = i % 4
                        with cols[col_idx]:
                            if df[column].dtype in ['int64', 'float64']:
                                new_row_data[column] = st.number_input(
                                    f"{column}:",
                                    value=0.0,
                                    key=f"new_{column}_{selected_sheet}"
                                )
                            else:
                                new_row_data[column] = st.text_input(
                                    f"{column}:",
                                    key=f"new_{column}_{selected_sheet}"
                                )
                    
                    if st.form_submit_button("إضافة صف جديد"):
                        new_df = pd.concat([edited_df, pd.DataFrame([new_row_data])], ignore_index=True)
                        success, commit_url = update_sheet_data(selected_sheet, new_df)
                        if success:
                            st.success("✅ تم إضافة الصف الجديد بنجاح")
                            if commit_url:
                                st.markdown(f"[📎 عرض التعديل على GitHub]({commit_url})")
                            st.rerun()

# -------------------------------
# Tab 3: الإحصائيات
# -------------------------------
if len(tabs) > 2:
    with tabs[2]:
        st.header("📈 إحصائيات المحطات")
        
        if not production_data:
            st.warning("⚠ لا توجد بيانات متاحة.")
        else:
            # اختيار الشيت للإحصائيات
            available_sheets = get_all_sheets()
            selected_sheet = st.selectbox(
                "📋 اختر المحطة أو القسم للإحصائيات:",
                available_sheets,
                key="stats_sheet_select"
            )
            
            if selected_sheet:
                df = production_data[selected_sheet]
                
                st.subheader(f"إحصائيات {selected_sheet}")
                
                # الإحصائيات الأساسية
                stats_df = generate_sheet_statistics(df, selected_sheet)
                if not stats_df.empty:
                    st.dataframe(stats_df, use_container_width=True)

# -------------------------------
# Tab 4: إدارة المستخدمين (للمسؤول فقط)
# -------------------------------
if permissions["can_manage_users"] and len(tabs) > 3:
    with tabs[3]:
        st.header("👥 إدارة المستخدمين")
        
        users = load_users()
        
        # عرض المستخدمين الحاليين
        st.subheader("📋 المستخدمين الحاليين")
        if users:
            user_data = []
            for username, info in users.items():
                user_data.append({
                    "اسم المستخدم": username,
                    "الدور": info.get("role", "user"),
                    "الصلاحيات": ", ".join(info.get("permissions", [])),
                    "تاريخ الإنشاء": info.get("created_at", "غير معروف")
                })
            
            users_df = pd.DataFrame(user_data)
            st.dataframe(users_df, use_container_width=True)
        
        # إضافة مستخدم جديد
        st.subheader("➕ إضافة مستخدم جديد")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            new_username = st.text_input("اسم المستخدم الجديد:")
        with col2:
            new_password = st.text_input("كلمة المرور:", type="password")
        with col3:
            user_role = st.selectbox("الدور:", ["admin", "data_entry", "viewer"])
        
        if st.button("إضافة مستخدم"):
            if not new_username.strip() or not new_password.strip():
                st.warning("⚠ الرجاء إدخال اسم المستخدم وكلمة المرور.")
            elif new_username in users:
                st.warning("⚠ هذا المستخدم موجود بالفعل.")
            else:
                if user_role == "admin":
                    permissions_list = ["all"]
                elif user_role == "data_entry":
                    permissions_list = ["data_entry"]
                else:
                    permissions_list = ["view_stats"]
                
                users[new_username] = {
                    "password": new_password,
                    "role": user_role,
                    "permissions": permissions_list,
                    "created_at": datetime.now().isoformat()
                }
                if save_users(users):
                    st.success(f"✅ تم إضافة المستخدم '{new_username}' بنجاح.")
                    st.rerun()

# -------------------------------
# Tab 5: الدعم الفني
# -------------------------------
if len(tabs) > 4:
    with tabs[4]:
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
        st.markdown("- الإصدار: 1.0")
        st.markdown("- آخر تحديث: 2024")
        st.markdown("- النظام: نظام إدارة محطات الإنتاج")
        
        st.info("""
        *ملاحظات مهمة:*
        - النظام يدعم جميع أنواع ملفات Excel متعددة الشيتات
        - يمكن عرض وتعديل أي شيت تلقائياً دون الحاجة لتحديد الأعمدة
        - البيانات تحفظ تلقائياً على GitHub للنسخ الاحتياطي
        - يمكن تصدير البيانات بأي وقت كملف Excel
        """)
