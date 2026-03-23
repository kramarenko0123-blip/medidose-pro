import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(
    page_title="MediDose Pro",
    page_icon="💊",
    layout="centered"
)

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

# Поиск подходящей дозировки
def find_dose_row(df, drug_name, age, weight, egfr):
    drug_df = df[df['generic_name'].str.contains(drug_name, case=False, na=False)]
    
    for _, row in drug_df.iterrows():
        # Проверка возраста
        if pd.notna(row.get('age_min')) and age < row['age_min']:
            continue
        if pd.notna(row.get('age_max')) and age > row['age_max']:
            continue
        
        # Проверка веса
        if pd.notna(row.get('weight_min')) and weight < row['weight_min']:
            continue
        if pd.notna(row.get('weight_max')) and weight > row['weight_max']:
            continue
        
        # Проверка СКФ
        if egfr is not None:
            if pd.notna(row.get('egfr_min')) and egfr < row['egfr_min']:
                continue
            if pd.notna(row.get('egfr_max')) and egfr > row['egfr_max']:
                continue
        
        return row
    
    return None

# Расчет дозы
def calculate_dose(row, weight):
    dose_per_kg = row.get('dose_mg_per_kg')
    dose_fixed = row.get('dose_mg_fixed')
    dose_unit = row.get('dose_unit', 'мг')
    frequency = row.get('frequency', '')
    max_daily = row.get('max_daily_mg')
    
    if pd.notna(dose_per_kg):
        calculated = dose_per_kg * weight
        if pd.notna(max_daily) and calculated > max_daily:
            calculated = max_daily
            return f"{calculated:.0f} {dose_unit}", frequency, True
        return f"{calculated:.0f} {dose_unit}", frequency, False
    elif pd.notna(dose_fixed):
        return f"{dose_fixed} {dose_unit}", frequency, False
    return None, None, False

def main():
    st.title("💊 MediDose Pro")
    st.markdown("---")
    
    # Загрузка данных
    data, sheets, indications_df = load_data()
    if data is None:
        st.error("❌ Ошибка загрузки данных")
        return
    
    # Выбор группы
    group = st.selectbox("Группа", sheets)
    df = data[group]
    
    # Поиск
    drugs = sorted(df['generic_name'].unique())
    drug = st.selectbox("Препарат", drugs)
    
    # Параметры
    col1, col2 = st.columns(2)
    with col1:
        age = st.number_input("Возраст (лет)", min_value=0.0, value=30.0, step=1.0)
        weight = st.number_input("Вес (кг)", min_value=0.5, value=70.0, step=1.0)
    with col2:
        height = st.number_input("Рост (см)", min_value=50.0, value=170.0, step=1.0)
        if height > 0 and weight > 0:
            bsa = round(np.sqrt((weight * height) / 3600), 2)
            st.caption(f"BSA: {bsa} м²")
    
    use_egfr = st.checkbox("Учитывать СКФ")
    egfr = None
    if use_egfr:
        egfr = st.number_input("СКФ (мл/мин)", min_value=0.0, value=90.0, step=5.0)
    
    st.markdown("---")
    
    # Расчет
    if st.button("💊 Рассчитать дозу", type="primary"):
        row = find_dose_row(df, drug, age, weight, egfr)
        
        if row is None:
            st.error("❌ Не найдено подходящей дозировки")
        else:
            dose, freq, limited = calculate_dose(row, weight)
            
            if dose:
                st.success("✅ Результат расчета")
                st.markdown(f"### 💊 {drug}")
                st.markdown(f"**Разовая доза:** {dose}")
                if freq:
                    st.markdown(f"**Кратность:** {freq}")
                if limited:
                    st.warning("⚠️ Доза ограничена максимальной суточной")
                if pd.notna(row.get('special')):
                    st.info(f"ℹ️ {row['special']}")
                
                # Сохраняем для показаний
                st.session_state['last_drug'] = drug
            else:
                st.error("❌ Ошибка расчета")
    
    st.markdown("---")
    
    # Показания
    if 'last_drug' in st.session_state:
        if st.button("📚 Показания"):
            if indications_df is not None:
                match = indications_df[indications_df['drug_name'].str.contains(
                    st.session_state['last_drug'], case=False, na=False
                )]
                if not match.empty:
                    st.markdown("### 📋 Показания")
                    st.info(match.iloc[0]['indications'])
                else:
                    st.warning("Показания не найдены")
            else:
                st.warning("Лист 'Показания' отсутствует")

if __name__ == "__main__":
    main()
