import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(
    page_title="MediDose Pro",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Мобильная адаптация
st.markdown("""
<style>
    .main > div {
        padding: 1rem 0.5rem;
    }
    .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 0.75rem;
        font-size: 1rem;
        font-weight: 600;
    }
    .stSelectbox > div > div {
        border-radius: 12px;
    }
    .stNumberInput > div > div > input {
        border-radius: 12px;
    }
    .stAlert {
        border-radius: 12px;
    }
    h1 {
        text-align: center;
        font-size: 1.8rem !important;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
        color: white;
    }
    .indications-box {
        background: #f0f2f6;
        border-radius: 12px;
        padding: 1rem;
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Расчет BSA
def calculate_bsa(weight, height):
    if weight > 0 and height > 0:
        return round(np.sqrt((weight * height) / 3600), 2)
    return None

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
def find_dose(row, age, weight, egfr):
    if row is None:
        return None
    
    # Проверка возраста
    if pd.notna(row.get('age_min')) and age < row['age_min']:
        return None
    if pd.notna(row.get('age_max')) and age > row['age_max']:
        return None
    
    # Проверка веса
    if pd.notna(row.get('weight_min')) and weight < row['weight_min']:
        return None
    if pd.notna(row.get('weight_max')) and weight > row['weight_max']:
        return None
    
    # Проверка СКФ
    if egfr is not None:
        if pd.notna(row.get('egfr_min')) and egfr < row['egfr_min']:
            return None
        if pd.notna(row.get('egfr_max')) and egfr > row['egfr_max']:
            return None
    
    return row

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
            warning = f"⚠️ Макс. суточная: {max_daily} {dose_unit}"
        return {
            'dose': f"{calculated:.0f} {dose_unit}",
            'freq': frequency,
            'warning': warning
        }
    elif pd.notna(dose_fixed):
        return {
            'dose': f"{dose_fixed} {dose_unit}",
            'freq': frequency,
            'warning': ""
        }
    return None

def main():
    # Загрузка данных
    data, sheets, indications_df = load_data()
    if data is None:
        st.error("❌ Файл drug_database_full.xlsx не найден")
        st.info("Убедитесь, что файл загружен в репозиторий")
        return
    
    st.title("💊 MediDose Pro")
    st.caption("Калькулятор доз лекарственных препаратов")
    st.divider()
    
    # Инициализация состояния
    if 'calculated' not in st.session_state:
        st.session_state.calculated = False
    if 'dose_result' not in st.session_state:
        st.session_state.dose_result = None
    if 'selected_drug' not in st.session_state:
        st.session_state.selected_drug = None
    if 'drug_info' not in st.session_state:
        st.session_state.drug_info = None
    if 'show_info' not in st.session_state:
        st.session_state.show_info = False
    
    # Выбор группы
    group = st.selectbox("Группа препаратов", sheets)
    df = data[group]
    
    # Поиск
    search = st.text_input("🔍 Поиск", placeholder="Введите название...")
    drugs = sorted(df['generic_name'].unique())
    if search:
        drugs = [d for d in drugs if search.lower() in d.lower()]
    
    drug = st.selectbox("Препарат", drugs, key="drug_select")
    
    # Параметры
    st.subheader("Параметры пациента")
    
    col1, col2 = st.columns(2)
    with col1:
        age = st.number_input("Возраст (лет)", min_value=0.0, max_value=120.0, value=30.0)
        weight = st.number_input("Вес (кг)", min_value=0.5, max_value=300.0, value=70.0)
    with col2:
        height = st.number_input("Рост (см)", min_value=50.0, max_value=250.0, value=170.0)
        if height > 0 and weight > 0:
            bsa = calculate_bsa(weight, height)
            st.caption(f"BSA: {bsa} м²")
    
    use_egfr = st.checkbox("Учитывать СКФ")
    egfr = None
    if use_egfr:
        egfr = st.number_input("СКФ (мл/мин)", min_value=0.0, max_value=200.0, value=90.0)
    
    st.divider()
    
    # Кнопка расчета
    if st.button("💊 РАССЧИТАТЬ ДОЗУ", type="primary"):
        # Ищем подходящую строку
        drug_df = df[df['generic_name'].str.contains(drug, case=False, na=False)]
        matching_row = None
        
        for _, row in drug_df.iterrows():
            matched = find_dose(row, age, weight, egfr)
            if matched is not None:
                matching_row = matched
                break
        
        if matching_row is None:
            st.error("❌ Нет подходящей дозировки для указанных параметров")
            st.session_state.calculated = False
            st.session_state.dose_result = None
        else:
            result = calculate_dose(matching_row, weight)
            if result:
                st.session_state.dose_result = result
                st.session_state.calculated = True
                st.session_state.selected_drug = drug
                st.session_state.show_info = False
            else:
                st.error("❌ Ошибка расчета дозы")
    
    # Отображение результата
    if st.session_state.calculated and st.session_state.dose_result:
        st.success("✅ Доза рассчитана")
        
        res = st.session_state.dose_result
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"""
            <div class="metric-card">
                <div style="font-size: 0.8rem;">РАЗОВАЯ ДОЗА</div>
                <div style="font-size: 1.8rem; font-weight: bold;">{res['dose']}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_b:
            freq_text = res['freq'] if res['freq'] else "по назначению"
            st.markdown(f"""
            <div class="metric-card">
                <div style="font-size: 0.8rem;">КРАТНОСТЬ</div>
                <div style="font-size: 1.2rem; font-weight: bold;">{freq_text}</div>
            </div>
            """, unsafe_allow_html=True)
        
        if res['warning']:
            st.warning(res['warning'])
        
        st.divider()
    
    # Кнопка показаний
    if st.session_state.calculated and st.session_state.selected_drug:
        if st.button("📚 ПОКАЗАТЬ ПОКАЗАНИЯ"):
            if indications_df is not None:
                matching = indications_df[indications_df['drug_name'].str.contains(
                    st.session_state.selected_drug, case=False, na=False
                )]
                if not matching.empty:
                    st.session_state.drug_info = matching.iloc[0]['indications']
                else:
                    st.session_state.drug_info = None
                st.session_state.show_info = True
            else:
                st.warning("Лист 'Показания' не найден")
        
        # Отображение показаний
        if st.session_state.show_info:
            if st.session_state.drug_info:
                st.markdown("### 📋 Показания")
                st.info(st.session_state.drug_info)
                st.caption("*Источник: локальная база данных*")
            else:
                st.warning(f"Показания для '{st.session_state.selected_drug}' не найдены")

if __name__ == "__main__":
    main()
