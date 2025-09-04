"""
Scalar API Documentation Views for Itqan CMS
"""
from django.http import HttpResponse
from django.views import View


class ScalarDocsView(View):
    """
    Serve Scalar API documentation interface
    Based on: https://scalar.com/
    """
    
    def get(self, request):
        # Use the static OpenAPI YAML file since it's more stable
        openapi_url = request.build_absolute_uri('/openapi.yaml')
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Itqan CMS API Documentation</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
        body {{
            margin: 0;
            padding: 0;
        }}
    </style>
</head>
<body>
    <script
        id="api-reference"
        data-url="{openapi_url}"
        data-configuration='{{"theme": "purple", "layout": "modern", "defaultHttpClient": {{"targetKey": "javascript", "clientKey": "fetch"}}}}'
    ></script>
    <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
</body>
</html>
        """
        
        return HttpResponse(html_content, content_type='text/html')


class ScalarAPIClientView(View):
    """
    Serve Scalar API Client interface (standalone API testing tool)
    """
    
    def get(self, request):
        # Use the static OpenAPI YAML file since it's more stable
        openapi_url = request.build_absolute_uri('/openapi.yaml')
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Itqan CMS API Client</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
        body {{
            margin: 0;
            padding: 0;
            height: 100vh;
        }}
    </style>
</head>
<body>
    <script
        id="api-client"
        type="application/json"
        data-configuration='{{"spec": {{"url": "{openapi_url}"}}}}'
    ></script>
    <script src="https://cdn.jsdelivr.net/npm/@scalar/api-client"></script>
</body>
</html>
        """
        
        return HttpResponse(html_content, content_type='text/html')