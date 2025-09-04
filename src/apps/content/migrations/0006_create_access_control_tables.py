# Generated manually for access control models
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0004_create_missing_asset_tables'),
    ]

    operations = [
        migrations.RunSQL(
            # Create asset_access_request table
            """
            DROP TABLE IF EXISTS asset_access_request CASCADE;
            
            CREATE TABLE asset_access_request (
                id SERIAL PRIMARY KEY,
                developer_user_id INTEGER NOT NULL,
                asset_id INTEGER NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                developer_access_reason TEXT NOT NULL,
                intended_use VARCHAR(20) NOT NULL,
                admin_response TEXT NOT NULL DEFAULT '',
                approved_at TIMESTAMP WITH TIME ZONE,
                approved_by_id INTEGER,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN NOT NULL DEFAULT true
            );
            
            ALTER TABLE asset_access_request 
                ADD CONSTRAINT asset_access_request_developer_user_id_fkey 
                FOREIGN KEY (developer_user_id) REFERENCES accounts_user(id) ON DELETE CASCADE;
            
            ALTER TABLE asset_access_request 
                ADD CONSTRAINT asset_access_request_asset_id_fkey 
                FOREIGN KEY (asset_id) REFERENCES asset(id) ON DELETE CASCADE;
                
            ALTER TABLE asset_access_request 
                ADD CONSTRAINT asset_access_request_approved_by_id_fkey 
                FOREIGN KEY (approved_by_id) REFERENCES accounts_user(id) ON DELETE SET NULL;
                
            ALTER TABLE asset_access_request 
                ADD CONSTRAINT asset_access_request_developer_user_asset_unique 
                UNIQUE (developer_user_id, asset_id);
            
            CREATE INDEX asset_access_request_developer_user_id_idx 
                ON asset_access_request (developer_user_id);
            CREATE INDEX asset_access_request_asset_id_idx 
                ON asset_access_request (asset_id);
            CREATE INDEX asset_access_request_status_idx 
                ON asset_access_request (status);
            CREATE INDEX asset_access_request_created_at_idx 
                ON asset_access_request (created_at);
            """,
            # Reverse migration
            "DROP TABLE IF EXISTS asset_access_request CASCADE;"
        ),
        
        migrations.RunSQL(
            # Create asset_access table
            """
            DROP TABLE IF EXISTS asset_access CASCADE;
            
            CREATE TABLE asset_access (
                id SERIAL PRIMARY KEY,
                asset_access_request_id INTEGER NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                asset_id INTEGER NOT NULL,
                effective_license_id INTEGER NOT NULL,
                granted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP WITH TIME ZONE,
                download_url TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN NOT NULL DEFAULT true
            );
            
            ALTER TABLE asset_access 
                ADD CONSTRAINT asset_access_asset_access_request_id_fkey 
                FOREIGN KEY (asset_access_request_id) REFERENCES asset_access_request(id) ON DELETE CASCADE;
                
            ALTER TABLE asset_access 
                ADD CONSTRAINT asset_access_user_id_fkey 
                FOREIGN KEY (user_id) REFERENCES accounts_user(id) ON DELETE CASCADE;
                
            ALTER TABLE asset_access 
                ADD CONSTRAINT asset_access_asset_id_fkey 
                FOREIGN KEY (asset_id) REFERENCES asset(id) ON DELETE CASCADE;
                
            ALTER TABLE asset_access 
                ADD CONSTRAINT asset_access_effective_license_id_fkey 
                FOREIGN KEY (effective_license_id) REFERENCES license(id) ON DELETE RESTRICT;
                
            ALTER TABLE asset_access 
                ADD CONSTRAINT asset_access_user_asset_unique 
                UNIQUE (user_id, asset_id);
            
            CREATE INDEX asset_access_user_id_idx 
                ON asset_access (user_id);
            CREATE INDEX asset_access_asset_id_idx 
                ON asset_access (asset_id);
            CREATE INDEX asset_access_granted_at_idx 
                ON asset_access (granted_at);
            """,
            # Reverse migration
            "DROP TABLE IF EXISTS asset_access CASCADE;"
        ),

        migrations.RunSQL(
            # Create usage_event table
            """
            DROP TABLE IF EXISTS usage_event CASCADE;
            
            CREATE TABLE usage_event (
                id SERIAL PRIMARY KEY,
                developer_user_id INTEGER NOT NULL,
                usage_kind VARCHAR(20) NOT NULL,
                subject_kind VARCHAR(20) NOT NULL,
                resource_id INTEGER,
                asset_id INTEGER,
                metadata JSONB NOT NULL DEFAULT '{}',
                ip_address INET,
                user_agent TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN NOT NULL DEFAULT true
            );
            
            ALTER TABLE usage_event 
                ADD CONSTRAINT usage_event_developer_user_id_fkey 
                FOREIGN KEY (developer_user_id) REFERENCES accounts_user(id) ON DELETE CASCADE;
            
            CREATE INDEX usage_event_developer_user_id_idx 
                ON usage_event (developer_user_id);
            CREATE INDEX usage_event_usage_kind_idx 
                ON usage_event (usage_kind);
            CREATE INDEX usage_event_subject_kind_idx 
                ON usage_event (subject_kind);
            CREATE INDEX usage_event_created_at_idx 
                ON usage_event (created_at);
            CREATE INDEX usage_event_resource_id_idx 
                ON usage_event (resource_id);
            CREATE INDEX usage_event_asset_id_idx 
                ON usage_event (asset_id);
            """,
            # Reverse migration
            "DROP TABLE IF EXISTS usage_event CASCADE;"
        ),

        migrations.RunSQL(
            # Create distribution table
            """
            DROP TABLE IF EXISTS distribution CASCADE;
            
            CREATE TABLE distribution (
                id SERIAL PRIMARY KEY,
                resource_id INTEGER NOT NULL,
                format_type VARCHAR(20) NOT NULL,
                endpoint_url TEXT NOT NULL,
                version VARCHAR(50) NOT NULL,
                access_config JSONB NOT NULL DEFAULT '{}',
                metadata JSONB NOT NULL DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN NOT NULL DEFAULT true
            );
            
            ALTER TABLE distribution 
                ADD CONSTRAINT distribution_resource_id_fkey 
                FOREIGN KEY (resource_id) REFERENCES resource(id) ON DELETE CASCADE;
                
            ALTER TABLE distribution 
                ADD CONSTRAINT distribution_resource_format_version_unique 
                UNIQUE (resource_id, format_type, version);
            
            CREATE INDEX distribution_resource_id_idx 
                ON distribution (resource_id);
            CREATE INDEX distribution_format_type_idx 
                ON distribution (format_type);
            CREATE INDEX distribution_created_at_idx 
                ON distribution (created_at);
            """,
            # Reverse migration
            "DROP TABLE IF EXISTS distribution CASCADE;"
        ),
    ]
