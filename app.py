import streamlit as st
import pandas as pd
import requests
import base64
from io import BytesIO
import os

# إعداد الصفحة
st.set_page_config(page_title="GitHub Excel Editor", layout="wide", page_icon="📊")
st.title("📊 محرر Excel من GitHub")

# معلومات GitHub - يمكن تعيينها كمتغيرات بيئة
st.sidebar.header("إعدادات GitHub")

# يمكن تعيين القيم الافتراضية هنا
repo_owner = st.sidebar.text_input("mahmedabdallh123", value="your-username")
repo_name = st.sidebar.text_input("Maintain-luva", value="your-repo-name") 
file_path = st.sidebar.text_input("مسار ملف", value="data/stations.xlsx")
branch = st.sidebar.text_input("main", value="main")

# استخدام token من متغيرات البيئة أو من input
github_token = st.sidebar.text_input("GitHub Token", type="password", value=os.getenv('GITHUB_TOKEN', ''))

def get_file_from_github():
    """جلب ملف Excel من GitHub"""
    try:
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{file_path}?ref={branch}"
        headers = {"Authorization": f"token {github_token}"}
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            content = response.json()['content']
            file_content = base64.b64decode(content)
            return file_content, response.json()['sha'], response.json().get('html_url')
        else:
            st.error(f"خطأ في جلب الملف: {response.status_code} - {response.json().get('message', '')}")
            return None, None, None
    except Exception as e:
        st.error(f"خطأ: {str(e)}")
        return None, None, None

def save_file_to_github(df_dict, sha, commit_message):
    """حفظ الملف إلى GitHub"""
    try:
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{file_path}"
        
        # تحويل جميع DataFrames إلى Excel في الذاكرة
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            for sheet_name, df in df_dict.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        content_base64 = base64.b64encode(output.getvalue()).decode()
        
        data = {
            "message": commit_message,
            "content": content_base64,
            "sha": sha,
            "branch": branch
        }
        
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.put(url, json=data, headers=headers)
        
        if response.status_code == 200:
            return True, response.json()['commit']['html_url']
        else:
            st.error(f"خطأ في الحفظ: {response.status_code} - {response.json().get('message', '')}")
            return False, None
            
    except Exception as e:
        st.error(f"خطأ في الحفظ: {str(e)}")
        return False, None

def get_all_sheets(excel_file):
    """قراءة جميع أوراق Excel"""
    try:
        excel_data = pd.ExcelFile(excel_file)
        sheets_data = {}
        for sheet_name in excel_data.sheet_names:
            sheets_data[sheet_name] = pd.read_excel(excel_file, sheet_name=sheet_name)
        return sheets_data, excel_data.sheet_names
    except Exception as e:
        st.error(f"خطأ في قراءة الملف: {str(e)}")
        return {}, []

# زر تحميل البيانات
if st.sidebar.button("🔄 تحميل البيانات من GitHub"):
    if not all([repo_owner, repo_name, file_path, github_token]):
        st.error("⚠ يرجى ملء جميع حقول GitHub")
    else:
        with st.spinner("جاري تحميل البيانات من GitHub..."):
            file_content, file_sha, file_url = get_file_from_github()
            
            if file_content:
                st.session_state.file_content = file_content
                st.session_state.file_sha = file_sha
                st.session_state.file_url = file_url
                st.session_state.sheets_data, st.session_state.sheet_names = get_all_sheets(BytesIO(file_content))
                st.success(f"✅ تم تحميل البيانات بنجاح من: {repo_owner}/{repo_name}")

# عرض الرابط إذا كان الملف محملاً
if 'file_url' in st.session_state and st.session_state.file_url:
    st.sidebar.markdown(f"[📎 عرض الملف على GitHub]({st.session_state.file_url})")

# عرض البيانات إذا كانت محملة
if 'sheets_data' in st.session_state and st.session_state.sheets_data:
    sheets_data = st.session_state.sheets_data
    sheet_names = st.session_state.sheet_names
    
    # تبويبات للتنقل بين الأوراق
    selected_sheet = st.selectbox("اختر الورقة", sheet_names)
    
    if selected_sheet:
        df = sheets_data[selected_sheet]
        
        st.header(f"📋 {selected_sheet}")
        
        # عرض معلومات عن البيانات
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info(f"📊 عدد الصفوف: {len(df)}")
        with col2:
            st.info(f"🏷 عدد الأعمدة: {len(df.columns)}")
        with col3:
            st.info(f"📝 نوع البيانات: Excel")
        
        # عرض الأعمدة المتاحة
        st.subheader("الأعمدة المتاحة")
        st.write(df.columns.tolist())
        
        # اختيار الأعمدة للعرض
        selected_columns = st.multiselect(
            "اختر الأعمدة للعرض:",
            options=df.columns.tolist(),
            default=df.columns.tolist()
        )
        
        if selected_columns:
            # محرر البيانات
            st.subheader("محرر البيانات")
            st.write("يمكنك تعديل البيانات مباشرة في الجدول أدناه:")
            
            # استخدام data_editor للتعديل المباشر
            edited_df = st.data_editor(
                df[selected_columns],
                use_container_width=True,
                height=400,
                num_rows="dynamic"
            )
            
            # زر الحفظ
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                commit_message = st.text_input("رسالة الحفظ", value=f"تم تحديث {selected_sheet}")
                
                if st.button("💾 حفظ التغييرات على GitHub", type="primary"):
                    if not github_token:
                        st.error("⚠ يرجى إدخال GitHub Token")
                    else:
                        # تحديث البيانات في session state
                        updated_sheets_data = st.session_state.sheets_data.copy()
                        updated_sheets_data[selected_sheet] = edited_df
                        
                        with st.spinner("جاري حفظ التغييرات على GitHub..."):
                            success, commit_url = save_file_to_github(
                                updated_sheets_data, 
                                st.session_state.file_sha, 
                                commit_message
                            )
                            
                            if success:
                                st.success("✅ تم حفظ التغييرات بنجاح!")
                                st.session_state.sheets_data = updated_sheets_data
                                st.session_state.file_sha = requests.get(
                                    f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{file_path}",
                                    headers={"Authorization": f"token {github_token}"}
                                ).json()['sha']
                                
                                if commit_url:
                                    st.markdown(f"[📎 عرض التعديل على GitHub]({commit_url})")

# إضافة تعليمات الاستخدام
with st.sidebar.expander("🆘 تعليمات الاستخدام"):
    st.markdown("""
    *كيفية الاستخدام:*
    1. أدخل معلومات GitHub
    2. اضغط على "تحميل البيانات"
    3. اختر الورقة المطلوبة
    4. عدل البيانات مباشرة في الجدول
    5. أدخل رسالة الحفظ
    6. اضغط على "حفظ التغييرات"

    *المتطلبات:*
    - GitHub Token مع صلاحيات repo
    - ملف Excel موجود في المستودع
    - اتصال بالإنترنت
    """)

# معلومات إضافية
st.sidebar.markdown("---")
st.sidebar.info("""
*المميزات:*
- ✅ قراءة تلقائية لجميع الأوراق
- ✏ تعديل مباشر على البيانات
- 💾 حفظ تلقائي على GitHub
- 🔄 تحديث فوري
- 📊 دعم كامل للغة العربية
""")
