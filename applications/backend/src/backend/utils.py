# type: ignore
def minimal_schema(schema: dict) -> dict:
    """
    Reduce the OpenAPI schema to only include paths and methods.

    Args:
        schema (dict): The original OpenAPI schema.

    Returns:
        dict: The reduced OpenAPI schema with only essential endpoint information.

    Example output:
    {
        "endpoints": {
            "/generic/datetime": {
                "get": {
                    "method": "GET",
                    "summary": "Get Datetime",
                    "parameters": [
                        {
                            "name": "api_key",
                            "in": "query",
                            "required": true,
                            "type": "string",
                            "description": "API key for authentication"
                        }
                    ],
                    "response": {
                        "datetime": {
                            "type": "string",
                            "required": true,
                            "description": ""
                        }
                    }
                }
            }
        }
    }
    """
    minimal = {"endpoints": {}}

    # Extract paths from the OpenAPI schema
    paths = schema.get("paths", {})

    for path, methods in paths.items():
        minimal["endpoints"][path] = {}

        for method, details in methods.items():
            if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                endpoint_info = {
                    "method": method.upper(),
                    "summary": details.get("summary", ""),
                    "parameters": [],
                }

                # Extract parameters (excluding auth headers)
                parameters = details.get("parameters", [])
                for param in parameters:
                    param_name = param.get("name", "").lower()
                    # Skip authentication headers since they're global
                    if param_name in ["x-api-key", "authorization"]:
                        continue

                    param_info = {
                        "name": param.get("name"),
                        "in": param.get("in"),  # query, header, path
                        "required": param.get("required", False),
                        "type": param.get("schema", {}).get("type", "string"),
                        "description": param.get("description", ""),
                    }
                    endpoint_info["parameters"].append(param_info)

                # Extract request body info if present
                request_body = details.get("requestBody")
                if request_body:
                    content = request_body.get("content", {})
                    if "application/json" in content:
                        schema_ref = content["application/json"].get("schema")
                        endpoint_info["request_body"] = {
                            "required": request_body.get("required", False),
                            "content_type": "application/json",
                            "schema": _extract_schema_properties(schema_ref, schema),
                        }

                # Extract response info
                responses = details.get("responses", {})
                if "200" in responses:
                    response_content = responses["200"].get("content", {})
                    if "application/json" in response_content:
                        response_schema = response_content["application/json"].get(
                            "schema"
                        )
                        endpoint_info["response"] = _extract_schema_properties(
                            response_schema, schema
                        )

                minimal["endpoints"][path][method] = endpoint_info

    return minimal


def _extract_schema_properties(schema_ref: dict, full_schema: dict) -> dict:
    """
    Extract properties from a schema reference.

    Args:
        schema_ref: Schema reference or inline schema
        full_schema: Full OpenAPI schema for resolving $ref

    Returns:
        dict: Simplified schema properties
    """
    if not schema_ref:
        return {}

    # Handle $ref references
    if "$ref" in schema_ref:
        ref_path = schema_ref["$ref"]
        if ref_path.startswith("#/"):
            # Navigate to the referenced schema
            parts = ref_path[2:].split("/")
            current = full_schema
            for part in parts:
                current = current.get(part, {})
            schema_ref = current

    # Extract properties
    properties = schema_ref.get("properties", {})
    required = schema_ref.get("required", [])

    simplified = {}
    for prop_name, prop_details in properties.items():
        simplified[prop_name] = {
            "type": prop_details.get("type", "unknown"),
            "required": prop_name in required,
            "description": prop_details.get("description", ""),
        }

    return simplified
