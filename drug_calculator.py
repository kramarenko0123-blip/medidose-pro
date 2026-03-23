import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="MediDose Pro", page_icon="💊", layout="wide")

# Функция для получения информации о препарате из Excel
def get_drug_info_local(drug_name, df_indications):
    """Получение информации о препарате из локальной базы"""
    matching = df_indications[df_indications['drug_name'].str.contains(drug_name, case=False, na=False)]
    if not matching.empty:
        return matching.iloc[0]['indications']
    else:
        return None

# Расчет BSA
def calculate_bsa(weight, height):
    return round(np.sqrt((weight * height) / 3600), 2)

# Загрузка Excel
@st.cache_data
def load_data():
    try:
        excel_file = pd.ExcelFile('drug_database_full.xlsx')
        sheets = excel_file.sheet_names
        data = {}
        for sheet in sheets:
            df = excel_file.parse(sheet)
            for col in ['age_min', 'age_max', 'weight_min', 'weight_max', 'egfr_min', 'egfr_max']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            for col in ['dose_mg_per_kg', 'dose_mg_fixed', 'max_daily_mg']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            data[sheet] = df
        
        indications_df = None
        if 'Показания' in sheets:
            indications_df = excel_file.parse('Показания')
        
        return data, sheets, indications_df
    except Exception as e:
        return None, None, None

# Поиск строки
def find_matching_row(df, drug_name, age, weight, egfr=None):
    drug_df = df[df['generic_name'].str.contains(drug_name, case=False, na=False)]
    if drug_df.empty:
        return None, "Препарат не найден"
    
    age_matches = drug_df[
        (drug_df['age_min'].isna() | (age >= drug_df['age_min'])) &
        (drug_df['age_max'].isna() | (age <= drug_df['age_max']))
    ]
    if age_matches.empty:
        return None, f"Нет данных для возраста {age} лет"
    
    weight_matches = age_matches[
        (age_matches['weight_min'].isna() | (weight >= age_matches['weight_min'])) &
        (age_matches['weight_max'].isna() | (weight <= age_matches['weight_max']))
    ]
    if weight_matches.empty:
        return None, f"Нет данных для веса {weight} кг"
    
    if egfr is not None:
        egfr_matches = weight_matches[
            (weight_matches['egfr_min'].isna() | (egfr >= weight_matches['egfr_min'])) &
            (weight_matches['egfr_max'].isna() | (egfr <= weight_matches['egfr_max']))
        ]
        if not egfr_matches.empty:
            return egfr_matches.iloc[0], None
        no_egfr = weight_matches[weight_matches['egfr_min'].isna() & weight_matches['egfr_max'].isna()]
        if not no_egfr.empty:
            return no_egfr.iloc[0], None
        return None, f"Нет данных для СКФ {egfr}"
    
    return weight_matches.iloc[0], None

# Расчет дозы
def calculate_dose(row, weight):
    dose_per_kg = row.get('dose_mg_per_kg')
    dose_fixed = row.get('dose_mg_fixed')
    dose_unit = row.get('dose_unit', 'мг')
    frequency = row.get('frequency', '')
    max_daily = row.get('max_daily_mg')
    
    if pd.notna(dose_per_kg):
        calculated = dose_per_kg * weight
        warning = ""
        if pd.notna(max_daily) and calculated > max_daily:
            calculated = max_daily
            warning = f"⚠️ Ограничено макс. суточной: {max_daily} {dose_unit}"
        return {
            'type': 'Весозависимая',
            'single': f"{calculated:.0f} {dose_unit}",
            'daily': f"{calculated:.0f} {dose_unit}",
            'calc': f"{dose_per_kg} × {weight} = {calculated:.0f} {dose_unit}",
            'freq': frequency,
            'warning': warning
        }
    elif pd.notna(dose_fixed):
        return {
            'type': 'Фиксированная',
            'single': f"{dose_fixed} {dose_unit}",
            'daily': f"{dose_fixed} {dose_unit}",
            'calc': f"Фиксированная доза: {dose_fixed} {dose_unit}",
            'freq': frequency,
            'warning': ""
        }
    return {'error': 'Нет данных о дозировке'}

def main():
    data, sheets, indications_df = load_data()
    if data is None:
        st.error("❌ Файл drug_database_full.xlsx не найден!")
        return
    
    st.title("💊 MediDose Pro")
    st.markdown("Профессиональный калькулятор доз лекарственных препаратов")
    st.markdown("---")
    
    # Ввод данных
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📂 Выбор препарата")
        group = st.selectbox("Группа препаратов", sheets)
        df = data[group]
        
        search = st.text_input("🔍 Поиск препарата", placeholder="Введите название...")
        drugs = sorted(df['generic_name'].unique())
        if search:
            drugs = [d for d in drugs if search.lower() in d.lower()]
        
        selected_drug = st.selectbox("Препарат", drugs)
    
    with col2:
        st.subheader("👤 Параметры пациента")
        age = st.number_input("Возраст (лет)", min_value=0.0, max_value=120.0, value=30.0, step=1.0)
        weight = st.number_input("Вес (кг)", min_value=0.5, max_value=300.0, value=70.0, step=1.0)
        height = st.number_input("Рост (см) - для BSA", min_value=50.0, max_value=250.0, value=170.0, step=1.0)
        
        if height > 0 and weight > 0:
            bsa = calculate_bsa(weight, height)
            st.info(f"📐 Площадь поверхности тела (BSA): **{bsa} м²**")
        
        use_egfr = st.checkbox("🔬 Учитывать СКФ")
        egfr = None
        if use_egfr:
            egfr = st.number_input("СКФ (мл/мин)", min_value=0.0, max_value=200.0, value=90.0, step=5.0)
    
    st.markdown("---")
    
    # Переменные для хранения результата
    dose_result = None
    dose_error = None
    
    # Кнопка расчета дозы
    if st.button("💊 РАССЧИТАТЬ ДОЗУ", type="primary", use_container_width=True):
        row, error = find_matching_row(df, selected_drug, age, weight, egfr)
        
        if error:
            dose_error = error
        else:
            dose_result = calculate_dose(row, weight)
    
    # Отображаем результат расчета
    if dose_error:
        st.error(f"❌ {dose_error}")
    elif dose_result and 'error' not in dose_result:
        st.success("✅ Доза рассчитана успешно!")
        
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Тип расчета", dose_result['type'])
        col_b.metric("Разовая доза", dose_result['single'])
        col_c.metric("Суточная доза", dose_result['daily'])
        
        st.info(f"🧮 {dose_result['calc']}")
        
        if dose_result.get('freq'):
            st.write(f"📅 Кратность приема: {dose_result['freq']}")
        
        if dose_result.get('warning'):
            st.warning(dose_result['warning'])
        
        # Сохраняем в session_state для показаний
        st.session_state['last_drug'] = selected_drug
        st.session_state['last_dose'] = dose_result['single']
    elif dose_result and 'error' in dose_result:
        st.error(dose_result['error'])
    
    st.markdown("---")
    
    # Кнопка для показаний
    show_indications = st.button("📚 ПОКАЗАТЬ ПОКАЗАНИЯ", use_container_width=True)
    
    # Отображаем показания если нажата кнопка
    if show_indications:
        if 'last_drug' in st.session_state:
            drug_name = st.session_state['last_drug']
            if indications_df is not None:
                info = get_drug_info_local(drug_name, indications_df)
                if info:
                    st.markdown("### 📋 Показания")
                    st.info(info)
                    st.caption("*Источник: локальная база данных*")
                else:
                    st.warning(f"⚠️ Показания для препарата '{drug_name}' не найдены в листе 'Показания'")
            else:
                st.warning("⚠️ Лист 'Показания' не найден в Excel файле")
        else:
            st.warning("⚠️ Сначала рассчитайте дозу препарата!")
    
    # Боковая панель
    with st.sidebar:
        st.markdown("### 🏥 MediDose Pro")
        st.markdown("---")
        st.markdown("#### ✅ Функции")
        st.markdown("""
        - 🔍 Поиск препаратов
        - 📐 Расчет BSA
        - 🩸 Учет СКФ
        - 📚 Показания из Excel
        """)
        st.markdown("---")
        st.markdown("#### 📝 Как добавить показания")
        st.markdown("""
        1. Откройте Excel файл
        2. Создайте лист **Показания**
        3. Колонки: **drug_name**, **indications**
        4. Заполните для препаратов
        """)
        st.markdown("---")
        total_drugs = sum(len(df) for df in data.values())
        st.metric("Всего препаратов", total_drugs)
        st.metric("Групп", len(sheets))
        st.markdown("---")

if __name__ == "__main__":
    main()