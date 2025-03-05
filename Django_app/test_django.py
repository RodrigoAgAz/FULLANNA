#!/usr/bin/env python
# Simple script to test Django configuration

import os
import sys
import django

def main():
    print(f"Python version: {sys.version}")
    print(f"Django version: {django.__version__}")
    
    # Check Django settings path
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'anna_project.settings')
    print(f"DJANGO_SETTINGS_MODULE: {os.environ.get('DJANGO_SETTINGS_MODULE')}")
    
    # Try to setup Django
    try:
        django.setup()
        print("Django setup successful!")
    except Exception as e:
        print(f"Django setup failed: {e}")
        return
    
    # Check installed apps
    try:
        from django.conf import settings
        print(f"Installed Apps: {settings.INSTALLED_APPS}")
    except Exception as e:
        print(f"Error getting settings: {e}")
    
    # Check URL configuration
    try:
        from django.urls import resolve, get_resolver
        print("URL patterns:")
        resolver = get_resolver()
        for pattern in resolver.url_patterns:
            print(f"  - {pattern}")
    except Exception as e:
        print(f"Error checking URLs: {e}")

if __name__ == "__main__":
    main()