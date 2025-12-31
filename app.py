import streamlit as st
import hashlib
import base64
from datetime import datetime, timedelta, date
import time
import re
import pandas as pd
import plotly.graph_objects as go
from utils.database import db

# ==================== CONFIGURATION ====================
APP_NAME = "K-Link Analytics"
APP_VERSION = "1.0.0"

# ✅ Load dari secrets.toml atau default
if hasattr(st, 'secrets'):
    SECRET_KEY = st.secrets.get("LICENSE_SECRET", "klink2024secure")
    ENVIRONMENT = "PRODUCTION"
else:
    SECRET_KEY = "klink2024secure"
    ENVIRONMENT = "DEVELOPMENT"

# ==================== PAGE CONFIG ====================
st.set_page_config(
    page_title=APP_NAME,
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== LICENSE VALIDATOR ====================
class LicenseValidator:
    def __init__(self):
        self.secret = SECRET_KEY
    
    def _clean_key(self, key):
        if not key:
            return ""
        key = re.sub(r'\s+', '', key)
        key = re.sub(r'[^A-Za-z0-9+/=]', '', key)
        return key
    
    def validate(self, license_key):
        try:
            license_key = self._clean_key(license_key)
            
            if not license_key or len(license_key) < 20:
                return False, "❌ Invalid license key format"
            
            # Add padding
            padding = 4 - (len(license_key) % 4)
            if padding != 4:
                license_key += '=' * padding
            
            try:
                decoded = base64.b64decode(license_key).decode('utf-8')
            except:
                return False, "❌ Invalid license encoding"
            
            parts = decoded.split('|')
            
            if len(parts) != 3:
                return False, "❌ Invalid license format"
            
            email, expiry_str, signature = parts
            
            if '@' not in email or '.' not in email:
                return False, "❌ Invalid email in license"
            
            data = f"{email}|{expiry_str}"
            expected = hashlib.md5(f"{data}{self.secret}".encode()).hexdigest()[:8]
            
            if signature != expected:
                return False, "❌ License validation failed"
            
            try:
                if len(expiry_str) != 14:
                    return False, "❌ Invalid expiry format"
                expiry = datetime.strptime(expiry_str, "%Y%m%d%H%M%S")
            except:
                return False, "❌ Invalid expiry date"
            
            if datetime.now() > expiry:
                return False, f"⏰ License expired on {expiry.strftime('%d %B %Y')}"
            
            days_left = (expiry - datetime.now()).days
            
            return True, {
                "email": email,
                "expiry": expiry,
                "days_left": days_left,
                "license_key": license_key,
                "environment": ENVIRONMENT
            }
            
        except Exception as e:
            return False, f"⚠️ Error: {str(e)[:100]}"

# ==================== UTILITY FUNCTIONS ====================
def safe_float(value):
    try:
        return float(value)
    except:
        return 0.0

def fmt_number(n):
    n_float = safe_float(n)
    
    if n_float >= 1_000_000_000:
        return f"{n_float/1_000_000_000:.1f}B"
    elif n_float >= 1_000_000:
        return f"{n_float/1_000_000:.1f}M"
    elif n_float >= 1_000:
        return f"{n_float/1_000:.1f}K"
    else:
        return f"{int(n_float):,}"

def fmt_currency(n):
    n_float = safe_float(n)
    return f"Rp {int(n_float):,}"

def fmt_percent(n):
    n_float = safe_float(n)
    return f"{n_float:.1f}%"

def calculate_growth(current, previous):
    current_float = safe_float(current)
    previous_float = safe_float(previous)
    
    if previous_float == 0:
        return 0
    return ((current_float - previous_float) / previous_float) * 100

# ==================== OPTIMIZED DATA FUNCTIONS ====================
@st.cache_data(ttl=300)  # Cache 5 menit
def get_today_stats():
    """Get today's statistics - OPTIMIZED"""
    q = """
    SELECT 
        COUNT(*) AS total_transactions,
        SUM(tbv) AS total_bv,
        SUM(tdp) AS total_tdp,
        COUNT(DISTINCT dfno) AS unique_members,
        COUNT(DISTINCT loccd) AS unique_stockists
    FROM klink_mlm2010.dbo.newtrh
    WHERE CAST(createdt AS DATE) = CAST(GETDATE() AS DATE)
    """
    return db.query(q)

@st.cache_data(ttl=300)
def get_yesterday_stats():
    """Get yesterday's statistics"""
    q = """
    SELECT 
        COUNT(*) AS total_transactions,
        SUM(tbv) AS total_bv,
        SUM(tdp) AS total_tdp,
        COUNT(DISTINCT dfno) AS unique_members
    FROM klink_mlm2010.dbo.newtrh
    WHERE CAST(createdt AS DATE) = CAST(DATEADD(DAY, -1, GETDATE()) AS DATE)
    """
    return db.query(q)

@st.cache_data(ttl=600)  # Cache 10 menit
def get_monthly_stats():
    """Get current month statistics"""
    q = """
    SELECT 
        COUNT(*) AS total_transactions,
        SUM(tbv) AS total_bv,
        SUM(tdp) AS total_tdp,
        COUNT(DISTINCT dfno) AS unique_members,
        COUNT(DISTINCT loccd) AS unique_stockists
    FROM klink_mlm2010.dbo.newtrh
    WHERE YEAR(createdt) = YEAR(GETDATE()) 
      AND MONTH(createdt) = MONTH(GETDATE())
    """
    return db.query(q)

@st.cache_data(ttl=300)
def get_last_7days():
    """Get last 7 days trend (lebih ringan dari 30 hari)"""
    q = """
    SELECT TOP 7
        CAST(createdt AS DATE) AS trx_date,
        COUNT(*) AS total_transactions,
        SUM(tbv) AS total_bv,
        COUNT(DISTINCT dfno) AS unique_members
    FROM klink_mlm2010.dbo.newtrh
    WHERE createdt >= DATEADD(DAY, -7, GETDATE())
    GROUP BY CAST(createdt AS DATE)
    ORDER BY trx_date
    """
    return db.query(q)

@st.cache_data(ttl=300)
def get_top_stockists():
    """Get top 5 stockists (lebih ringan)"""
    q = """
    SELECT TOP 5
        loccd AS stockist_code,
        SUM(tbv) AS total_bv,
        COUNT(*) AS transaction_count
    FROM klink_mlm2010.dbo.newtrh
    WHERE CAST(createdt AS DATE) = CAST(GETDATE() AS DATE)
    GROUP BY loccd
    ORDER BY total_bv DESC
    """
    return db.query(q)

# ==================== NEW: MEMBER JOIN FUNCTIONS ====================
@st.cache_data(ttl=300)
def get_today_member_join():
    """Get today's member join statistics"""
    q = """
    SELECT 
        COUNT(*) AS total_join,
        COUNT(CASE WHEN status = 'A' THEN 1 END) AS active_members
    FROM klink_mlm2010.dbo.msmemb
    WHERE CAST(jointdt AS DATE) = CAST(GETDATE() AS DATE)
    """
    return db.query(q)

@st.cache_data(ttl=600)
def get_monthly_member_join():
    """Get monthly member join statistics"""
    q = """
    SELECT 
        COUNT(*) AS total_join,
        COUNT(CASE WHEN status = 'A' THEN 1 END) AS active_members
    FROM klink_mlm2010.dbo.msmemb
    WHERE YEAR(jointdt) = YEAR(GETDATE()) 
      AND MONTH(jointdt) = MONTH(GETDATE())
    """
    return db.query(q)

@st.cache_data(ttl=300)
def get_member_join_trend():
    """Get member join trend for last 7 days"""
    q = """
    SELECT TOP 7
        CAST(jointdt AS DATE) AS join_date,
        COUNT(*) AS daily_join
    FROM klink_mlm2010.dbo.msmemb
    WHERE jointdt >= DATEADD(DAY, -7, GETDATE())
    GROUP BY CAST(jointdt AS DATE)
    ORDER BY join_date
    """
    return db.query(q)

# ==================== COMPACT LOGIN PAGE ====================
def show_login():
    """Show compact login page"""
    # Clear sidebar
    st.sidebar.empty()
    
    # Simple centered layout
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Simple header
        st.markdown(f"""
        <div style='text-align: center; margin-bottom: 20px;'>
            <h2 style='color: #4B0082;'>🔐 {APP_NAME}</h2>
            <p style='color: #666; font-size: 14px;'>v{APP_VERSION} • {ENVIRONMENT}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Database status
        status = db.get_status()
        if "demo" in status.lower():
            st.warning(status)
        else:
            st.success(status)
        
        # Tabs for different login methods
        tab1, tab2 = st.tabs(["📝 **Paste Key**", "📤 **Upload File**"])
        
        license_input = ""
        
        with tab1:
            # Default tab: Paste Key
            license_input = st.text_area(
                "**License Key:**",
                height=80,
                placeholder="Paste your license key here...",
                key="license_input"
            )
            
            # Demo key shortcut
            with st.expander("🚀 **Quick Demo**", expanded=False):
                demo_email = "demo@klink.com"
                expiry_date = datetime.now() + timedelta(days=365)
                expiry_str = expiry_date.strftime("%Y%m%d%H%M%S")
                
                data = f"{demo_email}|{expiry_str}"
                signature = hashlib.md5(f"{data}{SECRET_KEY}".encode()).hexdigest()[:8]
                license_data = f"{data}|{signature}"
                demo_key = base64.b64encode(license_data.encode()).decode()
                
                st.code(demo_key, language="text")
                
                if st.button("Use Demo Key", key="demo_btn", use_container_width=True):
                    license_input = demo_key
                    st.rerun()
        
        with tab2:
            uploaded = st.file_uploader(
                "Choose license file",
                type=['key', 'txt', 'lic'],
                help="Upload .key, .txt, or .lic file"
            )
            
            if uploaded:
                try:
                    content = uploaded.read().decode('utf-8')
                    matches = re.findall(r'[A-Za-z0-9+/=]{20,}', content)
                    license_input = matches[0] if matches else content.strip()
                    st.success("✅ File loaded successfully")
                except:
                    st.error("❌ Failed to read file")
        
        # Validate button
        if st.button("🔑 **VALIDATE & LOGIN**", type="primary", use_container_width=True):
            if not license_input:
                st.error("Please enter or upload a license key")
            else:
                with st.spinner("Validating..."):
                    validator = LicenseValidator()
                    valid, result = validator.validate(license_input)
                    
                    if valid:
                        st.session_state.authenticated = True
                        st.session_state.user_info = result
                        st.success(f"✅ Welcome {result['email']}!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(result)
        
        # Footer
        st.markdown("---")
        st.caption(f"© 2024 {APP_NAME}")

# ==================== OPTIMIZED DASHBOARD ====================
def show_main_dashboard():
    """Show optimized main dashboard"""
    # Show data source
    if db.is_demo():
        st.warning("📊 **Demo Mode**: Showing sample data")
    else:
        st.success("✅ **Live Data**: Connected to database")
    
    st.title("📊 K-Link Dashboard")
    st.caption(f"Real-time analytics • {datetime.now().strftime('%d %B %Y %H:%M')}")
    
    # Refresh button
    if st.button("🔄 Refresh Data", key="refresh_main"):
        st.cache_data.clear()
        st.rerun()
    
    # Load data with progress
    with st.spinner("🔄 Loading data..."):
        # Load critical data first
        today_df = get_today_stats()
        yesterday_df = get_yesterday_stats()
        
        # Load other data in background
        monthly_df = get_monthly_stats()
        trend_df = get_last_7days()
        top_stockists = get_top_stockists()
        
        # New: Member join data
        today_join = get_today_member_join()
        monthly_join = get_monthly_member_join()
        join_trend = get_member_join_trend()
    
    # ====================
    # KPI CARDS - ROW 1
    # ====================
    st.subheader("🎯 Today's Performance")
    
    if not today_df.empty:
        today_stats = today_df.iloc[0]
        
        # Get values safely
        today_transactions = safe_float(today_stats.get('total_transactions', 0))
        today_bv = safe_float(today_stats.get('total_bv', 0))
        today_tdp = safe_float(today_stats.get('total_tdp', 0))
        today_members = safe_float(today_stats.get('unique_members', 0))
        today_stockists = safe_float(today_stats.get('unique_stockists', 0))
        
        # Get yesterday for comparison
        if not yesterday_df.empty:
            yesterday_stats = yesterday_df.iloc[0]
            yesterday_transactions = safe_float(yesterday_stats.get('total_transactions', 0))
            yesterday_bv = safe_float(yesterday_stats.get('total_bv', 0))
            yesterday_tdp = safe_float(yesterday_stats.get('total_tdp', 0))
            yesterday_members = safe_float(yesterday_stats.get('unique_members', 0))
        else:
            yesterday_transactions = yesterday_bv = yesterday_tdp = yesterday_members = 0
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            delta_tx = calculate_growth(today_transactions, yesterday_transactions)
            st.metric("Transactions", fmt_number(today_transactions), fmt_percent(delta_tx))
        
        with col2:
            delta_bv = calculate_growth(today_bv, yesterday_bv)
            st.metric("Business Volume", fmt_number(today_bv), fmt_percent(delta_bv))
        
        with col3:
            delta_tdp = calculate_growth(today_tdp, yesterday_tdp)
            st.metric("Total Sales", fmt_currency(today_tdp), fmt_percent(delta_tdp))
        
        with col4:
            delta_mem = calculate_growth(today_members, yesterday_members)
            st.metric("Active Members", fmt_number(today_members), fmt_percent(delta_mem))
        
        with col5:
            st.metric("Active Stockists", fmt_number(today_stockists), "Today")
    
    # ====================
    # MEMBER JOIN SECTION - NEW
    # ====================
    st.subheader("👥 Member Growth")
    
    if not today_join.empty:
        today_join_stats = today_join.iloc[0]
        monthly_join_stats = monthly_join.iloc[0] if not monthly_join.empty else {}
        
        today_join_count = safe_float(today_join_stats.get('total_join', 0))
        today_active = safe_float(today_join_stats.get('active_members', 0))
        monthly_join_count = safe_float(monthly_join_stats.get('total_join', 0))
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Today's Join", fmt_number(today_join_count), "New Members")
        
        with col2:
            st.metric("Active Today", fmt_number(today_active), "Active")
        
        with col3:
            st.metric("Monthly Join", fmt_number(monthly_join_count), "This Month")
    
    # ====================
    # CHARTS SECTION
    # ====================
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📈 Daily Trend")
        if not trend_df.empty and 'trx_date' in trend_df.columns:
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=trend_df["trx_date"],
                y=trend_df["total_bv"],
                mode='lines',
                name='BV',
                line=dict(color='#2E86AB', width=3),
                fill='tozeroy',
                fillcolor='rgba(46, 134, 171, 0.1)'
            ))
            
            fig.update_layout(
                title="Business Volume (Last 7 Days)",
                height=300,
                template="plotly_white",
                margin=dict(l=20, r=20, t=40, b=20),
                showlegend=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No trend data available")
    
    with col2:
        st.subheader("🏆 Top Stockists")
        if not top_stockists.empty:
            # Create better visualization
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                y=top_stockists["stockist_code"],
                x=top_stockists["total_bv"],
                orientation='h',
                marker_color='#4ECDC4',
                text=top_stockists["total_bv"].apply(fmt_number),
                textposition='auto'
            ))
            
            fig.update_layout(
                title="Today's Top 5",
                height=300,
                template="plotly_white",
                margin=dict(l=80, r=20, t=40, b=20),  # More left margin for labels
                xaxis_title="BV",
                yaxis_title="Stockist",
                showlegend=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No stockist data available")
    
    # ====================
    # MONTHLY SUMMARY
    # ====================
    st.subheader("📅 Monthly Summary")
    
    if not monthly_df.empty:
        monthly_stats = monthly_df.iloc[0]
        
        monthly_bv = safe_float(monthly_stats.get('total_bv', 0))
        monthly_members = safe_float(monthly_stats.get('unique_members', 0))
        monthly_transactions = safe_float(monthly_stats.get('total_transactions', 0))
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            progress = min(100, (date.today().day / 30) * 100)
            st.metric(
                label="Month Progress",
                value=f"{date.today().day}/30",
                delta=f"{progress:.0f}%"
            )
        
        with col2:
            st.metric(
                label="Monthly BV",
                value=fmt_number(monthly_bv),
                delta="This Month"
            )
        
        with col3:
            avg_daily_bv = monthly_bv / date.today().day if date.today().day > 0 else 0
            st.metric(
                label="Avg Daily BV",
                value=fmt_number(avg_daily_bv),
                delta="Month to Date"
            )
        
        with col4:
            st.metric(
                label="Total Members",
                value=fmt_number(monthly_members),
                delta="This Month"
            )
    
    # ====================
    # SYSTEM STATUS
    # ====================
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Test database connection
        test_df = db.query("SELECT GETDATE() AS server_time")
        if test_df is not None and not test_df.empty:
            st.success("✅ **Database:** Connected")
            server_time = test_df.iloc[0]['server_time']
            if isinstance(server_time, datetime):
                st.caption(f"Server Time: {server_time.strftime('%H:%M:%S')}")
        else:
            st.warning("⚠️ **Database:** Using demo data")
    
    with col2:
        st.success("✅ **Application:** Running")
        st.caption(f"Environment: {ENVIRONMENT}")
        st.caption(f"Last Update: {datetime.now().strftime('%H:%M:%S')}")

# ==================== SETTINGS PAGE ====================
def show_settings():
    """Show settings page"""
    st.title("⚙️ Settings")
    
    user = st.session_state.user_info
    
    with st.expander("👤 Account Information", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Email:** {user['email']}")
            st.write(f"**Environment:** {user.get('environment', 'N/A')}")
        
        with col2:
            days = user['days_left']
            if days > 30:
                status = "✅ Active"
            elif days > 7:
                status = "⚠️ Expiring Soon"
            else:
                status = "⏰ Critical"
            
            st.write(f"**License Status:** {status}")
            st.write(f"**Days Remaining:** {days}")
            st.caption(f"Expires: {user['expiry'].strftime('%d %b %Y')}")
    
    with st.expander("🔧 Database Configuration"):
        st.write(f"**Status:** {db.get_status()}")
        
        if st.button("🔄 Test Connection"):
            test_result = db.query("SELECT GETDATE() AS server_time")
            if test_result is not None and not test_result.empty:
                st.success(f"✅ Connected! Server: {test_result.iloc[0]['server_time']}")
            else:
                st.warning("⚠️ Using demo data")
        
        if st.button("🔄 Clear Cache"):
            st.cache_data.clear()
            st.success("Cache cleared!")
            time.sleep(1)
            st.rerun()

# ==================== AUTH CHECK ====================
def check_auth():
    """Check authentication status"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        return False
    
    if 'user_info' not in st.session_state:
        st.session_state.authenticated = False
        return False
    
    # Check expiry
    user_info = st.session_state.user_info
    if datetime.now() > user_info['expiry']:
        st.session_state.authenticated = False
        st.session_state.expired_msg = "⏰ Your license has expired"
        return False
    
    return True

# ==================== DASHBOARD NAVIGATION ====================
def show_dashboard():
    """Show main dashboard with sidebar"""
    user = st.session_state.user_info
    
    # Sidebar
    with st.sidebar:
        st.markdown(f"### 👤 {user['email'].split('@')[0]}")
        
        # License status
        days = user['days_left']
        if days > 30:
            icon = "✅"
        elif days > 7:
            icon = "⚠️"
        else:
            icon = "⏰"
        
        st.markdown(f"{icon} **License:** {days} days")
        st.caption(f"Expires: {user['expiry'].strftime('%d %b %Y')}")
        
        # Database status
        st.markdown("---")
        if db.is_demo():
            st.warning("📊 Demo Data")
        else:
            st.success("✅ Live Database")
        
        st.markdown("---")
        
        # Navigation
        pages = ["🏠 Dashboard", "⚙️ Settings"]
        
        if 'current_page' not in st.session_state:
            st.session_state.current_page = pages[0]
        
        for page in pages:
            if st.button(
                page, 
                use_container_width=True,
                type="primary" if st.session_state.current_page == page else "secondary"
            ):
                st.session_state.current_page = page
                st.rerun()
        
        st.markdown("---")
        
        # Logout button
        if st.button("🚪 **Logout**", use_container_width=True):
            for key in ['authenticated', 'user_info', 'current_page']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        
        # Footer
        st.caption(f"v{APP_VERSION} • {ENVIRONMENT}")
    
    # Show selected page
    if st.session_state.current_page == "🏠 Dashboard":
        show_main_dashboard()
    elif st.session_state.current_page == "⚙️ Settings":
        show_settings()

# ==================== MAIN APPLICATION ====================
def main():
    """Main application flow"""
    
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    # Check authentication
    if not check_auth():
        show_login()
    else:
        show_dashboard()

if __name__ == "__main__":
    main()