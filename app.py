import streamlit as st
import hashlib
import base64
from datetime import datetime, timedelta
import time
import re

# ==================== CONFIGURATION ====================
APP_NAME = "Login"
APP_VERSION = "1.0.0"

# ✅ COMBINED: Bisa local dan online
if hasattr(st, 'secrets') and 'LICENSE_SECRET' in st.secrets:
    # Running di Streamlit Cloud
    SECRET_KEY = st.secrets["LICENSE_SECRET"]
    ENVIRONMENT = "PRODUCTION"
else:
    # Running di local
    SECRET_KEY = "klink2024secure"  # Default untuk development
    ENVIRONMENT = "DEVELOPMENT"

print(f"Running in {ENVIRONMENT} mode")

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
                return False, "Invalid license key"
            
            # Add padding
            padding = 4 - (len(license_key) % 4)
            if padding != 4:
                license_key += '=' * padding
            
            # Decode
            try:
                decoded = base64.b64decode(license_key).decode('utf-8')
            except:
                return False, "Invalid license format"
            
            parts = decoded.split('|')
            
            if len(parts) != 3:
                return False, "Invalid license format"
            
            email, expiry_str, signature = parts
            
            # Basic email check
            if '@' not in email or '.' not in email:
                return False, "Invalid email format"
            
            # Verify signature
            data = f"{email}|{expiry_str}"
            expected = hashlib.md5(f"{data}{self.secret}".encode()).hexdigest()[:8]
            
            if signature != expected:
                return False, "License validation failed"
            
            # Check expiry
            try:
                if len(expiry_str) != 14:
                    return False, "Invalid expiry format"
                expiry = datetime.strptime(expiry_str, "%Y%m%d%H%M%S")
            except:
                return False, "Invalid expiry date"
            
            if datetime.now() > expiry:
                return False, f"License expired on {expiry.strftime('%d %B %Y')}"
            
            days_left = (expiry - datetime.now()).days
            
            return True, {
                "email": email,
                "expiry": expiry,
                "days_left": days_left,
                "license_key": license_key,
                "environment": ENVIRONMENT
            }
            
        except Exception as e:
            return False, f"Error: {str(e)}"

# ==================== GENERATE DEMO KEY ====================
def generate_demo_key():
    """Generate demo key for testing"""
    email = "demo@klink.com"
    expiry = datetime.now() + timedelta(days=365)
    expiry_str = expiry.strftime("%Y%m%d%H%M%S")
    
    data = f"{email}|{expiry_str}"
    signature = hashlib.md5(f"{data}{SECRET_KEY}".encode()).hexdigest()[:8]
    
    license_data = f"{data}|{signature}"
    return base64.b64encode(license_data.encode()).decode()

# ==================== AUTH CHECK ====================
def check_auth():
    """Check authentication status"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        return False
    
    if not st.session_state.authenticated:
        return False
    
    if 'user_info' not in st.session_state:
        st.session_state.authenticated = False
        return False
    
    # Check expiry
    user_info = st.session_state.user_info
    if datetime.now() > user_info['expiry']:
        st.session_state.authenticated = False
        st.session_state.expired_msg = "Your license has expired"
        return False
    
    return True

# ==================== LOGIN PAGE ====================
def show_login():
    """Show login page"""
    st.set_page_config(
        page_title=f"Login - {APP_NAME}",
        page_icon="🔐",
        layout="centered"
    )
    
    # CSS
    st.markdown("""
    <style>
    .main { padding: 20px; }
    .login-box {
        background: white;
        padding: 30px;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    .env-badge {
        position: absolute;
        top: 10px;
        right: 10px;
        background: #4CAF50;
        color: white;
        padding: 5px 10px;
        border-radius: 5px;
        font-size: 12px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Environment badge
    st.markdown(f'<div class="env-badge">{ENVIRONMENT}</div>', unsafe_allow_html=True)
    
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.title(f"🔐 {APP_NAME}")
            st.caption(f"v{APP_VERSION} | {ENVIRONMENT}")
            
            # Demo key
            #if 'demo_key' not in st.session_state:
             #   st.session_state.demo_key = generate_demo_key()
            
            #st.info("**Quick Start:** Click the button below for instant access")
            
            #if st.button("🚀 **TRY DEMO**", type="primary", use_container_width=True):
             #   validator = LicenseValidator()
              #  valid, result = validator.validate(st.session_state.demo_key)
                
               # if valid:
                #    st.session_state.authenticated = True
                 #   st.session_state.user_info = result
                  #  st.success("Login successful!")
                   # time.sleep(1)
                    #st.rerun()
                #else:
                 #   st.error(result)
            
           # st.markdown("---")
            
            # Custom license
            #st.markdown("**Or use your own license:**")
            
            tab1, tab2 = st.tabs(["📝 Paste Key", "📤 Upload File"])
            
            license_input = ""
            
            with tab1:
                license_input = st.text_area("License Key:", height=100)
            
            with tab2:
                uploaded = st.file_uploader("Choose file", type=['key', 'txt'])
                if uploaded:
                    try:
                        content = uploaded.read().decode('utf-8')
                        matches = re.findall(r'[A-Za-z0-9+/=]{20,}', content)
                        license_input = matches[0] if matches else content.strip()
                    except:
                        st.error("Failed to read file")
            
            if license_input and st.button("🔑 **VALIDATE**", use_container_width=True):
                with st.spinner("Validating..."):
                    validator = LicenseValidator()
                    valid, result = validator.validate(license_input)
                    
                    if valid:
                        st.session_state.authenticated = True
                        st.session_state.user_info = result
                        st.success(f"Welcome {result['email']}!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(result)
            
            # Footer
            st.markdown("---")
            st.caption(f"© 2024 {APP_NAME}")

# ==================== DASHBOARD ====================
def show_dashboard():
    """Show main dashboard"""
    st.set_page_config(
        page_title=APP_NAME,
        page_icon="📊",
        layout="wide"
    )
    
    user = st.session_state.user_info
    
    # Sidebar
    with st.sidebar:
        st.markdown(f"### 👤 {user['email'].split('@')[0]}")
        st.markdown(f"**Environment:** {user.get('environment', 'N/A')}")
        
        days = user['days_left']
        if days > 30:
            st.success(f"✅ {days} days")
        elif days > 7:
            st.warning(f"⚠️ {days} days")
        else:
            st.error(f"⏰ {days} days")
        
        st.caption(f"Expires: {user['expiry'].strftime('%d %b %Y')}")
        
        if st.button("🚪 **Logout**", use_container_width=True):
            for key in ['authenticated', 'user_info']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        
        st.markdown("---")
        
        # Navigation
        pages = ["🏠 Dashboard", "📈 Analytics", "📊 Reports", "⚙️ Settings"]
        
        if 'page' not in st.session_state:
            st.session_state.page = pages[0]
        
        for page in pages:
            if st.button(page, use_container_width=True, 
                        type="primary" if st.session_state.page == page else "secondary"):
                st.session_state.page = page
                st.rerun()
    
    # Main content
    if st.session_state.page == "🏠 Dashboard":
        st.title(f"📊 {APP_NAME}")
        st.markdown(f"**Welcome, {user['email'].split('@')[0]}!**")
        
        # Metrics
        cols = st.columns(4)
        metrics = [
            ("Revenue", "Rp 1.2B", "+12%"),
            ("Users", "1,425", "+8%"),
            ("Growth", "23%", "+3%"),
            ("Sessions", "24.8K", "+16%")
        ]
        
        for col, (label, value, delta) in zip(cols, metrics):
            col.metric(label, value, delta)
        
        # Chart
        st.subheader("Performance Overview")
        st.line_chart({
            'Jan': 120, 'Feb': 150, 'Mar': 180,
            'Apr': 210, 'May': 240, 'Jun': 270
        })
        
    elif st.session_state.page == "📈 Analytics":
        st.title("📈 Analytics")
        st.write("Advanced analytics...")
        
    elif st.session_state.page == "📊 Reports":
        st.title("📊 Reports")
        st.write("Report generation...")
        
    elif st.session_state.page == "⚙️ Settings":
        st.title("⚙️ Settings")
        
        with st.expander("Account Information"):
            st.json({
                "email": user["email"],
                "expiry": user["expiry"].strftime("%Y-%m-%d"),
                "days_remaining": user["days_left"],
                "environment": user.get("environment", "N/A")
            })

# ==================== MAIN ====================
def main():
    """Main application flow"""
    
    # Initialize
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    # Check auth
    if not check_auth():
        show_login()
    else:
        show_dashboard()

if __name__ == "__main__":
    main()