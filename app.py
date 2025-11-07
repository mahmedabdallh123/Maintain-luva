import streamlit as st
import pandas as pd
import json
import os
import io
import requests
import shutil
import re
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
    "APP_TITLE": "نظام إدارة صيانه المحطات",
    "APP_ICON": "🏭",
    
    # إعدادات GitHub
    "REPO_NAME": "mahmedabdallh123/Maintain-luva",
    "BRANCH": "main",
    "PRODUCTION_FILE_PATH": "station.xlsx",
    "LOCAL_PRODUCTION_FILE": "station.xlsx",
    
    # إعدادات الأمان
    "MAX_ACTIVE_USERS": 5,
    "SESSION_DURATION_MINUTES": 120,
    
    # إعدادات الواجهة
    "SHOW_TECH_SUPPORT_TO_ALL": True,
    "CUSTOM_TABS": ["📊 عرض المحطات", "✏ تعديل البيانات", "📈 الإحصائيات", "👥 إدارة المستخدمين", "📞 الدعم الفني"]
}

# ===============================
# 🗂 إعدادات الملفات
# ===============================
USERS_FILE = "users.json"
STATE_FILE = "state.json"
SESSION_DURATION = timedelta(minutes=APP_CONFIG["SESSION_DURATION_MINUTES"])
MAX_ACTIVE_USERS = APP_CONFIG["MAX_ACTIVE_USERS"]

# إنشاء رابط GitHub تلقائياً من الإعدادات
PRODUCTION_GITHUB_URL = f"https://github.com/{APP_CONFIG['REPO_NAME'].split('/')[0]}/{APP_CONFIG['REPO_NAME'].split('/')[1]}/raw/{APP_CONFIG['BRANCH']}/{APP_CONFIG['PRODUCTION_FILE_PATH']}"

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
                "permissions": ["data_entry", "view_stats"]
            }
        }
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_users, f, indent=4, ensure_ascii=False)
        return default_users
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
            return users
    except Exception as e:
        st.error(f"❌ خطأ في ملف users.json: {e}")
        return {
            "admin": {"password": "1111", "role": "admin", "permissions": ["all"], "created_at": datetime.now().isoformat()}
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
    
    for key in list(st.session_state.keys()):
        if key != "rerun":
            st.session_state.pop(key)
    
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
                if username_input in active_users and username_input != "admin":
                    st.warning("⚠ هذا المستخدم مسجل دخول بالفعل.")
                    return False
                elif active_count >= MAX_ACTIVE_USERS and username_input != "admin":
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
# 🔄 طرق جلب الملف من GitHub
# -------------------------------
def fetch_production_from_github():
    """تحميل ملف الإنتاج من GitHub"""
    try:
        # إنشاء ملف مؤقت للتحميل
        temp_file = "temp_production_data.xlsx"
        
        response = requests.get(PRODUCTION_GITHUB_URL, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(temp_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        # إذا كان التحميل ناجحاً، انقل الملف إلى الموقع الدائم
        if os.path.exists(temp_file):
            if os.path.exists(APP_CONFIG["LOCAL_PRODUCTION_FILE"]):
                os.remove(APP_CONFIG["LOCAL_PRODUCTION_FILE"])
            os.rename(temp_file, APP_CONFIG["LOCAL_PRODUCTION_FILE"])
        
        # مسح الكاش
        try:
            st.cache_data.clear()
        except:
            pass
            
        return True
    except Exception as e:
        # إذا فشل التحميل، احذف الملف المؤقت إذا كان موجوداً
        if os.path.exists("temp_production_data.xlsx"):
            os.remove("temp_production_data.xlsx")
        st.error(f"⚠ فشل التحديث من GitHub: {str(e)}")
        return False

# -------------------------------
# 📂 تحميل البيانات
# -------------------------------
@st.cache_data(show_spinner=False, ttl=300)
def load_production_data():
    """تحميل بيانات محطات الإنتاج"""
    if not os.path.exists(APP_CONFIG["LOCAL_PRODUCTION_FILE"]):
        st.warning("⚠ لم يتم العثور على ملف الإنتاج. يرجى تحديث الملف من GitHub.")
        return {}
    
    try:
        # قراءة جميع الشيتات في ملف Excel
        excel_file = pd.ExcelFile(APP_CONFIG["LOCAL_PRODUCTION_FILE"])
        sheets_data = {}
        
        for sheet_name in excel_file.sheet_names:
            try:
                df = pd.read_excel(APP_CONFIG["LOCAL_PRODUCTION_FILE"], sheet_name=sheet_name)
                
                # تنظيف البيانات - معالجة الأعمدة الرقمية بشكل آمن
                for col in df.columns:
                    if df[col].dtype == 'object':
                        try:
                            # محاولة تحويل الأعمدة النصية إلى رقمية إذا أمكن
                            converted = pd.to_numeric(df[col], errors='coerce')
                            # إذا تم تحويل أكثر من 50% من القيم بنجاح، استخدم الأعمدة الرقمية
                            if converted.notna().sum() > len(df) * 0.5:
                                df[col] = converted
                        except:
                            pass
                
                sheets_data[sheet_name] = df
            except Exception as e:
                st.error(f"❌ خطأ في تحميل شيت {sheet_name}: {str(e)}")
                continue
        
        return sheets_data
    except Exception as e:
        st.error(f"❌ خطأ في تحميل بيانات الإنتاج: {str(e)}")
        return {}

def get_all_sheets():
    """الحصول على قائمة جميع الشيتات المتاحة"""
    sheets_data = load_production_data()
    return list(sheets_data.keys()) if sheets_data else []

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
    """حفظ بيانات الإنتاج إلى ملف Excel"""
    try:
        with pd.ExcelWriter(APP_CONFIG["LOCAL_PRODUCTION_FILE"], engine='openpyxl') as writer:
            for sheet_name, df in sheets_data.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        # امسح الكاش
        try:
            st.cache_data.clear()
        except:
            pass

        return True
    except Exception as e:
        st.error(f"❌ خطأ في حفظ البيانات: {str(e)}")
        return False

def update_sheet_data(sheet_name, updated_df):
    """تحديث بيانات شيت معين"""
    sheets_data = load_production_data()
    if sheet_name in sheets_data:
        sheets_data[sheet_name] = updated_df
        return save_production_data(sheets_data, f"تحديث بيانات {sheet_name}")
    return False

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
            "can_see_tech_support": APP_CONFIG["SHOW_TECH_SUPPORT_TO_ALL"]
        }
    else:  # viewer
        return {
            "can_input": False,
            "can_view_stats": True,
            "can_manage_users": False,
            "can_see_tech_support": APP_CONFIG["SHOW_TECH_SUPPORT_TO_ALL"]
        }

def generate_sheet_statistics(df, sheet_name):
    """توليد إحصائيات للشيت المحدد"""
    if df.empty:
        return pd.DataFrame()
    
    stats = {
        'المعيار': ['عدد الصفوف', 'عدد الأعمدة', 'البيانات غير الفارغة'],
        'القيمة': [len(df), len(df.columns), df.count().sum()]
    }
    
    # إحصائيات عددية للأعمدة الرقمية فقط
    numeric_columns = df.select_dtypes(include=['number']).columns
    if len(numeric_columns) > 0:
        for col in numeric_columns:
            if df[col].notna().any():  # التأكد من وجود بيانات رقمية
                stats['المعيار'].extend([f'متوسط {col}', f'أقل {col}', f'أعلى {col}', f'مجموع {col}'])
                stats['القيمة'].extend([
                    f"{df[col].mean():.2f}" if not pd.isna(df[col].mean()) else "N/A",
                    f"{df[col].min():.2f}" if not pd.isna(df[col].min()) else "N/A",
                    f"{df[col].max():.2f}" if not pd.isna(df[col].max()) else "N/A",
                    f"{df[col].sum():.2f}" if not pd.isna(df[col].sum()) else "N/A"
                ])
    
    return pd.DataFrame(stats)

def safe_numeric_filter(df, column):
    """تصفية آمنة للأعمدة الرقمية"""
    try:
        # التأكد من أن العمود رقمي وأن هناك بيانات
        if df[column].dtype in ['int64', 'float64'] and df[column].notna().any():
            min_val = float(df[column].min())
            max_val = float(df[column].max())
            
            # إذا كانت القيم كلها متشابهة، نضيف مدى صغير
            if min_val == max_val:
                min_val = min_val - 0.1
                max_val = max_val + 0.1
            
            st.write(f"*مدى القيم في {column}:* من {min_val:.2f} إلى {max_val:.2f}")
            
            selected_min, selected_max = st.slider(
                f"اختر مدى {column}:",
                min_val, max_val, (min_val, max_val),
                key=f"slider_{column}"
            )
            
            filtered_df = df[(df[column] >= selected_min) & (df[column] <= selected_max)]
            return filtered_df
        else:
            st.warning(f"العمود {column} لا يحتوي على بيانات رقمية كافية للتصفية")
            return df
    except Exception as e:
        st.error(f"خطأ في التصفية: {str(e)}")
        return df

# -------------------------------
# 🖥 الواجهة الرئيسية
# -------------------------------
def main():
    st.set_page_config(
        page_title=APP_CONFIG["APP_TITLE"], 
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # شريط تسجيل الدخول
    with st.sidebar:
        st.header("👤 الجلسة")
        if not st.session_state.get("logged_in"):
            if not login_ui():
                return
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
            with st.spinner("جاري تحديث البيانات..."):
                if fetch_production_from_github():
                    st.success("✅ تم تحديث البيانات بنجاح")
                    st.rerun()
                else:
                    st.error("❌ فشل تحديث البيانات")
        
        if st.button("🗑 مسح الكاش"):
            try:
                st.cache_data.clear()
                st.success("✅ تم مسح الكاش بنجاح")
                st.rerun()
            except Exception as e:
                st.error(f"❌ خطأ في مسح الكاش: {str(e)}")
        
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
    tab_names = ["📊 عرض المحطات", "📈 الإحصائيات"]
    
    if permissions["can_input"]:
        tab_names.insert(1, "✏ تعديل البيانات")
    
    if permissions["can_manage_users"]:
        tab_names.append("👥 إدارة المستخدمين")
    
    if permissions["can_see_tech_support"]:
        tab_names.append("📞 الدعم الفني")

    tabs = st.tabs(tab_names)

    # -------------------------------
    # Tab 1: عرض المحطات
    # -------------------------------
    with tabs[0]:
        st.header("📊 عرض بيانات المحطات")
        
        if not production_data:
            st.warning("⚠ لا توجد بيانات متاحة. يرجى تحديث الملف من GitHub.")
        else:
            available_sheets = get_all_sheets()
            if not available_sheets:
                st.error("❌ لا توجد شيتات متاحة في الملف")
            else:
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
                    
                    # خيارات التصفية البسيطة
                    st.subheader("🔍 تصفية البيانات")
                    
                    # تصفية حسب الأعمدة النصية
                    text_columns = df.select_dtypes(include=['object']).columns
                    if len(text_columns) > 0:
                        filter_column = st.selectbox("اختر عمود للتصفية النصية:", text_columns)
                        unique_values = df[filter_column].dropna().unique()
                        if len(unique_values) > 0:
                            selected_value = st.selectbox("اختر قيمة:", unique_values)
                            
                            if st.button("تطبيق التصفية النصية"):
                                filtered_df = df[df[filter_column] == selected_value]
                                st.dataframe(filtered_df, use_container_width=True)
                    
                    # تصفية حسب الأعمدة الرقمية
                    numeric_columns = df.select_dtypes(include=['number']).columns
                    if len(numeric_columns) > 0:
                        num_column = st.selectbox("اختر عمود رقمي للتصفية:", numeric_columns)
                        if st.button("تطبيق التصفية الرقمية"):
                            filtered_df = safe_numeric_filter(df, num_column)
                            if filtered_df is not None:
                                st.dataframe(filtered_df, use_container_width=True)

    # -------------------------------
    # Tab 2: تعديل البيانات
    # -------------------------------
    if permissions["can_input"] and "✏ تعديل البيانات" in tab_names:
        tab_index = tab_names.index("✏ تعديل البيانات")
        with tabs[tab_index]:
            st.header("✏ تعديل بيانات المحطات")
            
            if not production_data:
                st.warning("⚠ لا توجد بيانات متاحة. يرجى تحديث الملف من GitHub.")
            else:
                available_sheets = get_all_sheets()
                if not available_sheets:
                    st.error("❌ لا توجد شيتات متاحة في الملف")
                else:
                    selected_sheet = st.selectbox(
                        "📋 اختر المحطة أو القسم للتعديل:",
                        available_sheets,
                        key="edit_sheet_select"
                    )
                    
                    if selected_sheet:
                        df = production_data[selected_sheet]
                        
                        st.subheader(f"تعديل بيانات {selected_sheet}")
                        st.info("💡 يمكنك تعديل البيانات مباشرة في الجدول أدناه")
                        
                        # استخدام محرر البيانات
                        try:
                            edited_df = st.data_editor(
                                df,
                                use_container_width=True,
                                height=400,
                                num_rows="dynamic",
                                key=f"editor_{selected_sheet}"
                            )
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                if st.button("💾 حفظ التغييرات", type="primary"):
                                    if update_sheet_data(selected_sheet, edited_df):
                                        st.success("✅ تم حفظ التغييرات بنجاح")
                                        st.rerun()
                                    else:
                                        st.error("❌ فشل حفظ التغييرات")
                            
                            with col2:
                                if st.button("🔄 إعادة تحميل"):
                                    st.rerun()
                            
                        except Exception as e:
                            st.error(f"❌ خطأ في تحرير البيانات: {str(e)}")

    # -------------------------------
    # Tab الإحصائيات
    # -------------------------------
    stats_tab_index = tab_names.index("📈 الإحصائيات")
    with tabs[stats_tab_index]:
        st.header("📈 إحصائيات المحطات")
        
        if not production_data:
            st.warning("⚠ لا توجد بيانات متاحة.")
        else:
            available_sheets = get_all_sheets()
            if not available_sheets:
                st.error("❌ لا توجد شيتات متاحة في الملف")
            else:
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
                    else:
                        st.info("⚠ لا توجد إحصائيات رقمية متاحة للعرض")
                    
                    # عرض بسيط للبيانات الرقمية
                    numeric_columns = df.select_dtypes(include=['number']).columns
                    if len(numeric_columns) > 0:
                        st.subheader("📊 البيانات الرقمية")
                        st.dataframe(df[numeric_columns].describe(), use_container_width=True)

    # -------------------------------
    # Tab إدارة المستخدمين
    # -------------------------------
    if permissions["can_manage_users"] and "👥 إدارة المستخدمين" in tab_names:
        tab_index = tab_names.index("👥 إدارة المستخدمين")
        with tabs[tab_index]:
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
                        permissions_list = ["data_entry", "view_stats"]
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
    # Tab الدعم الفني
    # -------------------------------
    if permissions["can_see_tech_support"] and "📞 الدعم الفني" in tab_names:
        tab_index = tab_names.index("📞 الدعم الفني")
        with tabs[tab_index]:
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
            st.markdown("- الإصدار: 2.0 (مستقر)")
            st.markdown("- آخر تحديث: 2024")
            st.markdown("- النظام: نظام إدارة محطات الإنتاج")
            
            st.info("""
            *ملاحظات مهمة:*
            - النظام يدعم جميع أنواع ملفات Excel متعددة الشيتات
            - يمكن عرض وتعديل أي شيت تلقائياً
            - في حالة وجود أي مشاكل، يرجى التواصل مع الدعم الفني
            """)

if _name_ == "_main_":
   
