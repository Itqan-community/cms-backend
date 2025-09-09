"""
Management command to verify database schema matches Django model definitions
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.apps import apps
from django.db import models
import sys


class Command(BaseCommand):
    help = 'Verify database schema matches Django model definitions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Automatically create migrations for mismatches'
        )
        parser.add_argument(
            '--app',
            type=str,
            help='Check specific app only'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🔍 Verifying Database Schema vs Model Definitions')
        )
        self.stdout.write('=' * 60)
        
        mismatches = []
        
        # Get all models
        if options['app']:
            models_to_check = apps.get_app_config(options['app']).get_models()
        else:
            models_to_check = apps.get_models()
        
        for model in models_to_check:
            app_label = model._meta.app_label
            model_name = model._meta.model_name
            table_name = model._meta.db_table
            
            self.stdout.write(f"\n📋 Checking {app_label}.{model_name} ({table_name})")
            
            # Check if table exists
            if not self.table_exists(table_name):
                self.stdout.write(
                    self.style.ERROR(f"❌ Table {table_name} does not exist!")
                )
                mismatches.append(f"Missing table: {table_name}")
                continue
            
            # Get expected fields from model
            expected_fields = {}
            for field in model._meta.fields:
                column_name = field.column
                field_type = self.get_django_field_type(field)
                expected_fields[column_name] = field_type
            
            # Get actual fields from database
            actual_fields = self.get_table_columns(table_name)
            
            # Compare fields
            field_mismatches = self.compare_fields(
                table_name, expected_fields, actual_fields
            )
            
            if field_mismatches:
                mismatches.extend(field_mismatches)
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"✅ {table_name} schema matches model")
                )
        
        # Summary
        self.stdout.write('\n' + '=' * 60)
        if mismatches:
            self.stdout.write(
                self.style.ERROR(f"❌ Found {len(mismatches)} schema mismatches:")
            )
            for mismatch in mismatches:
                self.stdout.write(f"  - {mismatch}")
            
            if options['fix']:
                self.stdout.write(
                    self.style.WARNING("\n🔧 Creating migrations to fix mismatches...")
                )
                from django.core.management import call_command
                call_command('makemigrations')
            else:
                self.stdout.write(
                    self.style.WARNING("\n💡 Run with --fix to create migrations automatically")
                )
            
            sys.exit(1)
        else:
            self.stdout.write(
                self.style.SUCCESS("✅ All schemas match model definitions!")
            )
    
    def table_exists(self, table_name):
        """Check if table exists in database"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, [table_name])
            return cursor.fetchone()[0]
    
    def get_table_columns(self, table_name):
        """Get actual columns from database table"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, [table_name])
            return {
                row[0]: {'type': row[1], 'nullable': row[2] == 'YES'}
                for row in cursor.fetchall()
            }
    
    def get_django_field_type(self, field):
        """Map Django field to database type"""
        if isinstance(field, models.AutoField):
            return 'serial'
        elif isinstance(field, models.ForeignKey):
            return 'integer'
        elif isinstance(field, models.CharField):
            return 'character varying'
        elif isinstance(field, models.TextField):
            return 'text'
        elif isinstance(field, models.BooleanField):
            return 'boolean'
        elif isinstance(field, models.DateTimeField):
            return 'timestamp with time zone'
        elif isinstance(field, models.DateField):
            return 'date'
        elif isinstance(field, models.IntegerField):
            return 'integer'
        elif isinstance(field, models.JSONField):
            return 'jsonb'
        else:
            return 'unknown'
    
    def compare_fields(self, table_name, expected_fields, actual_fields):
        """Compare expected vs actual fields"""
        mismatches = []
        
        # Check for missing fields
        for field_name, field_info in expected_fields.items():
            if field_name not in actual_fields:
                mismatches.append(
                    f"{table_name}: Missing column '{field_name}'"
                )
        
        # Check for extra fields (excluding Django internal fields)
        for field_name in actual_fields:
            if (field_name not in expected_fields and 
                not field_name.startswith('_') and
                field_name not in ['id']):  # Allow Django's auto id field
                self.stdout.write(
                    self.style.WARNING(f"⚠️  {table_name}: Extra column '{field_name}'")
                )
        
        return mismatches
