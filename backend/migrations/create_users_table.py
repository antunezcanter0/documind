#!/usr/bin/env python3
# migrations/create_users_table.py
"""
Migration script to create users and refresh_tokens tables
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from app.core.database import get_db

async def create_users_table():
    """Create users and refresh_tokens tables"""
    
    # SQL for users table
    create_users_sql = """
    CREATE TABLE IF NOT EXISTS users (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        username VARCHAR(50) UNIQUE NOT NULL,
        email VARCHAR(100) UNIQUE NOT NULL,
        hashed_password VARCHAR(255) NOT NULL,
        full_name VARCHAR(100),
        is_active BOOLEAN DEFAULT TRUE,
        is_superuser BOOLEAN DEFAULT FALSE,
        role VARCHAR(50) DEFAULT 'user',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE,
        last_login TIMESTAMP WITH TIME ZONE,
        login_count INTEGER DEFAULT 0,
        bio TEXT,
        avatar_url VARCHAR(255),
        preferences TEXT
    );
    
    CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
    CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
    CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
    """
    
    # SQL for refresh_tokens table
    create_refresh_tokens_sql = """
    CREATE TABLE IF NOT EXISTS refresh_tokens (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL,
        token_hash VARCHAR(255) UNIQUE NOT NULL,
        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
        is_revoked BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    
    CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);
    CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
    CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);
    """
    
    # SQL for trigger to update updated_at
    create_trigger_sql = """
    CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
    $$ language 'plpgsql';
    
    DROP TRIGGER IF EXISTS update_users_updated_at ON users;
    CREATE TRIGGER update_users_updated_at
        BEFORE UPDATE ON users
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """
    
    async for db in get_db():
        try:
            # Create users table
            await db.execute(text(create_users_sql))
            print("✅ Users table created successfully")
            
            # Create refresh_tokens table
            await db.execute(text(create_refresh_tokens_sql))
            print("✅ Refresh tokens table created successfully")
            
            # Create trigger for updated_at
            await db.execute(text(create_trigger_sql))
            print("✅ Updated_at trigger created successfully")
            
            # Create default admin user
            from app.core.security import get_password_hash
            admin_password_hash = get_password_hash("admin123")
            
            await db.execute(text("""
                INSERT INTO users (username, email, hashed_password, full_name, role, is_superuser)
                VALUES ('admin', 'admin@documind.com', :password_hash, 'System Administrator', 'admin', true)
                ON CONFLICT (username) DO NOTHING
            """), {"password_hash": admin_password_hash})
            
            print("✅ Default admin user created (username: admin, password: admin123)")
            
            await db.commit()
            print("🎉 Migration completed successfully!")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            await db.rollback()
            raise

if __name__ == "__main__":
    asyncio.run(create_users_table())
