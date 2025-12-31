import streamlit as st
import hashlib
import base64
from datetime import datetime, timedelta, date
import time
import re
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import sys

# ==================== CONFIGURATION ====================
APP_NAME = "K-Link Analytics"
APP_VERSION = "1.0.0"

# ✅ Load dari secrets.toml atau default
if hasattr(st, 'secrets'):
    SECRET_KEY = st.secrets.get("LICENSE_SECRET", "klink2024secure")
    ENVIRONMENT = "PRODUCTION"
    
    DB_CONFIG = {
        'use_ssh': st.secrets.get("USE_SSH", False),
        'ssh_host': st.secrets.get("SSH_HOST", ""),
        'ssh_port': st.secrets.get("SSH_PORT", 22),
        'ssh_user': st.secrets.get("SSH_USER", ""),
        'ssh_pass': st.secrets.get("SSH_PASS", ""),
        'db_host': st.secrets.get("DB_HOST", ""),
        'db_port': st.secrets.get("DB_PORT", 1433),
        'db_name': st.secrets.get("DB_NAME", "klink_mlm2010"),
        'db_user': st.secrets.get("DB_USER", ""),
        'db_pass': st.secrets.get("DB_PASS", ""),
        'direct_server': st.secrets.get("DIRECT_SERVER", ""),
        'direct_database': st.secrets.get("DIRECT_DATABASE", ""),
        'direct_user': st.secrets.get("DIRECT_USER", ""),
        'direct_pass': st.secrets.get("DIRECT_PASS", "")
    }
else:
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

# ==================== SMART DATABASE CONNECTOR ====================
class SmartDatabaseConnector:
    def __init__(self):
        self.connection = None
        self.tunnel = None
        self.is_connected = False
        self.mode = "unknown"  # "real" atau "demo"
        self.connection_message = ""
        self.last_error = ""
        
    def initialize(self):
        """Try real connection first, fallback to demo if fails"""
        try:
            # Try real database connection
            self._try_real_connection()
            self.mode = "real"
            return True
            
        except Exception as e:
            # Fallback to demo mode
            self.last_error = str(e)
            self.mode = "demo"
            self.is_connected = True  # Demo mode is always "connected"
            self.connection_message = f"⚠️ Using demo data (Real DB failed: {str(e)[:80]})"
            print(f"Database fallback to demo: {e}")
            return True  # Still successful in demo mode
    
    def _try_real_connection(self):
        """Try to connect to real database"""
        try:
            # Import inside function to avoid issues if not installed
            import pyodbc
            
            # Determine connection method
            if DB_CONFIG.get('use_ssh', False) and DB_CONFIG.get('ssh_host'):
                # SSH connection
                from sshtunnel import SSHTunnelForwarder
                
                self.tunnel = SSHTunnelForwarder(
                    (DB_CONFIG['ssh_host'], DB_CONFIG['ssh_port']),
                    ssh_username=DB_CONFIG['ssh_user'],
                    ssh_password=DB_CONFIG['ssh_pass'],
                    remote_bind_address=(DB_CONFIG['db_host'], DB_CONFIG['db_port']),
                    local_bind_address=('127.0.0.1', 0)
                )
                
                self.tunnel.start()
                local_port = self.tunnel.local_bind_port
                
                conn_str = f"""
                    DRIVER={{ODBC Driver 17 for SQL Server}};
                    SERVER=127.0.0.1,{local_port};
                    DATABASE={DB_CONFIG['db_name']};
                    UID={DB_CONFIG['db_user']};
                    PWD={DB_CONFIG['db_pass']};
                    TrustServerCertificate=yes;
                    Connection Timeout=10;
                """
                
            else:
                # Direct connection
                server = DB_CONFIG.get('direct_server') or DB_CONFIG.get('db_host')
                database = DB_CONFIG.get('direct_database') or DB_CONFIG.get('db_name')
                username = DB_CONFIG.get('direct_user') or DB_CONFIG.get('db_user')
                password = DB_CONFIG.get('direct_pass') or DB_CONFIG.get('db_pass')
                port = DB_CONFIG.get('db_port', 1433)
                
                if not server:
                    raise Exception("No database server configured")
                
                conn_str = f"""
                    DRIVER={{ODBC Driver 17 for SQL Server}};
                    SERVER={server},{port};
                    DATABASE={database};
                    UID={username};
                    PWD={password};
                    TrustServerCertificate=yes;
                    Connection Timeout=15;
                """
            
            # Connect
            self.connection = pyodbc.connect(conn_str)
            self.is_connected = True
            self.connection_message = "✅ Connected to real database"
            
            # Test connection with a simple query
            test_df = self._execute_real_query("SELECT GETDATE() AS server_time")
            if test_df is not None:
                print(f"Real database test successful: {test_df.iloc[0]['server_time']}")
            
        except ImportError as e:
            raise Exception(f"Database driver not installed: {e}")
        except Exception as e:
            raise Exception(f"Database connection failed: {str(e)}")
    
    def _execute_real_query(self, query):
        """Execute query on real database"""
        if not self.connection:
            return None
        
        try:
            cursor = self.connection.cursor()
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
            print(f"Real query failed: {e}")
            return None
    
    def _generate_demo_data(self, query):
        """Generate realistic demo data based on query"""
        query_lower = query.lower()
        today = date.today()
        
        # TODAY'S STATS
        if "today" in query_lower or "getdate()" in query_lower:
            return pd.DataFrame([{
                'total_transactions': 187,
                'total_bv': 1425000,
                'total_tdp': 108750000,
                'unique_members': 94,
                'unique_stockists': 14
            }])
        
        # YESTERDAY'S STATS
        elif "yesterday" in query_lower:
            return pd.DataFrame([{
                'total_transactions': 165,
                'total_bv': 1280000,
                'total_tdp': 97500000,
                'unique_members': 88
            }])
        
        # MONTHLY STATS
        elif "month" in query_lower:
            return pd.DataFrame([{
                'total_transactions': 3421,
                'total_bv': 29875000,
                'total_tdp': 2240000000,
                'unique_members': 467,
                'unique_stockists': 52
            }])
        
        # LAST 30 DAYS TREND
        elif "30 days" in query_lower or "dateadd" in query_lower:
            dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') 
                    for i in range(29, -1, -1)]
            data = []
            base_bv = 1200000
            
            for i, d in enumerate(dates):
                # Realistic trend with some randomness
                day_factor = 1 + (i * 0.01)  # Slight upward trend
                random_factor = np.random.uniform(0.9, 1.1)
                
                data.append({
                    'trx_date': datetime.strptime(d, '%Y-%m-%d').date(),
                    'total_transactions': int(150 * day_factor * random_factor),
                    'total_bv': int(base_bv * day_factor * random_factor),
                    'unique_members': int(85 + (i * 0.5))
                })
            return pd.DataFrame(data)
        
        # TOP STOCKISTS
        elif "top 10" in query_lower or "stockist" in query_lower:
            stockists = ['STK001', 'STK005', 'STK012', 'STK008', 'STK003', 
                        'STK015', 'STK007', 'STK009', 'STK011', 'STK004']
            data = []
            
            for i, code in enumerate(stockists):
                data.append({
                    'stockist_code': code,
                    'total_bv': 650000 - (i * 55000),
                    'transaction_count': 52 - (i * 4),
                    'unique_members': 28 - (i * 2)
                })
            return pd.DataFrame(data)
        
        # SERVER TIME
        elif "server_time" in query_lower:
            return pd.DataFrame([{'server_time': datetime.now()}])
        
        # DEFAULT
        return pd.DataFrame()
    
    def query(self, query, params=None):
        """Smart query - uses real DB if available, otherwise demo data"""
        if self.mode == "real" and self.is_connected and self.connection:
            try:
                result = self._execute_real_query(query)
                if result is not None:
                    return result
                # If real query fails, fall through to demo
            except Exception as e:
                print(f"Real query failed, falling back to demo: {e}")
                self.mode = "demo"  # Switch to demo mode
        
        # Use demo data
        return self._generate_demo_data(query)
    
    def get_mode(self):
        return self.mode
    
    def get_status(self):
        if self.mode == "real":
            return "✅ Connected to live database"
        else:
            return f"📊 Using demo data ({self.connection_message})"
    
    def reconnect(self):
        """Try to reconnect to real database"""
        try:
            self._try_real_connection()
            self.mode = "real"
            return True, "✅ Reconnected to real database"
        except Exception as e:
            self.mode = "demo"
            return False, f"❌ Still using demo data: {str(e)[:80]}"

# Initialize database
if 'db' not in st.session_state:
    st.session_state.db = SmartDatabaseConnector()
    st.session_state.db.initialize()

db = st.session_state.db

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
            
            # DEMO LICENSE (always works)
            DEMO_KEY = "ZGVtb0BrbGluay5jb218MjAyNTEyMzEyMzU5NTl8YjVjNmQ0NQ=="
            
            if license_key == DEMO_KEY:
                return True, {
                    "email": "demo@klink.com",
                    "expiry": datetime.now() + timedelta(days=365),
                    "days_left": 365,
                    "license_key": license_key,
                    "environment": ENVIRONMENT
                }
            
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

# ==================== DATA FUNCTIONS (CACHED) ====================
@st.cache_data(ttl=300)
def get_today_stats():
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
    return db.query(q)

@st.cache_data(ttl=300)
def get_yesterday_stats():
    q = """
    SELECT 
        ISNULL(COUNT(*), 0) AS total_transactions,
        ISNULL(SUM(tbv), 0) AS total_bv,
        ISNULL(SUM(tdp), 0) AS total_tdp,
        ISNULL(COUNT(DISTINCT dfno), 0) AS unique_members
    FROM klink_mlm2010.dbo.newtrh
    WHERE CAST(createdt AS DATE) = CAST(DATEADD(DAY, -1, GETDATE()) AS DATE)
    """
    return db.query(q)

@st.cache_data(ttl=600)
def get_monthly_stats():
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
    return db.query(q)

@st.cache_data(ttl=300)
def get_last_30days():
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
    return db.query(q)

@st.cache_data(ttl=300)
def get_top_stockists():
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
    return db.query(q)

# ==================== LOGIN PAGE ====================
def show_login():
    st.sidebar.empty()
    
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
    </style>
    
    <div class="login-header">
        <h1>🔐 {APP_NAME}</h1>
        <p>v{APP_VERSION} | Professional Analytics Platform</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Show database status
    status = db.get_status()
    if "demo" in status.lower():
        st.warning(status)
    else:
        st.success(status)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.info("**Quick Start:** Use demo license key")
        
        # Demo license key
        demo_key = "ZGVtb0BrbGluay5jb218MjAyNTEyMzEyMzU5NTl8YjVjNmQ0NQ=="
        
        st.code(demo_key, language="text")
        
        if st.button("🚀 **USE DEMO LICENSE**", type="primary", use_container_width=True):
            with st.spinner("Logging in..."):
                validator = LicenseValidator()
                valid, result = validator.validate(demo_key)
                
                if valid:
                    st.session_state.authenticated = True
                    st.session_state.user_info = result
                    st.success(f"✅ Welcome {result['email']}!")
                    time.sleep(1)
                    st.rerun()
        
        st.markdown("---")
        
        # Custom license
        st.markdown("**Or enter custom license:**")
        license_input = st.text_area("License Key:", height=100)
        
        if st.button("🔑 **VALIDATE CUSTOM LICENSE**", use_container_width=True):
            if license_input:
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
            else:
                st.warning("Please enter a license key")
        
        st.markdown("---")
        st.caption(f"© 2024 {APP_NAME}")

# ==================== MAIN DASHBOARD ====================
def show_main_dashboard():
    st.title("📊 K-Link Dashboard")
    
    # Show data source
    if db.get_mode() == "real":
        st.success("✅ Live data from database")
    else:
        st.warning("📊 Demo data (database not connected)")
    
    st.caption(f"Real-time analytics • {datetime.now().strftime('%d %B %Y %H:%M')}")
    
    # Refresh button
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    
    # Load data
    with st.spinner("🔄 Loading data..."):
        today_df = get_today_stats()
        yesterday_df = get_yesterday_stats()
        monthly_df = get_monthly_stats()
        trend_df = get_last_30days()
        top_stockists = get_top_stockists()
    
    # KPI Cards
    st.subheader("📈 Today's Performance")
    
    if not today_df.empty:
        today_stats = today_df.iloc[0].to_dict()
        
        if not yesterday_df.empty:
            yesterday_stats = yesterday_df.iloc[0].to_dict()
        else:
            yesterday_stats = {'total_transactions': 0, 'total_bv': 0, 'total_tdp': 0, 'unique_members': 0}
        
        today_transactions = safe_float(today_stats.get('total_transactions', 0))
        yesterday_transactions = safe_float(yesterday_stats.get('total_transactions', 0))
        
        today_bv = safe_float(today_stats.get('total_bv', 0))
        yesterday_bv = safe_float(yesterday_stats.get('total_bv', 0))
        
        today_tdp = safe_float(today_stats.get('total_tdp', 0))
        yesterday_tdp = safe_float(yesterday_stats.get('total_tdp', 0))
        
        today_members = safe_float(today_stats.get('unique_members', 0))
        yesterday_members = safe_float(yesterday_stats.get('unique_members', 0))
        
        today_stockists = safe_float(today_stats.get('unique_stockists', 0))
        
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
    
    # Charts
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📈 Daily Trend")
        if not trend_df.empty:
            # Create chart
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
                title="Daily BV Trend",
                height=300,
                template="plotly_white"
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No trend data available")
    
    with col2:
        st.subheader("🏆 Top Stockists")
        if not top_stockists.empty:
            st.dataframe(top_stockists.head(5), use_container_width=True)
        else:
            st.info("No stockist data available")
    
    # Footer
    st.markdown("---")
    st.caption(f"Data source: {'Live Database' if db.get_mode() == 'real' else 'Demo Data'} • Last update: {datetime.now().strftime('%H:%M:%S')}")

# ==================== SETTINGS PAGE ====================
def show_settings():
    st.title("⚙️ Settings")
    
    user = st.session_state.user_info
    
    with st.expander("👤 Account Information"):
        st.write(f"**Email:** {user['email']}")
        st.write(f"**Environment:** {user.get('environment', 'N/A')}")
        
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
    
    with st.expander("🔧 Database Control"):
        current_mode = db.get_mode()
        st.write(f"**Current Mode:** {'📊 Demo Data' if current_mode == 'demo' else '✅ Live Database'}")
        st.write(f"**Status:** {db.get_status()}")
        
        if st.button("🔄 Reconnect to Real Database"):
            success, message = db.reconnect()
            if success:
                st.success(message)
                st.cache_data.clear()  # Clear cache to reload real data
            else:
                st.error(message)
            time.sleep(2)
            st.rerun()
        
        if st.button("🔄 Clear Cache"):
            st.cache_data.clear()
            st.success("Cache cleared!")
            time.sleep(1)
            st.rerun()
    
    with st.expander("📊 Configuration"):
        st.write("**Database Config:**")
        if DB_CONFIG.get('use_ssh'):
            st.write(f"- SSH: {DB_CONFIG.get('ssh_host')}:{DB_CONFIG.get('ssh_port')}")
            st.write(f"- DB: {DB_CONFIG.get('db_host')}:{DB_CONFIG.get('db_port')}")
        else:
            server = DB_CONFIG.get('direct_server') or DB_CONFIG.get('db_host')
            st.write(f"- Direct: {server}:{DB_CONFIG.get('db_port')}")

# ==================== AUTH CHECK ====================
def check_auth():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    return st.session_state.authenticated

# ==================== NAVIGATION ====================
def show_dashboard():
    user = st.session_state.user_info
    
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
        if db.get_mode() == "real":
            st.success("✅ Live DB")
        else:
            st.warning("📊 Demo")
        
        st.markdown("---")
        
        # Navigation
        pages = ["🏠 Dashboard", "⚙️ Settings"]
        
        if 'current_page' not in st.session_state:
            st.session_state.current_page = pages[0]
        
        for page in pages:
            if st.button(page, use_container_width=True,
                        type="primary" if st.session_state.current_page == page else "secondary"):
                st.session_state.current_page = page
                st.rerun()
        
        st.markdown("---")
        
        if st.button("🚪 **Logout**", use_container_width=True):
            for key in ['authenticated', 'user_info']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        
        st.caption(f"v{APP_VERSION} • {ENVIRONMENT}")
    
    if st.session_state.current_page == "🏠 Dashboard":
        show_main_dashboard()
    elif st.session_state.current_page == "⚙️ Settings":
        show_settings()

# ==================== MAIN APP ====================
def main():
    if not check_auth():
        show_login()
    else:
        show_dashboard()

if __name__ == "__main__":
    main()