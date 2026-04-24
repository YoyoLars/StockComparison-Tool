import wrds
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from io import BytesIO

# Page layout
st.set_page_config(
    page_title="Multi-Stock Price Trends Comparison",
    page_icon="📈",
    layout="wide"
)

st.title("📊 Multi-Stock Price Trends Comparison")
st.write("This app compares stock price data from CRSP via WRDS")

# About section
with st.expander("ℹ️ About This App"):
    st.markdown("""
    - **Purpose:** Compare stock performance from CRSP database
    - **Data Source:** WRDS (Wharton Research Data Services)
    - **Developer:** Student Project
    
    **How to use:**
    1. Enter your WRDS credentials
    2. Select stocks to compare
    3. Choose analysis options
    4. Click 'Run Analysis'
    """)

# Sidebar login
st.sidebar.header("🔐 WRDS Login")
username = st.sidebar.text_input("WRDS Username")
password = st.sidebar.text_input("WRDS Password", type="password")

# Stock selection
st.sidebar.header("📈 Stock Selection")
selected_hticks = st.sidebar.multiselect(
    "Select stocks to compare",
    options=["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "JPM"],
    default=["AAPL", "GOOGL"]
)

# Custom input
custom_hticks = st.sidebar.text_input(
    "Or enter custom hticks (comma-separated, e.g., 'NVDA, JPM, TSLA')",
    placeholder="NVDA, JPM, TSLA",
    help="Enter stock symbols separated by commas"
)

# Parse custom input
if custom_hticks:
    custom_list = [t.strip().upper() for t in custom_hticks.split(',')]
    selected_hticks = list(set(selected_hticks + custom_list))
    selected_hticks.sort()

st.sidebar.info(f"Selected stocks: {', '.join(selected_hticks)}")

# Date range
st.sidebar.header("📅 Date Range")
start_date = st.sidebar.date_input("Start Date", pd.to_datetime("2023-03-04"))
end_date = st.sidebar.date_input("End Date", pd.to_datetime("2025-04-21"))

# Display options
st.sidebar.header("📊 Display Options")
show_cumulative = st.sidebar.checkbox("📈 Cumulative Return Chart", value=True)
show_volatility = st.sidebar.checkbox("📊 Volatility Comparison", value=True)
show_distribution = st.sidebar.checkbox("📉 Return Distribution", value=False)
show_correlation = st.sidebar.checkbox("🔗 Correlation Matrix", value=False)
show_sharpe = st.sidebar.checkbox("⚖️ Sharpe Ratio", value=True)
show_monthly = st.sidebar.checkbox("📅 Monthly Heatmap", value=False)
show_raw_price = st.sidebar.checkbox("💰 Price Trends", value=True)
show_raw_data = st.sidebar.checkbox("📋 Raw Data", value=False)

# Run button
run_button = st.sidebar.button("🚀 Run Analysis")

if run_button:
    if not username or not password:
        st.error("❌ Please enter your WRDS username and password!")
    elif len(selected_hticks) == 0:
        st.error("❌ Please select at least one stock!")
    else:
        try:
            # Loading progress
            with st.spinner("📡 Connecting to WRDS..."):
                db = wrds.Connection(wrds_username=username)

            with st.spinner("📥 Fetching stock data..."):
                htick_list = "', '".join(selected_hticks)
                sql_query = f"""
                SELECT a.date, b.htick, a.prc, a.ret
                FROM crsp.msf AS a
                LEFT JOIN crsp.msfhdr AS b ON a.permno = b.permno
                WHERE b.htick IN ('{htick_list}')
                AND a.date >= '{start_date}'
                AND a.date <= '{end_date}'
                ORDER BY b.htick, a.date
                """

                df = db.raw_sql(sql_query, date_cols=["date"])
                db.close()

            if len(df) == 0:
                st.error("❌ No data found. Please check your htick symbols and date range.")
            else:
                with st.spinner("📊 Processing data..."):
                    # Validate tickers
                    valid_hticks = df['htick'].unique().tolist()
                    invalid_hticks = [h for h in selected_hticks if h not in valid_hticks]

                    if len(invalid_hticks) > 0:
                        st.warning(f"⚠️ These stocks were not found: {', '.join(invalid_hticks)}")

                    if len(valid_hticks) == 0:
                        st.error("❌ No valid stocks found!")
                    else:
                        # Data cleaning
                        df['prc'] = df['prc'].abs()
                        df = df.rename(columns={'prc': 'price', 'ret': 'daily_return'})
                        df = df.sort_values(['htick', 'date'])

                        # Calculate daily returns
                        df['daily_return'] = df.groupby('htick')['price'].pct_change()

                        # Calculate statistics
                        stats_list = []
                        for htick in valid_hticks:
                            stock_data = df[df['htick'] == htick]
                            if len(stock_data) > 0:
                                mean_ret = stock_data['daily_return'].mean()
                                std_ret = stock_data['daily_return'].std()
                                min_ret = stock_data['daily_return'].min()
                                max_ret = stock_data['daily_return'].max()
                                first_price = stock_data['price'].iloc[0]
                                last_price = stock_data['price'].iloc[-1]
                                total_ret = (last_price / first_price) - 1

                                stats_list.append({
                                    'htick': htick,
                                    'Mean Daily Return (%)': mean_ret * 100,
                                    'Std Dev (%)': std_ret * 100,
                                    'Min Return (%)': min_ret * 100,
                                    'Max Return (%)': max_ret * 100,
                                    'Total Return (%)': total_ret * 100
                                })

                        stats_df = pd.DataFrame(stats_list)

                        # Cumulative return
                        df['cumulative_return'] = (1 + df['daily_return']).groupby(df['htick']).cumprod()

                        # Sharpe ratio
                        risk_free_rate = 0
                        stats_df['Sharpe Ratio'] = (stats_df['Mean Daily Return (%)'] - risk_free_rate) / stats_df['Std Dev (%)']

                        # Correlation
                        returns_pivot = df.pivot(index='date', columns='htick', values='daily_return').dropna()
                        if len(returns_pivot.columns) > 1:
                            correlation = returns_pivot.corr()

                st.success("✅ Analysis complete!")

                # Data source info
                st.markdown(f"""
                ---
                **Data Source:** CRSP (Center for Research in Security Prices) via WRDS  
                **Data Access Date:** {pd.Timestamp.now().strftime('%Y-%m-%d')}  
                **Date Range:** {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}  
                **Disclaimer:** This tool is for educational purposes only.
                ---
                """)

                # Smart feedback
                best_idx = stats_df['Total Return (%)'].idxmax()
                best_stock = stats_df.loc[best_idx]
                st.success(
                    f"🏆 Best performer: **{best_stock['htick']}** "
                    f"with {best_stock['Total Return (%)']:.2f}% return!"
                )

                worst_idx = stats_df['Total Return (%)'].idxmin()
                worst_stock = stats_df.loc[worst_idx]
                st.warning(
                    f"📉 Worst performer: **{worst_stock['htick']}** "
                    f"with {worst_stock['Total Return (%)']:.2f}% return"
                )

                st.markdown("---")

                # Risk alerts
                st.subheader("⚠️ Risk Alerts")

                high_volatility = stats_df[stats_df['Std Dev (%)'] > 3]
                if len(high_volatility) > 0:
                    st.warning(f"⚠️ High volatility stocks (>3% daily): {', '.join(high_volatility['htick'])}")

                worst_day_stock = stats_df.loc[stats_df['Min Return (%)'].idxmin()]
                if worst_day_stock['Min Return (%)'] < -10:
                    st.error(f"🚨 {worst_day_stock['htick']} had an extreme loss of {worst_day_stock['Min Return (%)']:.2f}% in one day!")
                elif worst_day_stock['Min Return (%)'] < -5:
                    st.warning(f"📉 {worst_day_stock['htick']} had a significant loss of {worst_day_stock['Min Return (%)']:.2f}% in one day")

                if stats_df['Total Return (%)'].max() < 0:
                    st.error("📉 All stocks had negative returns in this period!")
                elif stats_df['Total Return (%)'].min() > 0:
                    st.success("📈 All stocks had positive returns in this period!")

                st.markdown("---")

                # Statistics table
                st.subheader("📋 Statistics Comparison")
                
                formatted_df = stats_df.copy()
                formatted_df['Mean Daily Return (%)'] = formatted_df['Mean Daily Return (%)'].apply(lambda x: f"{x:.4f}")
                formatted_df['Std Dev (%)'] = formatted_df['Std Dev (%)'].apply(lambda x: f"{x:.4f}")
                formatted_df['Min Return (%)'] = formatted_df['Min Return (%)'].apply(lambda x: f"{x:.2f}")
                formatted_df['Max Return (%)'] = formatted_df['Max Return (%)'].apply(lambda x: f"{x:.2f}")
                formatted_df['Total Return (%)'] = formatted_df['Total Return (%)'].apply(lambda x: f"{x:.2f}")
                formatted_df['Sharpe Ratio'] = formatted_df['Sharpe Ratio'].apply(lambda x: f"{x:.4f}")
                
                st.dataframe(formatted_df)

                st.markdown("---")

                # Charts
                if show_cumulative:
                    st.subheader("📈 Cumulative Return Comparison")

                    fig2, ax2 = plt.subplots(figsize=(12, 6))
                    for htick in valid_hticks:
                        stock_data = df[df['htick'] == htick]
                        if len(stock_data) > 0:
                            ax2.plot(stock_data['date'], stock_data['cumulative_return'], label=htick, linewidth=2)

                    ax2.set_xlabel('Date', fontsize=12)
                    ax2.set_ylabel('Cumulative Return', fontsize=12)
                    ax2.set_title('Cumulative Return Over Time', fontsize=14, fontweight='bold')
                    ax2.legend()
                    ax2.grid(True, alpha=0.3)
                    ax2.axhline(y=1, color='black', linestyle='--', alpha=0.5)
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    st.pyplot(fig2)
                    
                    buf2 = BytesIO()
                    fig2.savefig(buf2, format="png", dpi=300, bbox_inches='tight')
                    buf2.seek(0)
                    st.download_button(
                        label="📷 Download Cumulative Return Chart",
                        data=buf2,
                        file_name="cumulative_return_chart.png",
                        mime="image/png"
                    )

                if show_volatility:
                    st.subheader("📊 Volatility Comparison")

                    fig3, ax3 = plt.subplots(figsize=(10, 5))
                    volatility_data = stats_df[['htick', 'Std Dev (%)']].sort_values('Std Dev (%)', ascending=False)
                    colors = ['red' if x > stats_df['Std Dev (%)'].mean() else 'blue' for x in volatility_data['Std Dev (%)']]
                    ax3.bar(volatility_data['htick'], volatility_data['Std Dev (%)'], color=colors)
                    ax3.set_xlabel('Stock', fontsize=12)
                    ax3.set_ylabel('Standard Deviation (%)', fontsize=12)
                    ax3.set_title('Stock Volatility Comparison', fontsize=14, fontweight='bold')
                    ax3.grid(True, alpha=0.3, axis='y')
                    ax3.axhline(y=stats_df['Std Dev (%)'].mean(), color='green', linestyle='--', label='Average')
                    ax3.legend()
                    plt.tight_layout()
                    st.pyplot(fig3)
                    
                    buf3 = BytesIO()
                    fig3.savefig(buf3, format="png", dpi=300, bbox_inches='tight')
                    buf3.seek(0)
                    st.download_button(
                        label="📷 Download Volatility Chart",
                        data=buf3,
                        file_name="volatility_chart.png",
                        mime="image/png"
                    )
                    
                    st.info(f"📍 Average volatility: {stats_df['Std Dev (%)'].mean():.2f}%")

                if show_distribution:
                    st.subheader("📉 Daily Return Distribution")

                    fig4, ax4 = plt.subplots(figsize=(10, 5))
                    for htick in valid_hticks:
                        stock_data = df[df['htick'] == htick]['daily_return'].dropna()
                        ax4.hist(stock_data, bins=30, alpha=0.5, label=htick)

                    ax4.set_xlabel('Daily Return (%)', fontsize=12)
                    ax4.set_ylabel('Frequency', fontsize=12)
                    ax4.set_title('Daily Return Distribution', fontsize=14, fontweight='bold')
                    ax4.legend()
                    ax4.grid(True, alpha=0.3)
                    ax4.axvline(x=0, color='black', linestyle='--', alpha=0.5)
                    plt.tight_layout()
                    st.pyplot(fig4)
                    
                    buf4 = BytesIO()
                    fig4.savefig(buf4, format="png", dpi=300, bbox_inches='tight')
                    buf4.seek(0)
                    st.download_button(
                        label="📷 Download Distribution Chart",
                        data=buf4,
                        file_name="distribution_chart.png",
                        mime="image/png"
                    )

                if show_correlation:
                    st.subheader("🔗 Return Correlation Matrix")

                    if len(returns_pivot.columns) > 1:
                        fig5, ax5 = plt.subplots(figsize=(8, 6))
                        im = ax5.imshow(correlation, cmap='RdYlGn', vmin=-1, vmax=1)
                        ax5.set_xticks(range(len(correlation.columns)))
                        ax5.set_yticks(range(len(correlation.columns)))
                        ax5.set_xticklabels(correlation.columns)
                        ax5.set_yticklabels(correlation.columns)

                        for i in range(len(correlation.columns)):
                            for j in range(len(correlation.columns)):
                                text = ax5.text(j, i, f'{correlation.iloc[i, j]:.2f}', 
                                               ha="center", va="center", color="black")

                        ax5.set_title('Stock Return Correlation', fontsize=14, fontweight='bold')
                        plt.colorbar(im, ax=ax5, label='Correlation')
                        plt.tight_layout()
                        st.pyplot(fig5)
                        
                        buf5 = BytesIO()
                        fig5.savefig(buf5, format="png", dpi=300, bbox_inches='tight')
                        buf5.seek(0)
                        st.download_button(
                            label="📷 Download Correlation Chart",
                            data=buf5,
                            file_name="correlation_chart.png",
                            mime="image/png"
                        )
                        
                        st.write("**📖 Green = positively correlated, Red = negatively correlated**")
                    else:
                        st.info("Not enough data for correlation analysis")

                if show_sharpe:
                    st.subheader("⚖️ Sharpe Ratio Comparison (Risk-Adjusted Return)")

                    fig6, ax6 = plt.subplots(figsize=(10, 5))
                    sharpe_sorted = stats_df[['htick', 'Sharpe Ratio']].sort_values('Sharpe Ratio', ascending=False)
                    colors = ['green' if x > 0 else 'red' for x in sharpe_sorted['Sharpe Ratio']]
                    ax6.bar(sharpe_sorted['htick'], sharpe_sorted['Sharpe Ratio'], color=colors)
                    ax6.set_xlabel('Stock', fontsize=12)
                    ax6.set_ylabel('Sharpe Ratio', fontsize=12)
                    ax6.set_title('Risk-Adjusted Return (Sharpe Ratio)', fontsize=14, fontweight='bold')
                    ax6.grid(True, alpha=0.3, axis='y')
                    ax6.axhline(y=0, color='black', linestyle='--', alpha=0.5)
                    plt.tight_layout()
                    st.pyplot(fig6)
                    
                    buf6 = BytesIO()
                    fig6.savefig(buf6, format="png", dpi=300, bbox_inches='tight')
                    buf6.seek(0)
                    st.download_button(
                        label="📷 Download Sharpe Ratio Chart",
                        data=buf6,
                        file_name="sharpe_ratio_chart.png",
                        mime="image/png"
                    )
                    
                    st.info("📈 Higher Sharpe Ratio = Better risk-adjusted return. Positive = good, Negative = bad")

                if show_monthly:
                    st.subheader("📅 Monthly Return Heatmap")

                    df['year_month'] = df['date'].dt.to_period('M')
                    monthly_returns = df.groupby(['htick', 'year_month'])['daily_return'].sum().unstack(level=0)
                    monthly_returns_pct = monthly_returns.fillna(0).astype(float) * 100

                    fig7, ax7 = plt.subplots(figsize=(14, 6))
                    im2 = ax7.imshow(monthly_returns_pct.T, cmap='RdYlGn', aspect='auto', vmin=-20, vmax=20)
                    ax7.set_yticks(range(len(monthly_returns_pct.columns)))
                    ax7.set_yticklabels(monthly_returns_pct.columns)
                    ax7.set_xticks(range(len(monthly_returns_pct.index)))
                    ax7.set_xticklabels([str(x) for x in monthly_returns_pct.index], rotation=45)
                    ax7.set_xlabel('Month', fontsize=12)
                    ax7.set_ylabel('Stock', fontsize=12)
                    ax7.set_title('Monthly Return Heatmap (%)', fontsize=14, fontweight='bold')
                    plt.colorbar(im2, ax=ax7, label='Monthly Return (%)')
                    plt.tight_layout()
                    st.pyplot(fig7)
                    
                    buf7 = BytesIO()
                    fig7.savefig(buf7, format="png", dpi=300, bbox_inches='tight')
                    buf7.seek(0)
                    st.download_button(
                        label="📷 Download Monthly Heatmap",
                        data=buf7,
                        file_name="monthly_heatmap.png",
                        mime="image/png"
                    )
                    
                    st.write("**🟢 Green = positive return, 🔴 Red = negative return**")

                if show_raw_price:
                    st.subheader("💰 Price Trends")

                    fig, ax = plt.subplots(figsize=(12, 6))
                    for htick in valid_hticks:
                        stock_data = df[df['htick'] == htick]
                        if len(stock_data) > 0:
                            ax.plot(stock_data['date'], stock_data['price'], label=htick, linewidth=2)

                    ax.set_xlabel('Date', fontsize=12)
                    ax.set_ylabel('Price ($)', fontsize=12)
                    ax.set_title('Stock Price Comparison', fontsize=14, fontweight='bold')
                    ax.legend()
                    ax.grid(True, alpha=0.3)
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    st.pyplot(fig)
                    
                    buf = BytesIO()
                    fig.savefig(buf, format="png", dpi=300, bbox_inches='tight')
                    buf.seek(0)
                    st.download_button(
                        label="📷 Download Price Chart",
                        data=buf,
                        file_name="price_chart.png",
                        mime="image/png"
                    )

                if show_raw_data:
                    with st.expander("📋 View Raw Data"):
                        st.dataframe(df)

                # Auto analysis report
                st.markdown("---")
                st.subheader("📝 Analysis Summary")

                analysis_text = ""

                # Overall performance
                total_returns = stats_df['Total Return (%)']
                avg_return = total_returns.mean()
                max_return = total_returns.max()
                min_return = total_returns.min()
                best_stock = stats_df.loc[stats_df['Total Return (%)'].idxmax(), 'htick']
                worst_stock = stats_df.loc[stats_df['Total Return (%)'].idxmin(), 'htick']

                if avg_return > 0:
                    analysis_text += f"**Overall Performance:** Over the analysis period, the selected stocks showed a positive trend with an average total return of {avg_return:.2f}%. "
                else:
                    analysis_text += f"**Overall Performance:** Over the analysis period, the selected stocks showed a negative trend with an average total return of {avg_return:.2f}%. "

                analysis_text += f"{best_stock} was the best performer with a return of {max_return:.2f}%, while {worst_stock} was the worst with {min_return:.2f}%. "

                # Risk analysis
                avg_volatility = stats_df['Std Dev (%)'].mean()
                max_volatility_stock = stats_df.loc[stats_df['Std Dev (%)'].idxmax(), 'htick']
                max_volatility = stats_df['Std Dev (%)'].max()

                if avg_volatility < 1.5:
                    analysis_text += f"In terms of risk, these stocks showed relatively low volatility (average: {avg_volatility:.2f}%), indicating stable price movements. "
                elif avg_volatility < 3:
                    analysis_text += f"In terms of risk, these stocks showed moderate volatility (average: {avg_volatility:.2f}%), which is typical for equity investments. "
                else:
                    analysis_text += f"In terms of risk, these stocks showed high volatility (average: {avg_volatility:.2f}%), suggesting significant price swings. "

                if max_volatility > 3:
                    analysis_text += f"{max_volatility_stock} had the highest volatility at {max_volatility:.2f}%, which may indicate higher risk. "

                # Sharpe ratio analysis
                sharpe_ratios = stats_df['Sharpe Ratio']
                avg_sharpe = sharpe_ratios.mean()
                best_sharpe_stock = stats_df.loc[sharpe_ratios.idxmax(), 'htick']
                best_sharpe = sharpe_ratios.max()
                worst_sharpe_stock = stats_df.loc[sharpe_ratios.idxmin(), 'htick']
                worst_sharpe = sharpe_ratios.min()

                if avg_sharpe > 0.3:
                    analysis_text += f"On a risk-adjusted basis (Sharpe Ratio), the average was {avg_sharpe:.4f}, suggesting good risk-adjusted returns. "
                elif avg_sharpe > 0:
                    analysis_text += f"On a risk-adjusted basis (Sharpe Ratio), the average was {avg_sharpe:.4f}, suggesting moderate risk-adjusted returns. "
                else:
                    analysis_text += f"On a risk-adjusted basis (Sharpe Ratio), the average was {avg_sharpe:.4f}, suggesting poor risk-adjusted returns relative to the risk taken. "

                analysis_text += f"{best_sharpe_stock} had the best risk-adjusted return (Sharpe: {best_sharpe:.4f}), while {worst_sharpe_stock} had the worst (Sharpe: {worst_sharpe:.4f}). "

                # Correlation analysis
                if len(returns_pivot.columns) > 1:
                    correlations = []
                    for i in range(len(correlation.columns)):
                        for j in range(i+1, len(correlation.columns)):
                            correlations.append((correlation.columns[i], correlation.columns[j], correlation.iloc[i, j]))
                    
                    avg_correlation = sum([c[2] for c in correlations]) / len(correlations) if correlations else 0
                    max_corr = max(correlations, key=lambda x: x[2]) if correlations else (None, None, 0)
                    min_corr = min(correlations, key=lambda x: x[2]) if correlations else (None, None, 0)

                    if avg_correlation > 0.7:
                        analysis_text += f"These stocks showed strong positive correlation (avg: {avg_correlation:.2f}), meaning they tend to move together. "
                    elif avg_correlation > 0.3:
                        analysis_text += f"These stocks showed moderate positive correlation (avg: {avg_correlation:.2f}), indicating some co-movement. "
                    elif avg_correlation > -0.3:
                        analysis_text += f"These stocks showed low correlation (avg: {avg_correlation:.2f}), suggesting independent price movements. "
                    else:
                        analysis_text += f"These stocks showed negative correlation (avg: {avg_correlation:.2f}), meaning they tend to move in opposite directions. "

                    if max_corr[2] > 0.8:
                        analysis_text += f"The strongest correlation was between {max_corr[0]} and {max_corr[1]} ({max_corr[2]:.2f}). "
                    if min_corr[2] < 0:
                        analysis_text += f"The most uncorrelated pair was {min_corr[0]} and {min_corr[1]} ({min_corr[2]:.2f}). "

                # Investment insight
                analysis_text += "**Investment Insight:** "
                
                best_overall = stats_df.loc[stats_df['Total Return (%)'].idxmax()]
                safest = stats_df.loc[stats_df['Std Dev (%)'].idxmin()]
                best_risk_adjusted = stats_df.loc[sharpe_ratios.idxmax()]

                analysis_text += f"Based on the analysis: "
                
                if best_overall['Total Return (%)'] > 20:
                    analysis_text += f"For maximum returns, consider {best_overall['htick']} ({best_overall['Total Return (%)']:.2f}% total return). "
                if safest['Std Dev (%)'] < avg_volatility:
                    analysis_text += f"For lower risk, {safest['htick']} showed the most stable performance. "
                if best_risk_adjusted['htick'] != best_overall['htick']:
                    analysis_text += f"For best risk-adjusted returns, {best_risk_adjusted['htick']} (Sharpe: {best_risk_adjusted['Sharpe Ratio']:.4f}) may be preferable. "

                st.markdown(analysis_text)

                st.markdown("---")

                # Download buttons
                st.subheader("📥 Download Data")

                col1, col2 = st.columns([1, 1])

                with col1:
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Raw Data (CSV)",
                        data=csv,
                        file_name='stock_data.csv',
                        mime='text/csv',
                        use_container_width=True
                    )

                with col2:
                    stats_csv = stats_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📊 Download Statistics (CSV)",
                        data=stats_csv,
                        file_name='stock_statistics.csv',
                        mime='text/csv',
                        use_container_width=True
                    )

                st.markdown("---")

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.info("💡 Make sure your WRDS username and password are correct.")

else:
    st.info("👈 Enter your WRDS credentials and select stocks, then click **'Run Analysis'**")