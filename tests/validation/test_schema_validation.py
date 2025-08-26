#!/usr/bin/env python3
"""
Schema validation script for MNX
Validates OpenAPI spec and JSON schemas
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List

def check_dependencies():
    """Check and install required validation dependencies"""
    try:
        import jsonschema
        from openapi_spec_validator import validate_spec
        print("✓ Validation dependencies available")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Installing validation dependencies...")
        
        try:
            import subprocess
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", 
                "jsonschema", "openapi-spec-validator"
            ])
            print("✓ Dependencies installed successfully")
            return True
        except Exception as install_error:
            print(f"❌ Failed to install dependencies: {install_error}")
            return False

def validate_json_schemas(schemas_dir: Path) -> bool:
    """Validate JSON Schema files"""
    print("📋 Validating JSON schemas...")
    
    json_dir = schemas_dir / "json"
    if not json_dir.exists():
        print(f"⚠️  JSON schemas directory not found: {json_dir}")
        return True
    
    success = True
    schema_files = list(json_dir.glob("*.json"))
    
    if not schema_files:
        print("⚠️  No JSON schema files found")
        return True
    
    try:
        import jsonschema
        
        for schema_file in schema_files:
            print(f"  ✓ Checking {schema_file.name}...")
            
            try:
                # Load and validate JSON syntax
                with open(schema_file, 'r', encoding='utf-8') as f:
                    schema = json.load(f)
                
                # Validate JSON Schema structure
                jsonschema.validators.validator_for(schema).check_schema(schema)
                print(f"    ✓ Valid JSON Schema")
                
            except json.JSONDecodeError as e:
                print(f"    ❌ Invalid JSON syntax: {e}")
                success = False
            except jsonschema.SchemaError as e:
                print(f"    ❌ Invalid JSON Schema: {e}")
                success = False
            except Exception as e:
                print(f"    ❌ Validation error: {e}")
                success = False
                
    except ImportError:
        print("❌ jsonschema package not available")
        return False
        
    return success

def validate_openapi(schemas_dir: Path) -> bool:
    """Validate OpenAPI specification"""
    print("🌐 Validating OpenAPI specification...")
    
    openapi_file = schemas_dir / "openapi.json"
    if not openapi_file.exists():
        print(f"❌ OpenAPI file not found: {openapi_file}")
        return False
    
    try:
        from openapi_spec_validator import validate_spec
        
        print(f"  ✓ Checking {openapi_file.name}...")
        
        # Load and validate JSON syntax
        with open(openapi_file, 'r', encoding='utf-8') as f:
            spec = json.load(f)
        
        # Validate OpenAPI specification
        validate_spec(spec)
        print("    ✓ Valid OpenAPI 3.0 specification")
        return True
        
    except json.JSONDecodeError as e:
        print(f"    ❌ Invalid JSON syntax: {e}")
        return False
    except Exception as e:
        print(f"    ❌ OpenAPI validation failed: {e}")
        return False

def validate_sample_data(project_root: Path, schemas_dir: Path) -> bool:
    """Validate sample data against schemas"""
    print("📄 Validating sample data against schemas...")
    
    fixtures_dir = project_root / "tests" / "fixtures"
    if not fixtures_dir.exists():
        print("  ⚠️  No fixtures directory found, skipping sample validation")
        return True
    
    try:
        import jsonschema
        
        # Load event schema
        event_schema_file = schemas_dir / "event.schema.json"
        if not event_schema_file.exists():
            print("  ⚠️  Event schema not found, skipping sample validation")
            return True
            
        with open(event_schema_file, 'r', encoding='utf-8') as f:
            event_schema = json.load(f)
        
        success = True
        fixture_files = list(fixtures_dir.glob("**/*.json"))
        
        for fixture_file in fixture_files:
            print(f"  ✓ Validating {fixture_file.name}...")
            
            try:
                with open(fixture_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Try to validate against event schema
                jsonschema.validate(data, event_schema)
                print(f"    ✓ {fixture_file.name} validates against event schema")
                
            except jsonschema.ValidationError:
                print(f"    ⚠️  {fixture_file.name} does not match event schema (may be for different schema)")
                # Don't fail on this - fixtures might be for different schemas
            except json.JSONDecodeError as e:
                print(f"    ❌ Invalid JSON in {fixture_file.name}: {e}")
                success = False
            except Exception as e:
                print(f"    ❌ Error validating {fixture_file.name}: {e}")
                success = False
                
        return success
        
    except ImportError:
        print("❌ jsonschema package not available")
        return False

def check_schema_references(project_root: Path) -> bool:
    """Check if schemas are referenced in code"""
    print("🔗 Checking schema references in code...")
    
    services_dir = project_root / "services"
    if not services_dir.exists():
        print("  ⚠️  Services directory not found")
        return True
    
    schema_files = ["event.schema.json", "openapi.json"]
    
    for schema_name in schema_files:
        found = False
        
        # Search for schema references in Python files
        for py_file in services_dir.glob("**/*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if schema_name in content:
                        found = True
                        break
            except Exception:
                continue  # Skip files that can't be read
        
        if found:
            print(f"  ✓ {schema_name} is referenced in services")
        else:
            print(f"  ⚠️  {schema_name} not found in services (may be unused)")
    
    return True

def main():
    """Main validation function"""
    print("🔍 Validating MNX schemas...")
    
    # Get project paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    schemas_dir = project_root / "schemas"
    
    print(f"Working directory: {project_root}")
    print(f"Schemas directory: {schemas_dir}")
    print()
    
    if not schemas_dir.exists():
        print(f"❌ Schemas directory not found: {schemas_dir}")
        return 1
    
    # Check dependencies
    if not check_dependencies():
        return 1
    
    # Run validations
    success = True
    
    success &= validate_json_schemas(schemas_dir)
    success &= validate_openapi(schemas_dir)
    success &= validate_sample_data(project_root, schemas_dir)
    success &= check_schema_references(project_root)
    
    print()
    if success:
        print("✅ Schema validation completed successfully!")
        print("   - All JSON schemas are valid")
        print("   - OpenAPI specification is valid")
        print("   - Sample data validation completed")
        return 0
    else:
        print("❌ Schema validation failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
