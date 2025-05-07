"""
Configuration constants for API testing framework
"""

import os
from pathlib import Path

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Base directory for test files
TESTS_BASE_DIR = PROJECT_ROOT / 'tests'

# Application-specific configurations including valid environments and URLs
APPLICATIONS = {
    'users': {
        'description': 'User Management API',
        'environments': {
            'dev': 'http://127.0.0.1:5000',
            'staging': 'http://127.0.0.1:5000',
            'prod': 'http://127.0.0.1:5000'
        },
        'valid_environments': ['dev', 'staging', 'prod'],
        'base_path': TESTS_BASE_DIR / 'users'
    },
    'products': {
        'description': 'Product Catalog API',
        'environments': {
            'dev': 'http://localhost:3001',
            'staging': 'http://localhost:3001'
        },
        'valid_environments': ['dev', 'staging'],
        'base_path': TESTS_BASE_DIR / 'products'
    },
    'orders': {
        'description': 'Order Management API',
        'environments': {
            'dev': 'http://localhost:3002',
            'staging': 'http://localhost:3002',
            'prod': 'http://localhost:3002'
        },
        'valid_environments': ['dev', 'staging', 'prod'],
        'base_path': TESTS_BASE_DIR / 'orders'
    }
}

# Get all valid environments across all applications
VALID_ENVIRONMENTS = set()
for app_config in APPLICATIONS.values():
    VALID_ENVIRONMENTS.update(app_config['valid_environments'])
VALID_ENVIRONMENTS = list(VALID_ENVIRONMENTS)

# Get all valid folder paths
VALID_FOLDER_PATHS = set(app_config['base_path'] for app_config in APPLICATIONS.values())
