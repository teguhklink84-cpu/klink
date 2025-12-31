import streamlit as st
import hashlib
import base64
from datetime import datetime, timedelta, date
import time
import re
import pandas as pd
import plotly.graph_objects as go
from sshtunnel import SSHTunnelForwarder
import pyodbc
from decimal import Decimal

# ==================== CONFIGURATION ====================
APP_NAME = "K-Link Analytics"
APP_VERSION = "1.0.0"

# ✅ Load dari secrets.toml atau default
if hasattr(st, 'secrets'):
    # Running di Streamlit Cloud / dengan secrets.toml
    SECRET_KEY = st.secrets.get("LICENSE_SECRET", "klink2024secure")
    ENVIRONMENT = "PRODUCTION"
    
    # Database configuration dari secrets
    DB_CONFIG = {
        'use_ssh': st.secrets.get("USE_SSH", True),
        'ssh_host': st.secrets.get("SSH_HOST", ""),
        'ssh_port': st.secrets.get("SSH_PORT", 22),
        'ssh_user': st.secrets.get("SSH_USER", ""),
        'ssh_pass': st.secrets.get("SSH_PASS", ""),
        'db_host': st.secrets.get("DB_HOST", ""),
        'db_port': st.secrets.get("DB_PORT", 1433),
        'db_name': st.secrets.get("DB_NAME", "klink_mlm2010"),
        'db_user': st.secrets.get("DB_USER", ""),
        'db_pass': st.secrets.get("DB_PASS", "")
    }
else:
    # Running di local tanpa secrets
    SECRET_KEY = "klink2024secure"
    ENVIRONMENT = "DEVELOPMENT"
    DB_CONFIG = {}

# ==================== PAGE CONFIG ====================
st.set_page_config(
    page_title=APP_NAME,
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== DATABASE CONNECTION ====================
class DatabaseConnector:
    def __init__(self):
        self.connection = None
        self.tunnel = None
        self.is_connected = False
    
    def initialize_from_secrets(self):
        """Initialize database connection from secrets.toml"""
        if not DB_CONFIG:
            return False, "No database configuration found"
        
        try:
            # Check which connection method to use
            if DB_CONFIG.get('use_ssh', True) and DB_CONFIG.get('ssh_host'):
                # Use SSH connection
                return self.connect_with_ssh(
                    ssh_host=DB_CONFIG['ssh_host'],
                    ssh_port=DB_CONFIG['ssh_port'],
                    ssh_username=DB_CONFIG['ssh_user'],
                    ssh_password=DB_CONFIG['ssh_pass'],
                    db_host=DB_CONFIG['db_host'],
                    db_port=DB_CONFIG['db_port'],
                    db_database=DB_CONFIG['db_name'],
                    db_username=DB_CONFIG['db_user'],
                    db_password=DB_CONFIG['db_pass']
                )
            else:
                # Use direct connection
                return self.connect_direct(
                    server=DB_CONFIG['db_host'],
                    database=DB_CONFIG['db_name'],
                    username=DB_CONFIG['db_user'],
                    password=DB_CONFIG['db_pass'],
                    port=DB_CONFIG['db_port']
                )
                
        except Exception as e:
            return False, f"Initialization error: {str(e)}"
    
    def connect_with_ssh(self, ssh_host, ssh_port, ssh_username, ssh_password,
                        db_host, db_port, db_database, db_username, db_password):
        """Connect via SSH tunnel"""
        try:
            self.tunnel = SSHTunnelForwarder(
                (ssh_host, ssh_port),
                ssh_username=ssh_username,
                ssh_password=ssh_password,
                remote_bind_address=(db_host, db_port),
                local_bind_address=('127.0.0.1', 0)
            )
            
            self.tunnel.start()
            local_port = self.tunnel.local_bind_port
            
            conn_str = f"""
                DRIVER={{ODBC Driver 17 for SQL Server}};
                SERVER=127.0.0.1,{local_port};
                DATABASE={db_database};
                UID={db_username};
                PWD={db_password};
                TrustServerCertificate=yes;
            """
            
            self.connection = pyodbc.connect(conn_str)
            self.is_connected = True
            return True, "✅ Connected via SSH"
            
        except Exception as e:
            return False, f"❌ SSH Connection failed: {str(e)}"
    
    def connect_direct(self, server, database, username, password, port=1433):
        """Direct connection without SSH"""
        try:
            conn_str = f"""
                DRIVER={{ODBC Driver 17 for SQL Server}};
                SERVER={server},{port};
                DATABASE={database};
                UID={username};
                PWD={password};
                TrustServerCertificate=yes;
            """
            
            self.connection = pyodbc.connect(conn_str)
            self.is_connected = True
            return True, "✅ Direct connection successful"
            
        except pyodbc.InterfaceError:
            try:
                conn_str = f"""
                    DRIVER={{ODBC Driver 18 for SQL Server}};
                    SERVER={server},{port};
                    DATABASE={database};
                    UID={username};
                    PWD={password};
                    TrustServerCertificate=yes;
                """
                self.connection = pyodbc.connect(conn_str)
                self.is_connected = True
                return True, "✅ Connected with ODBC Driver 18"
            except Exception as e2:
                return False, f"❌ Connection failed: {str(e2)}"
        except Exception as e:
            return False, f"❌ Connection failed: {str(e)}"
    
    def query(self, query, params=None):
        """Execute SQL query and return DataFrame"""
        try:
            if not self.is_connected or not self.connection:
                # Try to reconnect if not connected
                success, message = self.initialize_from_secrets()
                if not success:
                    return None
            
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            if query.strip().upper().startswith('SELECT'):
                columns = [column[0] for column in cursor.description]
                results = cursor.fetchall()
                df = pd.DataFrame.from_records(results, columns=columns)
                return df
            else:
                self.connection.commit()
                return pd.DataFrame()
                
        except Exception as e:
            print(f"Query failed: {str(e)}")
            return None
    
    def test_connection(self):
        """Test database connection"""
        try:
            test_df = self.query("SELECT GETDATE() AS server_time")
            return test_df is not None
        except:
            return False
    
    def close(self):
        """Close connection and tunnel"""
        if self.connection:
            try:
                self.connection.close()
            except:
                pass
        if self.tunnel:
            try:
                self.tunnel.stop()
            except:
                pass
        self.is_connected = False

# Global database instance - INITIALIZE ONCE
if 'db' not in st.session_state:
    st.session_state.db = DatabaseConnector()
    # Try to initialize from secrets
    if DB_CONFIG:
        success, message = st.session_state.db.initialize_from_secrets()
        if success:
            st.session_state.db_initialized = True
            st.session_state.db_message = message
        else:
            st.session_state.db_initialized = False
            st.session_state.db_message = message
    else:
        st.session_state.db_initialized = False
        st.session_state.db_message = "No database configuration found"

db = st.session_state.db

# ==================== LICENSE VALIDATOR ====================
class LicenseValidator:
    def __init__(self):
        self.secret = SECRET_KEY
    
    def _clean_key(self, key):
        """Clean license key"""
        if not key:
            return ""
        key = re.sub(r'\s+', '', key)
        key = re.sub(r'[^A-Za-z0-9+/=]', '', key)
        return key
    
    def validate(self, license_key):
        """Validate license key"""
        try:
            license_key = self._clean_key(license_key)
            
            if not license_key or len(license_key) < 20:
                return False, "❌ Invalid license key format"
            
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
    """Convert value to float safely"""
    try:
        if isinstance(value, Decimal):
            return float(value)
        elif isinstance(value, (int, float)):
            return float(value)
        elif pd.isna(value):
            return 0.0
        else:
            return float(value)
    except:
        return 0.0

def safe_get(dict_obj, key, default=0):
    """Safely get value from dictionary"""
    if key in dict_obj:
        return dict_obj[key]
    return default

def fmt_number(n):
    """Format number with K, M suffixes"""
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
    """Format currency"""
    n_float = safe_float(n)
    return f"Rp {int(n_float):,}"

def fmt_percent(n):
    """Format percentage"""
    n_float = safe_float(n)
    return f"{n_float:.1f}%"

def calculate_growth(current, previous):
    """Calculate growth percentage safely"""
    current_float = safe_float(current)
    previous_float = safe_float(previous)
    
    if previous_float == 0:
        return 0
    return ((current_float - previous_float) / previous_float) * 100

# ==================== DATA FUNCTIONS (CACHED) ====================
@st.cache_data(ttl=600)
def get_today_stats():
    """Get today's statistics"""
    if not st.session_state.get('db_initialized', False):
        return pd.DataFrame([{
            'total_transactions': 0, 'total_bv': 0, 'total_tdp': 0,
            'unique_members': 0, 'unique_stockists': 0
        }])
    
    q = """
    SELECT 
        ISNULL(COUNT(*), 0) AS total_transactions,
        ISNULL(SUM(tbv), 0) AS total_bv,
        ISNULL(SUM(tdp), 0) AS total_tdp,
        ISNULL(COUNT(DISTINCT dfno), 0) AS unique_members,
        ISNULL(COUNT(DISTINCT loccd), 0) AS unique_stockists
    FROM klink_mlm2010.dbo.newtrh
    WHERE CAST(createdt AS DATE) = CAST(GETDATE() AS DATE)
    """
    result = db.query(q)
    if result is None or result.empty:
        return pd.DataFrame([{
            'total_transactions': 0, 'total_bv': 0, 'total_tdp': 0,
            'unique_members': 0, 'unique_stockists': 0
        }])
    return result

@st.cache_data(ttl=600)
def get_yesterday_stats():
    """Get yesterday's statistics"""
    if not st.session_state.get('db_initialized', False):
        return pd.DataFrame([{
            'total_transactions': 0, 'total_bv': 0, 
            'total_tdp': 0, 'unique_members': 0
        }])
    
    q = """
    SELECT 
        ISNULL(COUNT(*), 0) AS total_transactions,
        ISNULL(SUM(tbv), 0) AS total_bv,
        ISNULL(SUM(tdp), 0) AS total_tdp,
        ISNULL(COUNT(DISTINCT dfno), 0) AS unique_members
    FROM klink_mlm2010.dbo.newtrh
    WHERE CAST(createdt AS DATE) = CAST(DATEADD(DAY, -1, GETDATE()) AS DATE)
    """
    result = db.query(q)
    if result is None or result.empty:
        return pd.DataFrame([{
            'total_transactions': 0, 'total_bv': 0, 
            'total_tdp': 0, 'unique_members': 0
        }])
    return result

@st.cache_data(ttl=1800)
def get_monthly_stats():
    """Get current month statistics"""
    if not st.session_state.get('db_initialized', False):
        return pd.DataFrame([{
            'total_transactions': 0, 'total_bv': 0, 'total_tdp': 0,
            'unique_members': 0, 'unique_stockists': 0
        }])
    
    q = """
    SELECT 
        ISNULL(COUNT(*), 0) AS total_transactions,
        ISNULL(SUM(tbv), 0) AS total_bv,
        ISNULL(SUM(tdp), 0) AS total_tdp,
        ISNULL(COUNT(DISTINCT dfno), 0) AS unique_members,
        ISNULL(COUNT(DISTINCT loccd), 0) AS unique_stockists
    FROM klink_mlm2010.dbo.newtrh
    WHERE YEAR(createdt) = YEAR(GETDATE()) 
      AND MONTH(createdt) = MONTH(GETDATE())
    """
    result = db.query(q)
    if result is None or result.empty:
        return pd.DataFrame([{
            'total_transactions': 0, 'total_bv': 0, 'total_tdp': 0,
            'unique_members': 0, 'unique_stockists': 0
        }])
    return result

@st.cache_data(ttl=600)
def get_last_30days():
    """Get last 30 days trend"""
    if not st.session_state.get('db_initialized', False):
        return pd.DataFrame(columns=['trx_date', 'total_transactions', 'total_bv', 'unique_members'])
    
    q = """
    SELECT TOP 30
        CAST(createdt AS DATE) AS trx_date,
        ISNULL(COUNT(*), 0) AS total_transactions,
        ISNULL(SUM(tbv), 0) AS total_bv,
        ISNULL(COUNT(DISTINCT dfno), 0) AS unique_members
    FROM klink_mlm2010.dbo.newtrh
    WHERE createdt >= DATEADD(DAY, -30, GETDATE())
    GROUP BY CAST(createdt AS DATE)
    ORDER BY trx_date DESC
    """
    result = db.query(q)
    if result is None or result.empty:
        return pd.DataFrame(columns=['trx_date', 'total_transactions', 'total_bv', 'unique_members'])
    return result.sort_values('trx_date')

@st.cache_data(ttl=600)
def get_top_stockists():
    """Get top 10 stockists"""
    if not st.session_state.get('db_initialized', False):
        return pd.DataFrame(columns=['stockist_code', 'total_bv', 'transaction_count', 'unique_members'])
    
    q = """
    SELECT TOP 10
        loccd AS stockist_code,
        ISNULL(SUM(tbv), 0) AS total_bv,
        ISNULL(COUNT(*), 0) AS transaction_count,
        ISNULL(COUNT(DISTINCT dfno), 0) AS unique_members
    FROM klink_mlm2010.dbo.newtrh
    WHERE CAST(createdt AS DATE) = CAST(GETDATE() AS DATE)
    GROUP BY loccd
    ORDER BY total_bv DESC
    """
    result = db.query(q)
    return result if result is not None else pd.DataFrame()

# ==================== CHART FUNCTIONS ====================
def create_daily_trend_chart(trend_df):
    """Create daily trend chart"""
    if trend_df.empty or len(trend_df) < 2:
        return None
    
    # Convert to safe floats for plotting
    trend_df = trend_df.copy()
    trend_df['total_bv'] = trend_df['total_bv'].apply(safe_float)
    
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
        title="📈 Daily BV Trend",
        xaxis_title="",
        yaxis_title="BV",
        template="plotly_white",
        hovermode="x unified",
        showlegend=True,
        height=300,
        margin=dict(l=40, r=20, t=50, b=40),
        xaxis=dict(
            showgrid=False,
            tickformat="%b %d"
        ),
        yaxis=dict(
            gridcolor='rgba(0,0,0,0.05)'
        )
    )
    
    return fig

def create_stockist_chart(stockist_df):
    """Create bar chart for top stockists"""
    if stockist_df.empty:
        return None
    
    # Convert to safe floats
    stockist_df = stockist_df.copy()
    stockist_df['total_bv'] = stockist_df['total_bv'].apply(safe_float)
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=stockist_df["stockist_code"],
        y=stockist_df["total_bv"],
        name="BV",
        marker_color='#4ECDC4',
        text=stockist_df["total_bv"].apply(lambda x: fmt_number(x)),
        textposition='auto'
    ))
    
    fig.update_layout(
        title="🏆 Top Stockists (Today)",
        xaxis_title="Stockist Code",
        yaxis_title="BV",
        template="plotly_white",
        height=300,
        showlegend=False,
        margin=dict(l=40, r=20, t=50, b=60),
        xaxis=dict(tickangle=45)
    )
    
    return fig

# ==================== LOGIN PAGE ====================
def show_login():
    """Show login page"""
    # Clear sidebar for login
    st.sidebar.empty()
    
    # Main content
    st.markdown(f"""
    <style>
    .login-header {{
        text-align: center;
        padding: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
        color: white;
        margin-bottom: 30px;
    }}
    .env-badge {{
        position: absolute;
        top: 10px;
        right: 10px;
        background: #4CAF50;
        color: white;
        padding: 5px 10px;
        border-radius: 5px;
        font-size: 12px;
    }}
    </style>
    
    <div class="env-badge">{ENVIRONMENT}</div>
    <div class="login-header">
        <h1>🔐 {APP_NAME}</h1>
        <p>v{APP_VERSION} | Professional Analytics Platform</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.info("**Quick Start:** Enter your license key below")
        
        tab1, tab2 = st.tabs(["📝 Paste Key", "📤 Upload File"])
        
        license_input = ""
        
        with tab1:
            license_input = st.text_area(
                "License Key:", 
                height=100,
                placeholder="Paste your license key here..."
            )
        
        with tab2:
            uploaded = st.file_uploader("Choose file", type=['txt', 'key', 'lic'])
            if uploaded:
                try:
                    content = uploaded.read().decode('utf-8')
                    matches = re.findall(r'[A-Za-z0-9+/=]{20,}', content)
                    license_input = matches[0] if matches else content.strip()
                    st.success("✅ File loaded successfully")
                except:
                    st.error("❌ Failed to read file")
        
        if st.button("🔑 **VALIDATE LICENSE**", type="primary", use_container_width=True):
            if license_input:
                with st.spinner("🔍 Validating license..."):
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
            else:
                st.warning("⚠️ Please enter a license key")
        
        # Database connection status
        st.markdown("---")
        if st.session_state.get('db_initialized', False):
            st.success(f"✅ Database: {st.session_state.get('db_message', 'Connected')}")
        else:
            st.warning(f"⚠️ Database: {st.session_state.get('db_message', 'Not configured')}")
        
        # Footer
        st.caption(f"© 2024 {APP_NAME} • Secure Analytics Platform")

# ==================== MAIN DASHBOARD ====================
def show_main_dashboard():
    """Show optimized main dashboard"""
    # Main content
    st.title("📊 K-Link Dashboard")
    st.caption(f"Real-time analytics • {datetime.now().strftime('%d %B %Y %H:%M')}")
    
    # Database status
    if not st.session_state.get('db_initialized', False):
        st.error("❌ Database not connected. Please check your configuration in secrets.toml")
        return
    
    # Refresh button
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("🔄 Refresh Data", key="refresh_main"):
            st.cache_data.clear()
            st.rerun()
    
    # Load data
    with st.spinner("🔄 Loading data..."):
        today_df = get_today_stats()
        yesterday_df = get_yesterday_stats()
        monthly_df = get_monthly_stats()
        trend_df = get_last_30days()
        top_stockists = get_top_stockists()
    
    # ====================
    # KPI CARDS
    # ====================
    st.subheader("📈 Today's Performance")
    
    if not today_df.empty:
        today_stats = today_df.iloc[0].to_dict()
        
        # Get yesterday stats safely
        if not yesterday_df.empty:
            yesterday_stats = yesterday_df.iloc[0].to_dict()
        else:
            # Create default yesterday stats if not available
            yesterday_stats = {
                'total_transactions': 0,
                'total_bv': 0,
                'total_tdp': 0,
                'unique_members': 0
            }
        
        # Convert all to safe floats using safe_get
        today_transactions = safe_float(safe_get(today_stats, 'total_transactions', 0))
        yesterday_transactions = safe_float(safe_get(yesterday_stats, 'total_transactions', 0))
        
        today_bv = safe_float(safe_get(today_stats, 'total_bv', 0))
        yesterday_bv = safe_float(safe_get(yesterday_stats, 'total_bv', 0))
        
        today_tdp = safe_float(safe_get(today_stats, 'total_tdp', 0))
        yesterday_tdp = safe_float(safe_get(yesterday_stats, 'total_tdp', 0))
        
        today_members = safe_float(safe_get(today_stats, 'unique_members', 0))
        yesterday_members = safe_float(safe_get(yesterday_stats, 'unique_members', 0))
        
        today_stockists = safe_float(safe_get(today_stats, 'unique_stockists', 0))
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            delta_tx = calculate_growth(today_transactions, yesterday_transactions)
            st.metric(
                label="Transactions",
                value=fmt_number(today_transactions),
                delta=fmt_percent(delta_tx)
            )
        
        with col2:
            delta_bv = calculate_growth(today_bv, yesterday_bv)
            st.metric(
                label="Business Volume",
                value=fmt_number(today_bv),
                delta=fmt_percent(delta_bv)
            )
        
        with col3:
            delta_tdp = calculate_growth(today_tdp, yesterday_tdp)
            st.metric(
                label="Total Sales",
                value=fmt_currency(today_tdp),
                delta=fmt_percent(delta_tdp)
            )
        
        with col4:
            delta_mem = calculate_growth(today_members, yesterday_members)
            st.metric(
                label="Active Members",
                value=fmt_number(today_members),
                delta=fmt_percent(delta_mem)
            )
        
        with col5:
            st.metric(
                label="Active Stockists",
                value=fmt_number(today_stockists),
                delta="Today"
            )
    else:
        st.info("📊 No data available for today")
    
    # ====================
    # CHARTS SECTION
    # ====================
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📈 Daily Trend")
        if not trend_df.empty:
            fig_trend = create_daily_trend_chart(trend_df)
            if fig_trend:
                st.plotly_chart(fig_trend, use_container_width=True)
                
                # Trend analysis with safe calculations
                latest_bv = safe_float(trend_df["total_bv"].iloc[-1]) if len(trend_df) > 0 else 0
                avg_bv = safe_float(trend_df["total_bv"].mean()) if len(trend_df) > 0 else 0
                
                # SAFE division
                if avg_bv > 0:
                    trend_growth = ((latest_bv / avg_bv) - 1) * 100
                else:
                    trend_growth = 0
                
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.info(f"**Latest BV:** {fmt_number(latest_bv)}")
                with col_b:
                    st.info(f"**30-Day Avg:** {fmt_number(avg_bv)}")
                with col_c:
                    if trend_growth > 0:
                        st.info(f"**Trend:** 📈 {fmt_percent(trend_growth)}")
                    else:
                        st.info(f"**Trend:** 📉 {fmt_percent(trend_growth)}")
        else:
            st.info("📊 No trend data available")
    
    with col2:
        st.subheader("🏆 Top Stockists")
        if top_stockists is not None and not top_stockists.empty:
            fig_stockists = create_stockist_chart(top_stockists)
            if fig_stockists:
                st.plotly_chart(fig_stockists, use_container_width=True)
            
            # Show top 3
            if len(top_stockists) > 0:
                st.markdown("**Top 3 Today:**")
                for i, (_, row) in enumerate(top_stockists.head(3).iterrows(), 1):
                    bv_value = safe_float(row['total_bv'])
                    st.markdown(f"{i}. **{row['stockist_code']}** - {fmt_number(bv_value)} BV")
        else:
            st.info("🏢 No stockist data available today")
    
    # ====================
    # MONTHLY SUMMARY
    # ====================
    st.subheader("📅 Monthly Summary")
    
    if not monthly_df.empty:
        monthly_stats = monthly_df.iloc[0].to_dict()
        
        monthly_bv = safe_float(safe_get(monthly_stats, 'total_bv', 0))
        monthly_members = safe_float(safe_get(monthly_stats, 'unique_members', 0))
        
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
            if date.today().day > 0:
                avg_daily = monthly_bv / date.today().day
            else:
                avg_daily = 0
            st.metric(
                label="Avg Daily BV",
                value=fmt_number(avg_daily),
                delta="Month to Date"
            )
        
        with col4:
            st.metric(
                label="Total Members",
                value=fmt_number(monthly_members),
                delta="This Month"
            )
    else:
        st.info("📅 No monthly data available")
    
    # ====================
    # SYSTEM STATUS
    # ====================
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if db.test_connection():
            st.success("✅ **Database:** Connected")
            test_df = db.query("SELECT GETDATE() AS server_time")
            if test_df is not None and not test_df.empty:
                server_time = test_df.iloc[0]['server_time']
                if isinstance(server_time, datetime):
                    st.caption(f"Server Time: {server_time.strftime('%H:%M:%S')}")
        else:
            st.error("❌ **Database:** Disconnected")
    
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
    
    with st.expander("🎨 Display Settings"):
        theme = st.selectbox("Theme", ["Light", "Dark", "System"], key="theme_select")
        refresh_rate = st.selectbox("Auto-refresh", ["Disabled", "5 minutes", "15 minutes", "30 minutes"], key="refresh_select")
        
        if st.button("💾 Save Settings", key="save_settings"):
            st.success("✅ Settings saved!")
    
    with st.expander("🔧 Advanced"):
        if st.button("🔄 Clear Cache", key="clear_cache"):
            st.cache_data.clear()
            st.success("✅ Cache cleared!")
        
        if st.button("🔄 Reconnect Database", key="reconnect_db"):
            success, message = db.initialize_from_secrets()
            if success:
                st.session_state.db_initialized = True
                st.session_state.db_message = message
                st.success("✅ Database reconnected!")
            else:
                st.session_state.db_initialized = False
                st.session_state.db_message = message
                st.error(f"❌ {message}")

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

# ==================== MAIN DASHBOARD WRAPPER ====================
def show_dashboard():
    """Show main dashboard with sidebar navigation"""
    user = st.session_state.user_info
    
    # Sidebar Navigation
    with st.sidebar:
        st.markdown(f"### 👤 {user['email'].split('@')[0]}")
        
        # License status
        days = user['days_left']
        if days > 30:
            color = "green"
            icon = "✅"
        elif days > 7:
            color = "orange"
            icon = "⚠️"
        else:
            color = "red"
            icon = "⏰"
        
        # FIXED: Use markdown for HTML
        st.markdown(f"{icon} **License:** <span style='color:{color}'>{days} days</span>", 
                   unsafe_allow_html=True)
        st.caption(f"Expires: {user['expiry'].strftime('%d %b %Y')}")
        
        # Database status
        st.markdown("---")
        if st.session_state.get('db_initialized', False):
            st.success("✅ DB Connected")
        else:
            st.error("❌ DB Disconnected")
        
        st.markdown("---")
        
        # Navigation buttons
        st.markdown("### 📌 Navigation")
        
        # Define pages
        pages = {
            "🏠 Dashboard": "main",
            "⚙️ Settings": "settings"
        }
        
        # Initialize current page
        if 'current_page' not in st.session_state:
            st.session_state.current_page = "main"
        
        # Create navigation buttons
        for page_name, page_id in pages.items():
            if st.button(
                page_name, 
                use_container_width=True,
                key=f"nav_{page_id}",
                type="primary" if st.session_state.current_page == page_id else "secondary"
            ):
                st.session_state.current_page = page_id
                st.rerun()
        
        st.markdown("---")
        
        # Logout button
        if st.button("🚪 **Logout**", type="secondary", use_container_width=True, key="logout_btn"):
            for key in ['authenticated', 'user_info', 'db_connection', 'current_page']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        
        # Footer
        st.caption(f"v{APP_VERSION} • {ENVIRONMENT}")
    
    # Show selected page
    if st.session_state.current_page == "main":
        show_main_dashboard()
    elif st.session_state.current_page == "settings":
        show_settings()

# ==================== MAIN APPLICATION ====================
def main():
    """Main application flow"""
    
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    # Check authentication and show appropriate page
    if not check_auth():
        show_login()
    else:
        show_dashboard()

# ==================== RUN APPLICATION ====================
if __name__ == "__main__":
    main()