import streamlit as st
import pandas as pd
import plotly.express as px

# --- Configuration ---
st.set_page_config(page_title="Fee Analysis Dashboard", layout="wide")

@st.cache_data
def load_data(file_path):
    df = pd.read_csv(file_path, low_memory=False)
    
    # Fill NA in key categorical columns
    cat_cols = ['Payment Method', 'Card Type', 'Region', 'Processing Channel Name', 'Card Category', 'Action Type']
    for col in cat_cols:
        if col in df.columns:
            df[col] = df[col].fillna('Unknown')
            
    # --- Reverse Calculate GMV ---
    # We initialize Amount as 0 for all rows to prevent double counting
    df['Amount'] = 0.0
    
    # Converting negative costs to absolute numbers for cleaner reporting
    df['Absolute Fee Cost'] = df['Total Amount in Holding Currency'].abs()
    
    # Calculate Amount ONLY on rows where Breakdown Type is 'Premium Variable Fee'
    mask = df['Breakdown Type'] == 'Premium Variable Fee'
    # Premium Variable Fee = GMV * 0.0001 -> GMV = Fee / 0.0001
    df.loc[mask, 'Amount'] = df.loc[mask, 'Absolute Fee Cost'] / 0.0001
    
    return df

# Load the data
try:
    df = load_data('Fee.csv')
except FileNotFoundError:
    st.error("File 'Fee.csv' not found. Please ensure it is in the same folder as this script.")
    st.stop()

# --- Sidebar Filters ---
st.sidebar.header("Data Filters")

# Multiselects for various dimensions
selected_schemes = st.sidebar.multiselect("Card Scheme (Payment Method)", options=df['Payment Method'].unique(), default=df['Payment Method'].unique())
selected_card_types = st.sidebar.multiselect("Card Type", options=df['Card Type'].unique(), default=df['Card Type'].unique())
selected_regions = st.sidebar.multiselect("Regionality", options=df['Region'].unique(), default=df['Region'].unique())
selected_channels = st.sidebar.multiselect("Vertical (Channel)", options=df['Processing Channel Name'].unique(), default=df['Processing Channel Name'].unique())

# --- Apply Filters ---
filtered_df = df[
    (df['Payment Method'].isin(selected_schemes)) &
    (df['Card Type'].isin(selected_card_types)) &
    (df['Region'].isin(selected_regions)) &
    (df['Processing Channel Name'].isin(selected_channels))
]

# --- KPIs ---
st.title("💸 Payment Fee Analysis & GMV Dashboard")
st.markdown("Analyzing provider fees based on reverse-calculated Transaction Amounts.")

# Calculate totals
total_gmv = filtered_df['Amount'].sum()
total_fees = filtered_df['Absolute Fee Cost'].sum()
blended_fee_pct = (total_fees / total_gmv * 100) if total_gmv > 0 else 0

# Layout KPIs
col1, col2, col3 = st.columns(3)
col1.metric("Total Calculated GMV (HKD)", f"{total_gmv:,.2f}")
col2.metric("Total Fees (HKD)", f"{total_fees:,.2f}")
col3.metric("Blended Fee %", f"{blended_fee_pct:.4f} %")

st.markdown("---")

# --- Tables ---
st.subheader("Fees Breakdown vs Total GMV")

# Create Summary Table grouped by Breakdown Type
summary_table = filtered_df.groupby('Breakdown Type').agg(
    Fee_Cost=('Absolute Fee Cost', 'sum'),
).reset_index()

# Calculate % of the TOTAL Filtered GMV for each fee type
if total_gmv > 0:
    summary_table['% of Total GMV'] = (summary_table['Fee_Cost'] / total_gmv) * 100
    summary_table['% of Total Fees'] = (summary_table['Fee_Cost'] / total_fees) * 100
else:
    summary_table['% of Total GMV'] = 0.0
    summary_table['% of Total Fees'] = 0.0

# Sort by Fee Cost descending
summary_table = summary_table.sort_values(by='Fee_Cost', ascending=False)

# Format columns for display
display_table = summary_table.copy()
display_table['Fee_Cost'] = display_table['Fee_Cost'].map("{:,.2f}".format)
display_table['% of Total GMV'] = display_table['% of Total GMV'].map("{:.4f}%".format)
display_table['% of Total Fees'] = display_table['% of Total Fees'].map("{:.2f}%".format)

st.dataframe(display_table, use_container_width=True)

# Detailed drill-down table
with st.expander("View Detailed Breakdown by Fee Detail"):
    detail_table = filtered_df.groupby(['Breakdown Type', 'Fee Detail'], dropna=False).agg(
        Fee_Cost=('Absolute Fee Cost', 'sum')
    ).reset_index()
    
    # Replace NaN Fee Detail with 'N/A' for cleaner display
    detail_table['Fee Detail'] = detail_table['Fee Detail'].fillna('N/A')
    
    if total_gmv > 0:
        detail_table['% of Total GMV'] = (detail_table['Fee_Cost'] / total_gmv) * 100
    else:
        detail_table['% of Total GMV'] = 0.0
        
    detail_table = detail_table.sort_values(by='Fee_Cost', ascending=False)
    detail_table['Fee_Cost'] = detail_table['Fee_Cost'].map("{:,.2f}".format)
    detail_table['% of Total GMV'] = detail_table['% of Total GMV'].map("{:.4f}%".format)
    st.dataframe(detail_table, use_container_width=True)

# --- Charts ---
st.subheader("Visual Insights")
c1, c2 = st.columns(2)

with c1:
    fig_pie = px.pie(summary_table, values='Fee_Cost', names='Breakdown Type', title="Fee Distribution by Type", hole=0.4)
    st.plotly_chart(fig_pie, use_container_width=True)

with c2:
    fig_bar = px.bar(summary_table, x='Breakdown Type', y='Fee_Cost', title="Total Fees by Breakdown Type", text_auto='.2s')
    st.plotly_chart(fig_bar, use_container_width=True)
