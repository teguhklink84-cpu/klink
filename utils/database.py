import pandas as pd
import pyodbc
from sshtunnel import SSHTunnelForwarder
import streamlit as st

class SSHDatabase:
    def __init__(self):
        # Load dari secrets
        self.ssh_host = st.secrets["SSH_HOST"]
        self.ssh_user = st.secrets["SSH_USER"]
        self.ssh_pass = st.secrets["SSH_PASS"]
        self.ssh_port = int(st.secrets.get("SSH_PORT", 22))
        
        self.db_host_local = st.secrets["DB_HOST_LOCAL"]
        self.db_name = st.secrets["DB_NAME"]
        self.db_user = st.secrets["DB_USER"]
        self.db_pass = st.secrets["DB_PASS"]
        self.db_port = int(st.secrets.get("DB_PORT", 1433))
        
        self.tunnel = None
        st.toast("Database config loaded", icon="✅")
    
    def connect(self):
        """Create SSH tunnel and connect to database"""
        try:
            # Create SSH tunnel
            self.tunnel = SSHTunnelForwarder(
                (self.ssh_host, self.ssh_port),
                ssh_username=self.ssh_user,
                ssh_password=self.ssh_pass,
                remote_bind_address=(self.db_host_local, self.db_port),
                local_bind_address=('127.0.0.1', 0)
            )
            
            self.tunnel.start()
            local_port = self.tunnel.local_bind_port
            
            # Connect to SQL Server
            conn_str = f"""
                Driver={{ODBC Driver 17 for SQL Server}};
                Server=127.0.0.1,{local_port};
                Database={self.db_name};
                UID={self.db_user};
                PWD={self.db_pass};
                TrustServerCertificate=yes;
            """
            
            return pyodbc.connect(conn_str)
            
        except Exception as e:
            st.error(f"Connection failed: {str(e)}")
            return None
    
    def query(self, sql):
        """Execute SQL query"""
        conn = None
        try:
            conn = self.connect()
            if conn:
                df = pd.read_sql(sql, conn)
                return df
        except Exception as e:
            st.error(f"Query error: {str(e)}")
            return None
        finally:
            if conn:
                conn.close()

# Global instance
db = SSHDatabase()