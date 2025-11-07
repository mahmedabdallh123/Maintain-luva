import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="نظام فلترة وتحميل البيانات", layout="wide")

st.title("📊 نظام فلترة بيانات ديناميكي وتحميل النتائج")

uploaded_file = st.file_uploader("📁 اختر ملف Excel أو CSV", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    # ===============================
    # قراءة الملف
    # ===============================
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.success("✅ تم تحميل الملف بنجاح!")
    st.write(f"*عدد الصفوف:* {df.shape[0]} — *عدد الأعمدة:* {df.shape[1]}")
    st.dataframe(df.head(), use_container_width=True)

    st.divider()

    # ===============================
    # 🧠 التصفية بالنصوص
    # ===============================
    text_columns = df.select_dtypes(include=["object"]).columns
    filtered_df = df.copy()

    if len(text_columns) > 0:
        st.subheader("🔤 تصفية نصية")
        text_filter_column = st.selectbox("اختر العمود النصي:", text_columns)
        keyword = st.text_input("أدخل الكلمة أو جزء منها للبحث:")

        if st.button("تطبيق التصفية النصية"):
            filtered_df = filtered_df[filtered_df[text_filter_column].astype(str).str.contains(keyword, case=False, na=False)]
            st.dataframe(filtered_df, use_container_width=True)
            st.info(f"تم عرض {filtered_df.shape[0]} صف من أصل {df.shape[0]}")
    else:
        st.info("ℹ لا توجد أعمدة نصية في هذا الملف.")

    st.divider()

    # ===============================
    # 🔢 التصفية الرقمية
    # ===============================
    numeric_columns = df.select_dtypes(include=["number"]).columns
    st.subheader("🔢 تصفية رقمية")

    if len(numeric_columns) > 0:
        num_filter_column = st.selectbox("اختر عمود رقمي:", numeric_columns)

        # التحقق من وجود قيم رقمية حقيقية
        numeric_series = df[num_filter_column].dropna()
        if numeric_series.empty:
            st.warning(f"⚠ العمود '{num_filter_column}' لا يحتوي على قيم رقمية صالحة.")
        else:
            min_val = float(numeric_series.min())
            max_val = float(numeric_series.max())

            selected_min, selected_max = st.slider(
                f"اختر مدى {num_filter_column}:",
                min_val, max_val, (min_val, max_val)
            )

            if st.button("تطبيق التصفية الرقمية"):
                filtered_df = filtered_df[
                    (filtered_df[num_filter_column] >= selected_min) &
                    (filtered_df[num_filter_column] <= selected_max)
                ]
                st.dataframe(filtered_df, use_container_width=True)
                st.info(f"تم عرض {filtered_df.shape[0]} صف من أصل {df.shape[0]}")
    else:
        st.info("ℹ لا توجد أعمدة رقمية قابلة للتصفية في هذا الشيت.")

    st.divider()

    # ===============================
    # 💾 زر تحميل النتائج المفلترة
    # ===============================
    if not filtered_df.empty:
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            filtered_df.to_excel(writer, index=False, sheet_name="FilteredData")
        st.download_button(
            label="⬇ تحميل النتائج كملف Excel",
            data=buffer.getvalue(),
            file_name="filtered_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.warning("⬆ من فضلك حمّل ملف Excel أو CSV للبدء.")
