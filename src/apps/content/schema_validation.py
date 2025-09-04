"""
OpenAPI Schema Validation utilities
Ensures all API responses match OpenAPI specification exactly
"""
import json
import jsonschema
from django.conf import settings
from django.test import RequestFactory
from rest_framework.test import APIClient
from rest_framework import status
import yaml
import logging

logger = logging.getLogger(__name__)


class OpenAPIValidator:
    """
    Validates API responses against OpenAPI schema definitions
    """
    
    def __init__(self, openapi_spec_path=None):
        """Initialize validator with OpenAPI specification"""
        self.openapi_spec_path = openapi_spec_path or getattr(
            settings, 'OPENAPI_SPEC_PATH', 'openapi.yaml'
        )
        self.spec = self._load_openapi_spec()
        self.schemas = self._extract_schemas()
    
    def _load_openapi_spec(self):
        """Load and parse OpenAPI specification"""
        try:
            with open(self.openapi_spec_path, 'r', encoding='utf-8') as f:
                if self.openapi_spec_path.endswith('.yaml') or self.openapi_spec_path.endswith('.yml'):
                    return yaml.safe_load(f)
                else:
                    return json.load(f)
        except FileNotFoundError:
            logger.error(f"OpenAPI spec file not found: {self.openapi_spec_path}")
            return {}
        except Exception as e:
            logger.error(f"Failed to load OpenAPI spec: {e}")
            return {}
    
    def _extract_schemas(self):
        """Extract schema definitions from OpenAPI spec"""
        if not self.spec:
            return {}
        
        # OpenAPI 3.0 format
        return self.spec.get('components', {}).get('schemas', {})
    
    def validate_response_schema(self, response_data, schema_name):
        """
        Validate response data against a specific schema
        
        Args:
            response_data: The response data to validate
            schema_name: Name of the schema in OpenAPI spec
            
        Returns:
            tuple: (is_valid, errors)
        """
        if schema_name not in self.schemas:
            return False, [f"Schema '{schema_name}' not found in OpenAPI spec"]
        
        schema = self.schemas[schema_name]
        
        try:
            # Convert OpenAPI schema to JSON Schema format
            json_schema = self._convert_openapi_to_json_schema(schema)
            
            # Validate the response data
            jsonschema.validate(instance=response_data, schema=json_schema)
            return True, []
            
        except jsonschema.ValidationError as e:
            return False, [str(e)]
        except Exception as e:
            return False, [f"Validation error: {str(e)}"]
    
    def _convert_openapi_to_json_schema(self, openapi_schema):
        """
        Convert OpenAPI schema to JSON Schema format
        """
        # Basic conversion - this could be more sophisticated
        json_schema = openapi_schema.copy()
        
        # Handle OpenAPI-specific keywords
        if '$ref' in json_schema:
            # Resolve references
            ref = json_schema['$ref']
            if ref.startswith('#/components/schemas/'):
                schema_name = ref.split('/')[-1]
                if schema_name in self.schemas:
                    return self._convert_openapi_to_json_schema(self.schemas[schema_name])
        
        # Convert properties if they exist
        if 'properties' in json_schema:
            for prop_name, prop_schema in json_schema['properties'].items():
                json_schema['properties'][prop_name] = self._convert_openapi_to_json_schema(prop_schema)
        
        # Convert array items
        if 'items' in json_schema:
            json_schema['items'] = self._convert_openapi_to_json_schema(json_schema['items'])
        
        return json_schema
    
    def validate_api_endpoint(self, endpoint_path, method, response_data, status_code=200):
        """
        Validate an API endpoint response against OpenAPI spec
        
        Args:
            endpoint_path: The API endpoint path (e.g., '/assets/{id}')
            method: HTTP method (get, post, etc.)
            response_data: The actual response data
            status_code: HTTP status code
            
        Returns:
            tuple: (is_valid, errors)
        """
        if not self.spec or 'paths' not in self.spec:
            return False, ["No OpenAPI paths defined"]
        
        # Find the endpoint in the spec
        paths = self.spec['paths']
        
        # Look for exact match or parameterized match
        spec_path = None
        for path in paths:
            if path == endpoint_path:
                spec_path = path
                break
            # Check for parameterized paths like /assets/{id}
            if '{' in path and self._match_parameterized_path(endpoint_path, path):
                spec_path = path
                break
        
        if not spec_path:
            return False, [f"Endpoint '{endpoint_path}' not found in OpenAPI spec"]
        
        endpoint_spec = paths[spec_path]
        method_spec = endpoint_spec.get(method.lower())
        
        if not method_spec:
            return False, [f"Method '{method}' not defined for endpoint '{spec_path}'"]
        
        # Get response schema for the status code
        responses = method_spec.get('responses', {})
        status_str = str(status_code)
        
        if status_str not in responses:
            # Try default response
            if 'default' not in responses:
                return False, [f"Response {status_code} not defined for {method.upper()} {spec_path}"]
            response_spec = responses['default']
        else:
            response_spec = responses[status_str]
        
        # Get the response schema
        content = response_spec.get('content', {})
        if 'application/json' not in content:
            return True, []  # No JSON schema to validate
        
        json_content = content['application/json']
        schema = json_content.get('schema')
        
        if not schema:
            return True, []  # No schema defined
        
        # Validate against the schema
        try:
            json_schema = self._convert_openapi_to_json_schema(schema)
            jsonschema.validate(instance=response_data, schema=json_schema)
            return True, []
        except jsonschema.ValidationError as e:
            return False, [f"Schema validation failed: {str(e)}"]
        except Exception as e:
            return False, [f"Validation error: {str(e)}"]
    
    def _match_parameterized_path(self, actual_path, spec_path):
        """
        Check if an actual path matches a parameterized OpenAPI path
        
        Args:
            actual_path: e.g., '/assets/123'
            spec_path: e.g., '/assets/{id}'
        """
        actual_parts = actual_path.strip('/').split('/')
        spec_parts = spec_path.strip('/').split('/')
        
        if len(actual_parts) != len(spec_parts):
            return False
        
        for actual, spec in zip(actual_parts, spec_parts):
            if spec.startswith('{') and spec.endswith('}'):
                # Parameter placeholder - matches any value
                continue
            elif actual != spec:
                return False
        
        return True
    
    def validate_field_types(self, data, schema):
        """
        Validate that field types match schema expectations
        """
        errors = []
        
        if not isinstance(data, dict) or 'properties' not in schema:
            return errors
        
        properties = schema['properties']
        
        for field_name, field_value in data.items():
            if field_name not in properties:
                continue
            
            field_schema = properties[field_name]
            expected_type = field_schema.get('type')
            
            if expected_type == 'string' and not isinstance(field_value, str):
                if field_value is not None:  # Allow null for optional fields
                    errors.append(f"Field '{field_name}' should be string, got {type(field_value).__name__}")
            
            elif expected_type == 'integer' and not isinstance(field_value, int):
                if field_value is not None:
                    errors.append(f"Field '{field_name}' should be integer, got {type(field_value).__name__}")
            
            elif expected_type == 'boolean' and not isinstance(field_value, bool):
                if field_value is not None:
                    errors.append(f"Field '{field_name}' should be boolean, got {type(field_value).__name__}")
            
            elif expected_type == 'array' and not isinstance(field_value, list):
                if field_value is not None:
                    errors.append(f"Field '{field_name}' should be array, got {type(field_value).__name__}")
            
            elif expected_type == 'object' and not isinstance(field_value, dict):
                if field_value is not None:
                    errors.append(f"Field '{field_name}' should be object, got {type(field_value).__name__}")
        
        return errors


class APIResponseValidator:
    """
    Utility class for validating API responses in tests
    """
    
    def __init__(self):
        self.validator = OpenAPIValidator()
        self.client = APIClient()
    
    def validate_endpoint_response(self, endpoint_path, method='GET', auth_user=None, data=None):
        """
        Make API request and validate response against OpenAPI schema
        """
        if auth_user:
            self.client.force_authenticate(user=auth_user)
        
        # Make the API request
        if method.upper() == 'GET':
            response = self.client.get(endpoint_path)
        elif method.upper() == 'POST':
            response = self.client.post(endpoint_path, data=data, format='json')
        elif method.upper() == 'PUT':
            response = self.client.put(endpoint_path, data=data, format='json')
        elif method.upper() == 'DELETE':
            response = self.client.delete(endpoint_path)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        # Parse response data
        try:
            response_data = response.json() if hasattr(response, 'json') else response.data
        except:
            response_data = response.data
        
        # Validate against OpenAPI schema
        is_valid, errors = self.validator.validate_api_endpoint(
            endpoint_path, method, response_data, response.status_code
        )
        
        return {
            'is_valid': is_valid,
            'errors': errors,
            'status_code': response.status_code,
            'response_data': response_data
        }
    
    def run_comprehensive_validation(self):
        """
        Run validation against all major API endpoints
        """
        endpoints_to_test = [
            ('/assets', 'GET'),
            ('/licenses', 'GET'),
            ('/publishers', 'GET'),
        ]
        
        results = []
        
        for endpoint_path, method in endpoints_to_test:
            try:
                result = self.validate_endpoint_response(endpoint_path, method)
                result['endpoint'] = f"{method} {endpoint_path}"
                results.append(result)
                
                logger.info(f"Validated {method} {endpoint_path}: {'✅' if result['is_valid'] else '❌'}")
                
                if not result['is_valid']:
                    for error in result['errors']:
                        logger.error(f"  - {error}")
                        
            except Exception as e:
                logger.error(f"Failed to validate {method} {endpoint_path}: {e}")
                results.append({
                    'endpoint': f"{method} {endpoint_path}",
                    'is_valid': False,
                    'errors': [str(e)],
                    'status_code': None,
                    'response_data': None
                })
        
        return results


def validate_serializer_output(serializer_class, instance, schema_name):
    """
    Validate serializer output against OpenAPI schema
    """
    validator = OpenAPIValidator()
    
    # Serialize the instance
    if hasattr(serializer_class, 'from_asset_model'):
        # Custom serialization method
        serialized_data = serializer_class.from_asset_model(instance)
    elif hasattr(serializer_class, 'from_publishing_organization'):
        # Publisher serialization method
        serialized_data = serializer_class.from_publishing_organization(instance)
    elif hasattr(serializer_class, 'from_license_model'):
        # License serialization method
        serialized_data = serializer_class.from_license_model(instance)
    else:
        # Standard DRF serializer
        serializer = serializer_class(instance)
        serialized_data = serializer.data
    
    # Validate against schema
    is_valid, errors = validator.validate_response_schema(serialized_data, schema_name)
    
    return {
        'is_valid': is_valid,
        'errors': errors,
        'serialized_data': serialized_data
    }


def run_schema_validation_tests():
    """
    Run comprehensive schema validation tests
    """
    logger.info("🧪 Running OpenAPI Schema Validation Tests...")
    
    try:
        # Test API endpoints
        api_validator = APIResponseValidator()
        endpoint_results = api_validator.run_comprehensive_validation()
        
        # Test serializers with sample data
        from django.contrib.auth import get_user_model
        from .models import Asset, PublishingOrganization, License
        from .serializers import AssetSummarySerializer, PublisherSerializer, LicenseSummarySerializer
        
        User = get_user_model()
        
        serializer_results = []
        
        # Test Asset serialization
        asset = Asset.objects.first()
        if asset:
            result = validate_serializer_output(AssetSummarySerializer, asset, 'AssetSummary')
            result['serializer'] = 'AssetSummarySerializer'
            serializer_results.append(result)
        
        # Test Publisher serialization
        org = PublishingOrganization.objects.first()
        if org:
            result = validate_serializer_output(PublisherSerializer, org, 'Publisher')
            result['serializer'] = 'PublisherSerializer'
            serializer_results.append(result)
        
        # Test License serialization
        license_obj = License.objects.first()
        if license_obj:
            result = validate_serializer_output(LicenseSummarySerializer, license_obj, 'LicenseSummary')
            result['serializer'] = 'LicenseSummarySerializer'
            serializer_results.append(result)
        
        # Generate summary report
        total_tests = len(endpoint_results) + len(serializer_results)
        passed_tests = sum(1 for r in endpoint_results + serializer_results if r['is_valid'])
        
        logger.info(f"✅ Schema Validation Complete: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests < total_tests:
            logger.error("❌ Some schema validation tests failed:")
            for result in endpoint_results + serializer_results:
                if not result['is_valid']:
                    test_name = result.get('endpoint') or result.get('serializer')
                    logger.error(f"  - {test_name}: {result['errors']}")
        
        return {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'endpoint_results': endpoint_results,
            'serializer_results': serializer_results
        }
        
    except Exception as e:
        logger.error(f"Schema validation tests failed: {e}")
        return {
            'total_tests': 0,
            'passed_tests': 0,
            'endpoint_results': [],
            'serializer_results': [],
            'error': str(e)
        }
