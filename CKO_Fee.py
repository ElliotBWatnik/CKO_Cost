import streamlit as st
import pandas as pd
import plotly.express as px

# --- Configuration ---
st.set_page_config(page_title="Fee Analysis Dashboard", layout="wide")

st.title("💸 Payment Fee Analysis & GMV Dashboard")
st.markdown("Upload your Checkout.com Fee Summary Report to analyze provider fees based on reverse-calculated Transaction Amounts.")

# --- File Uploader ---
st.sidebar.header("Data Upload")
uploaded_file = st.sidebar.file_uploader("Upload Fee Report (CSV)", type=["csv"])

if not uploaded_file:
    st.info("👈 Please upload your Fee Summary Report CSV in the sidebar to generate the dashboard.")
    st.stop()

@st.cache_data
def load_data(file):
    df = pd.read_csv(file, low_memory=False)
    
    excluded_methods = ['AMEX', 'UNIONPAYINTERNATIONAL']
    if 'Payment Method' in df.columns:
        df = df[~df['Payment Method'].isin(excluded_methods)]
    
    cat_cols = ['Payment Method', 'Card Type', 'Region', 'Processing Channel Name', 'Card Category', 'Action Type']
    for col in cat_cols:
        if col in df.columns:
            df[col] = df[col].fillna('Unknown')
            
    df['Amount'] = 0.0
    if 'Total Amount in Holding Currency' in df.columns:
        df['Absolute Fee Cost'] = df['Total Amount in Holding Currency'].abs()
    else:
        st.error("Missing required column: 'Total Amount in Holding Currency'")
        st.stop()
        
    if 'Breakdown Type' in df.columns:
        mask = df['Breakdown Type'] == 'Premium Variable Fee'
        df.loc[mask, 'Amount'] = df.loc[mask, 'Absolute Fee Cost'] / 0.0001
    
    return df

df = load_data(uploaded_file)

# --- Sidebar Filters ---
st.sidebar.header("Data Filters")

def get_dropdown_options(series):
    return ["All"] + sorted(series.unique().tolist())

selected_scheme = st.sidebar.selectbox("Card Scheme (Payment Method)", options=get_dropdown_options(df['Payment Method']))
selected_card_type = st.sidebar.selectbox("Card Type", options=get_dropdown_options(df['Card Type']))
selected_region = st.sidebar.selectbox("Regionality", options=get_dropdown_options(df['Region']))
selected_channel = st.sidebar.selectbox("Vertical (Channel)", options=get_dropdown_options(df['Processing Channel Name']))

filtered_df = df.copy()

if selected_scheme != "All":
    filtered_df = filtered_df[filtered_df['Payment Method'] == selected_scheme]
if selected_card_type != "All":
    filtered_df = filtered_df[filtered_df['Card Type'] == selected_card_type]
if selected_region != "All":
    filtered_df = filtered_df
