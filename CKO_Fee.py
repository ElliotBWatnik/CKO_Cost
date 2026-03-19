import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- Configuration ---
st.set_page_config(page_title="Fee Analysis Dashboard", layout="wide")

@st.cache_data
def load_data():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, 'Fee.csv')
    
    if not os.path.exists(file_path):
        st.error(f"Cannot find the file at: {file_path}")
        st.stop()
        
    df = pd.read_csv(file_path, low_memory=False)
    
    excluded_methods = ['AMEX', 'UNIONPAYINTERNATIONAL']
    df = df[~df['Payment Method'].isin(excluded_methods)]
    
    cat_cols = ['Payment Method', 'Card Type', 'Region', 'Processing Channel Name', 'Card Category', 'Action Type']
    for col in cat_cols:
        if col in df.columns:
            df[col] = df[col].fillna('Unknown')
            
    df['Amount'] = 0.0
    df['Absolute Fee Cost'] = df['Total Amount in Holding Currency'].abs()
    mask = df['Breakdown Type'] == 'Premium Variable Fee'
    df.loc[mask, 'Amount'] = df.loc[mask, 'Absolute Fee Cost'] / 0.0001
    
    return df

df = load_data()

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
    filtered_df = filtered_df[filtered_df['Region'] == selected_region]
if selected_channel != "All":
    filtered_df = filtered_df[filtered_df['Processing Channel Name'] == selected_channel]

filtered_df['Fee Category'] = filtered_df['Breakdown Type'].apply(lambda x: str(x).split(' ')[0])

st.title("💸 Payment Fee Analysis & GMV Dashboard")
st.markdown("Analyzing provider fees based on reverse-calculated Transaction Amounts.")

total_gmv = filtered_df['Amount'].sum()
total_fees = filtered_df['Absolute Fee Cost'].sum()
blended_fee_pct = (total_fees / total_gmv * 100) if total_gmv > 0 else 0

col1, col2, col3 = st.columns(3)
col1.metric("Total Calculated Global GMV (HKD)", f"{total_gmv:,.2f}")
col2.metric("Total Fees (HKD)", f"{total_fees:,.2f}")
col3.metric("Blended Fee %", f"{blended_fee_pct:.4f} %")

st.markdown("---")

st.subheader("📊 Visa & Mastercard Summary")

visa_df = filtered_df[filtered_df['Payment Method'].str.upper() == 'VISA']
mc_df = filtered_df[filtered_df['Payment Method'].str.upper() == 'MASTERCARD']

# GMV Calculations
visa_gmv = visa_df['Amount'].sum()
mc_gmv = mc_df['Amount'].sum()

# Fee Calculations
visa_fees = visa_df['Absolute Fee Cost'].sum()
mc_fees = mc_df['Absolute Fee Cost'].sum()

# Percentage Calculations
visa_share = (visa_gmv / total_gmv * 100) if total_gmv > 0 else 0
mc_share = (mc_gmv / total_gmv * 100) if total_gmv > 0 else 0

visa_cost_pct = (visa_fees / visa_gmv * 100) if visa_gmv > 0 else 0
mc_cost_pct = (mc_fees / mc_gmv * 100) if mc_gmv > 0 else 0

# Display Metrics neatly grouped together
hc1, hc2 = st.columns(2)
with hc1:
    st.metric("VISA Overall GMV", f"{visa_gmv:,.2f}", f"{visa_share:.2f}% Share of Total GMV", delta_color="off")
    st.metric("VISA Overall Cost %", f"{visa_cost_pct:.4f}%")

with hc2:
    st.metric("MASTERCARD Overall GMV", f"{mc_gmv:,.2f}", f"{mc_share:.2f}% Share of Total GMV", delta_color="off")
    st.metric("MASTERCARD Overall Cost %", f"{mc_cost_pct:.4f}%")

st.markdown("---")

# ==========================================
# --- Vertical Scheme Pivot Table        ---
# ==========================================
st.markdown("**Cost % by Vertical, Scheme, and Card Type**")

vmc_df = pd.concat([visa_df, mc_df])
vmc_df['Payment Method'] = vmc_df['Payment Method'].str.upper()

pivot_base = vmc_df[vmc_df['Card Type'].isin(['Credit', 'Debit'])].copy()

if not pivot_base.empty:
    pivot_base = pivot_base.groupby(['Processing Channel Name', 'Payment Method', 'Card Type']).agg(
        GMV=('Amount', 'sum'),
        Fees=('Absolute Fee Cost', 'sum')
    ).reset_index()

    pivot_base['Cost %'] = (pivot_base['Fees'] / pivot_base['GMV'].replace(0, 1)) * 100

    pivot_table = pivot_base.pivot_table(
        index='Processing Channel Name', 
        columns=['Payment Method', 'Card Type'], 
        values='Cost %',
        aggfunc='sum'
    )

    for col in pivot_table.columns:
        pivot_table[col] = pivot_table[col].map(lambda x: f"{x:.4f}%" if pd.notna(x) else "N/A")
    
    st.dataframe(pivot_table, use_container_width=True)
else:
    st.info("No Credit or Debit data available for Visa or Mastercard under current filters.")

st.markdown("---")
st.markdown("Breakdown of core fees over the specific GMV generated by that subset.")

def build_granular_summary_df(df_subset, scheme_name):
    if df_subset.empty:
        return pd.DataFrame()
        
    group_cols = ['Region', 'Card Type']
    
    res_df = df_subset.groupby(group_cols)['Amount'].sum().reset_index()
    res_df.rename(columns={'Amount': 'Subset GMV'}, inplace=True)
        
    tot_fees = df_subset.groupby(group_cols)['Absolute Fee Cost'].sum().reset_index()
    res_df = pd.merge(res_df, tot_fees, on=group_cols, how='left')
    res_df.rename(columns={'Absolute Fee Cost': 'Total Fee Cost'}, inplace=True)

    cat_fees = df_subset.groupby(group_cols + ['Fee Category'])['Absolute Fee Cost'].sum().reset_index()
    
    pivot = cat_fees.pivot(index=group_cols, columns='Fee Category', values='Absolute Fee Cost').fillna(0).reset_index()
        
    res_df = pd.merge(res_df, pivot, on=group_cols, how='left').fillna(0)
    
    final_df = pd.DataFrame()
    final_df['Scheme'] = [scheme_name] * len(res_df)
    final_df['Region'] = res_df['Region']
    final_df['Card Type'] = res_df['Card Type']
    
    final_df['GMV (HKD)'] = res_df['Subset GMV'].map("{:,.2f}".format)
    
    if total_gmv > 0:
        final_df['Share of Total GMV'] = (res_df['Subset GMV'] / total_gmv * 100).map("{:.2f}%".format)
    else:
        final_df['Share of Total GMV'] = "0.00%"
    
    safe_gmv = res_df['Subset GMV'].replace(0, 1)
    
    final_df['Total Cost %'] = (res_df['Total Fee Cost'] / safe_gmv * 100).map("{:.4f}%".format)
    
    for col in ['Interchange', 'Scheme', 'Gateway', 'Premium']:
        if col in res_df.columns:
            final_df[f"{col} %"] = (res_df[col] / safe_gmv * 100).map("{:.4f}%".format)
        else:
            final_df[f"{col} %"] = "0.0000%"
            
    if total_gmv > 0:
        final_df['Weighted Cost %'] = (res_df['Total Fee Cost'] / total_gmv * 100).map("{:.4f}%".format)
    else:
        final_df['Weighted Cost %'] = "0.0000%"
            
    return final_df

summary_dfs = []
for scheme_name, sdf in [('VISA', visa_df), ('MASTERCARD', mc_df)]:
    if not sdf.empty:
        summary_dfs.append(build_granular_summary_df(sdf, scheme_name))

if summary_dfs:
    combined_summary = pd.concat(summary_dfs, ignore_index=True)
    st.dataframe(combined_summary, use_container_width=True)
else:
    st.info("No Visa or Mastercard data available with the current filters.")

st.markdown("---")

st.subheader("Fees Breakdown vs Total GMV")

summary_table = filtered_df.groupby('Breakdown Type').agg(
    Fee_Cost=('Absolute Fee Cost', 'sum'),
).reset_index()

if total_gmv > 0:
    summary_table['% of Total GMV'] = (summary_table['Fee_Cost'] / total_gmv) * 100
    summary_table['% of Total Fees'] = (summary_table['Fee_Cost'] / total_fees) * 100
else:
    summary_table['% of Total GMV'] = 0.0
    summary_table['% of Total Fees'] = 0.0

summary_table = summary_table.sort_values(by='Fee_Cost', ascending=False)

display_table = summary_table.copy()
display_table['Fee_Cost'] = display_table['Fee_Cost'].map("{:,.2f}".format)
display_table['% of Total GMV'] = display_table['% of Total GMV'].map("{:.4f}%".format)
display_table['% of Total Fees'] = display_table['% of Total Fees'].map("{:.2f}%".format)

st.dataframe(display_table, use_container_width=True)

with st.expander("View Detailed Breakdown by Fee Detail"):
    detail_table = filtered_df.groupby(['Breakdown Type', 'Fee Detail'], dropna=False).agg(
        Fee_Cost=('Absolute Fee Cost', 'sum')
    ).reset_index()
    
    detail_table['Fee Detail'] = detail_table['Fee Detail'].fillna('N/A')
    
    if total_gmv > 0:
        detail_table['% of Total GMV'] = (detail_table['Fee_Cost'] / total_gmv) * 100
    else:
        detail_table['% of Total GMV'] = 0.0
        
    detail_table = detail_table.sort_values(by='Fee_Cost', ascending=False)
    detail_table['Fee_Cost'] = detail_table['Fee_Cost'].map("{:,.2f}".format)
    detail_table['% of Total GMV'] = detail_table['% of Total GMV'].map("{:.4f}%".format)
    st.dataframe(detail_table, use_container_width=True)

st.subheader("Visual Insights")
c1, c2 = st.columns(2)

with c1:
    fig_pie = px.pie(summary_table, values='Fee_Cost', names='Breakdown Type', title="Fee Distribution by Type", hole=0.4)
    st.plotly_chart(fig_pie, use_container_width=True)

with c2:
    fig_bar = px.bar(summary_table, x='Breakdown Type', y='Fee_Cost', title="Total Fees by Breakdown Type", text_auto='.2s')
    st.plotly_chart(fig_bar, use_container_width=True)
