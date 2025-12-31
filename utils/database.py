import pandas as pd
import pyodbc
from sshtunnel import SSHTunnelForwarder
import streamlit as st
from datetime import datetime, timedelta
import numpy as np
import time

class SmartDatabase:
    def __init__(self):
        self.tunnel = None
        self.conn = None
        self.use_demo = False
        self.connection_message = ""
        self.last_query_time = 0
        self.query_cache = {}
        
        try:
            # Load configuration from secrets
            self.use_ssh = st.secrets.get("USE_SSH", True)
            
            if self.use_ssh:
                # SSH Configuration
                self.ssh_host = st.secrets["SSH_HOST"]
                self.ssh_user = st.secrets["SSH_USER"]
                self.ssh_pass = st.secrets["SSH_PASS"]
                self.ssh_port = int(st.secrets.get("SSH_PORT", 22))
                
                # Database Configuration (behind SSH)
                self.db_host = st.secrets["DB_HOST"]
                self.db_name = st.secrets["DB_NAME"]
                self.db_user = st.secrets["DB_USER"]
                self.db_pass = st.secrets["DB_PASS"]
                self.db_port = int(st.secrets.get("DB_PORT", 1433))
            else:
                # Direct Connection
                self.db_host = st.secrets.get("DIRECT_SERVER", st.secrets["DB_HOST"])
                self.db_name = st.secrets["DB_NAME"]
                self.db_user = st.secrets["DB_USER"]
                self.db_pass = st.secrets["DB_PASS"]
                self.db_port = int(st.secrets.get("DB_PORT", 1433))
            
            self.connection_message = "✅ Database config loaded"
            
        except Exception as e:
            self.use_demo = True
            self.connection_message = f"⚠️ Using demo data: {str(e)[:80]}"
    
    def connect(self):
        """Establish database connection with timeout"""
        if self.use_demo:
            return None
            
        try:
            current_time = time.time()
            # Rate limiting: max 1 connection attempt per 5 seconds
            if current_time - self.last_query_time < 5:
                return None
                
            self.last_query_time = current_time
            
            if self.use_ssh:
                # Create SSH tunnel with timeout
                self.tunnel = SSHTunnelForwarder(
                    (self.ssh_host, self.ssh_port),
                    ssh_username=self.ssh_user,
                    ssh_password=self.ssh_pass,
                    remote_bind_address=(self.db_host, self.db_port),
                    local_bind_address=('127.0.0.1', 0),
                    set_keepalive=30
                )
                
                self.tunnel.start()
                local_port = self.tunnel.local_bind_port
                
                conn_str = f"""
                    DRIVER={{ODBC Driver 17 for SQL Server}};
                    SERVER=127.0.0.1,{local_port};
                    DATABASE={self.db_name};
                    UID={self.db_user};
                    PWD={self.db_pass};
                    TrustServerCertificate=yes;
                    Connection Timeout=15;
                """
            else:
                conn_str = f"""
                    DRIVER={{ODBC Driver 17 for SQL Server}};
                    SERVER={self.db_host},{self.db_port};
                    DATABASE={self.db_name};
                    UID={self.db_user};
                    PWD={self.db_pass};
                    TrustServerCertificate=yes;
                    Connection Timeout=15;
                """
            
            self.conn = pyodbc.connect(conn_str)
            self.connection_message = "✅ Connected to database"
            return self.conn
            
        except Exception as e:
            self.use_demo = True
            self.connection_message = f"⚠️ Using demo data: {str(e)[:80]}"
            return None
    
    def query(self, sql, cache_ttl=300):
        """Execute SQL query with caching"""
        # Check cache first
        cache_key = hash(sql)
        current_time = time.time()
        
        if cache_key in self.query_cache:
            cached_data, timestamp = self.query_cache[cache_key]
            if current_time - timestamp < cache_ttl:
                return cached_data.copy()  # Return copy to prevent mutation
        
        # If using demo mode, generate realistic data
        if self.use_demo:
            result = self._generate_demo_data(sql)
            self.query_cache[cache_key] = (result.copy(), current_time)
            return result
        
        # Try real database
        try:
            if not self.conn:
                self.connect()
                if not self.conn:
                    result = self._generate_demo_data(sql)
                    self.query_cache[cache_key] = (result.copy(), current_time)
                    return result
            
            # Use simple query for better performance
            df = pd.read_sql(sql, self.conn)
            
            # Cache the result
            self.query_cache[cache_key] = (df.copy(), current_time)
            
            # Clean old cache entries
            self._clean_cache()
            
            return df
            
        except Exception as e:
            print(f"Query failed: {e}")
            self.use_demo = True
            result = self._generate_demo_data(sql)
            self.query_cache[cache_key] = (result.copy(), current_time)
            return result
    
    def _clean_cache(self):
        """Clean old cache entries"""
        current_time = time.time()
        expired_keys = []
        
        for key, (_, timestamp) in self.query_cache.items():
            if current_time - timestamp > 3600:  # 1 hour max cache
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.query_cache[key]
    
    def _generate_demo_data(self, sql):
        """Generate realistic demo data"""
        sql_lower = sql.lower()
        today = datetime.now().date()
        
        # TODAY'S STATS
        if "today" in sql_lower and "newtrh" in sql_lower:
            return pd.DataFrame([{
                'total_transactions': 187,
                'total_bv': 1425000,
                'total_tdp': 108750000,
                'unique_members': 94,
                'unique_stockists': 14
            }])
        
        # YESTERDAY'S STATS
        elif "yesterday" in sql_lower:
            return pd.DataFrame([{
                'total_transactions': 165,
                'total_bv': 1280000,
                'total_tdp': 97500000,
                'unique_members': 88
            }])
        
        # MONTHLY STATS
        elif "month" in sql_lower and "newtrh" in sql_lower:
            return pd.DataFrame([{
                'total_transactions': 3421,
                'total_bv': 29875000,
                'total_tdp': 2240000000,
                'unique_members': 467,
                'unique_stockists': 52
            }])
        
        # LAST 30 DAYS TREND
        elif "30 days" in sql_lower or "dateadd" in sql_lower:
            dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') 
                    for i in range(29, -1, -1)]
            data = []
            
            base_bv = 1000000
            for i, d in enumerate(dates):
                trend = 1 + (i * 0.02)  # Slight upward trend
                data.append({
                    'trx_date': datetime.strptime(d, '%Y-%m-%d').date(),
                    'total_transactions': int(120 * trend),
                    'total_bv': int(base_bv * trend),
                    'unique_members': int(80 * trend)
                })
            return pd.DataFrame(data)
        
        # TOP STOCKISTS
        elif "top 10" in sql_lower or "stockist" in sql_lower:
            data = []
            for i in range(1, 11):
                data.append({
                    'stockist_code': f'STK{str(i).zfill(3)}',
                    'total_bv': 650000 - (i * 55000),
                    'transaction_count': 52 - (i * 4),
                    'unique_members': 28 - (i * 2)
                })
            return pd.DataFrame(data)
        
        # MEMBER JOIN - NEW FEATURE
        elif "msmemb" in sql_lower or "jointdt" in sql_lower:
            if "today" in sql_lower:
                return pd.DataFrame([{
                    'total_join': 24,
                    'active_members': 187
                }])
            elif "month" in sql_lower:
                return pd.DataFrame([{
                    'total_join': 342,
                    'active_members': 2450
                }])
            else:
                # Daily join trend for last 7 days
                dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') 
                        for i in range(6, -1, -1)]
                data = []
                for i, d in enumerate(dates):
                    data.append({
                        'join_date': datetime.strptime(d, '%Y-%m-%d').date(),
                        'daily_join': 15 + i * 2,
                        'cumulative_join': 100 + i * 25
                    })
                return pd.DataFrame(data)
        
        # SERVER TIME
        elif "server_time" in sql_lower:
            return pd.DataFrame([{'server_time': datetime.now()}])
        
        # DEFAULT
        return pd.DataFrame()
    
    def get_status(self):
        return self.connection_message
    
    def is_demo(self):
        return self.use_demo

# Global instance
db = SmartDatabase()