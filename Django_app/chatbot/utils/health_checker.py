"""
Health Check System for ANNA
Monitors the health of all system components
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import httpx
from django.conf import settings
from django.http import JsonResponse

logger = logging.getLogger(__name__)

class HealthChecker:
    """Comprehensive health checking for all ANNA services"""
    
    def __init__(self):
        self.timeout = getattr(settings, 'HEALTH_CHECK_TIMEOUT', 10)
    
    async def check_all_services(self) -> Dict[str, Any]:
        """Check health of all services"""
        logger.info("Starting comprehensive health check")
        
        # Run all checks concurrently
        checks = await asyncio.gather(
            self._check_fhir(),
            self._check_redis(),
            self._check_openai(),
            self._check_medlineplus(),
            self._check_twilio(),
            self._check_email(),
            return_exceptions=True
        )
        
        # Map results
        services = ['fhir', 'redis', 'openai', 'medlineplus', 'twilio', 'email']
        results = {}
        
        for i, service in enumerate(services):
            if isinstance(checks[i], Exception):
                results[service] = {
                    'status': 'unhealthy',
                    'message': f'Health check failed: {str(checks[i])}'
                }
            else:
                results[service] = checks[i]
        
        # Calculate overall status
        healthy_count = sum(1 for r in results.values() if r['status'] == 'healthy')
        degraded_count = sum(1 for r in results.values() if r['status'] == 'degraded')
        unhealthy_count = sum(1 for r in results.values() if r['status'] == 'unhealthy')
        
        if unhealthy_count == 0 and degraded_count == 0:
            overall_status = 'healthy'
        elif unhealthy_count == 0:
            overall_status = 'degraded'
        else:
            overall_status = 'unhealthy'
        
        # Add summary
        results['summary'] = {
            'status': overall_status,
            'total_services': len(services),
            'healthy': healthy_count,
            'degraded': degraded_count,
            'unhealthy': unhealthy_count,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Health check completed: {overall_status} ({healthy_count}/{len(services)} healthy)")
        return results
    
    async def _check_fhir(self) -> Dict[str, Any]:
        """Check FHIR service health"""
        try:
            from ..views.services.fhir_service import FHIRService
            fhir_service = FHIRService()
            
            # Try a simple metadata request
            start_time = datetime.now()
            
            # Test with a simple Patient search with limit
            result = await fhir_service.search('Patient', {'_count': '1'})
            
            response_time = (datetime.now() - start_time).total_seconds()
            
            if result:
                return {
                    'status': 'healthy',
                    'message': 'FHIR service is accessible',
                    'response_time_ms': int(response_time * 1000),
                    'server_url': getattr(settings, 'FHIR_SERVER_URL', 'unknown')
                }
            else:
                return {
                    'status': 'degraded',
                    'message': 'FHIR service responded but returned no data',
                    'response_time_ms': int(response_time * 1000)
                }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'FHIR error: {str(e)}'
            }
    
    async def _check_redis(self) -> Dict[str, Any]:
        """Check Redis health"""
        try:
            from ..views.services.session import session_manager
            
            start_time = datetime.now()
            
            async with session_manager.get_redis() as redis:
                if redis:
                    await redis.ping()
                    response_time = (datetime.now() - start_time).total_seconds()
                    return {
                        'status': 'healthy',
                        'message': 'Redis is accessible',
                        'response_time_ms': int(response_time * 1000)
                    }
                else:
                    return {
                        'status': 'degraded',
                        'message': 'Redis unavailable, using in-memory fallback'
                    }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Redis error: {str(e)}'
            }
    
    async def _check_openai(self) -> Dict[str, Any]:
        """Check OpenAI API health"""
        try:
            from ..utils.openai_manager import openai_manager
            
            start_time = datetime.now()
            
            # Simple test request
            response = await openai_manager.chat_completion(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Say 'OK' if you can respond."}],
                max_tokens=5
            )
            
            response_time = (datetime.now() - start_time).total_seconds()
            
            if response and response.choices:
                return {
                    'status': 'healthy',
                    'message': 'OpenAI API is accessible',
                    'response_time_ms': int(response_time * 1000),
                    'model': 'gpt-4o-mini'
                }
            else:
                return {
                    'status': 'degraded',
                    'message': 'OpenAI API responded but with unexpected format'
                }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'OpenAI error: {str(e)}'
            }
    
    async def _check_medlineplus(self) -> Dict[str, Any]:
        """Check MedlinePlus API health"""
        try:
            start_time = datetime.now()
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    "https://connect.medlineplus.gov/service",
                    params={"mainSearchCriteria.v.c": "44054006"}  # Test with diabetes code
                )
                
                response_time = (datetime.now() - start_time).total_seconds()
                
                if response.status_code == 200:
                    return {
                        'status': 'healthy',
                        'message': f'MedlinePlus API accessible (HTTP {response.status_code})',
                        'response_time_ms': int(response_time * 1000)
                    }
                else:
                    return {
                        'status': 'degraded',
                        'message': f'MedlinePlus API returned HTTP {response.status_code}'
                    }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'MedlinePlus error: {str(e)}'
            }
    
    async def _check_twilio(self) -> Dict[str, Any]:
        """Check Twilio service health"""
        try:
            twilio_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
            twilio_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
            
            if not twilio_sid or not twilio_token:
                return {
                    'status': 'degraded',
                    'message': 'Twilio not configured - SMS notifications disabled'
                }
            
            # We can't easily test Twilio without sending a message,
            # so we'll just check if credentials are present
            from twilio.rest import Client
            client = Client(twilio_sid, twilio_token)
            
            # This will throw an exception if credentials are invalid
            # but we don't want to actually fetch account info in health check
            return {
                'status': 'healthy',
                'message': 'Twilio client initialized successfully',
                'phone_configured': bool(getattr(settings, 'TWILIO_PHONE_NUMBER', None))
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Twilio error: {str(e)}'
            }
    
    async def _check_email(self) -> Dict[str, Any]:
        """Check email service health"""
        try:
            from django.core.mail import get_connection
            
            # Check if email backend is configured
            connection = get_connection()
            
            # Just check if we can create a connection
            # We don't want to actually send test emails
            return {
                'status': 'healthy',
                'message': 'Email service configured',
                'backend': connection.__class__.__name__,
                'from_email_configured': bool(getattr(settings, 'DEFAULT_FROM_EMAIL', None))
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Email service error: {str(e)}'
            }
    
    async def check_service(self, service_name: str) -> Dict[str, Any]:
        """Check health of a specific service"""
        service_checks = {
            'fhir': self._check_fhir,
            'redis': self._check_redis,
            'openai': self._check_openai,
            'medlineplus': self._check_medlineplus,
            'twilio': self._check_twilio,
            'email': self._check_email
        }
        
        if service_name not in service_checks:
            return {
                'status': 'unhealthy',
                'message': f'Unknown service: {service_name}'
            }
        
        try:
            return await service_checks[service_name]()
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Health check failed: {str(e)}'
            }

# Global instance
health_checker = HealthChecker()

# Django view for health checks
async def health_check_view(request):
    """Django view for health checks"""
    service = request.GET.get('service')
    
    if service:
        # Check specific service
        result = await health_checker.check_service(service)
        status_code = 200 if result['status'] in ['healthy', 'degraded'] else 503
    else:
        # Check all services
        result = await health_checker.check_all_services()
        overall_status = result.get('summary', {}).get('status', 'unhealthy')
        status_code = 200 if overall_status in ['healthy', 'degraded'] else 503
    
    return JsonResponse(result, status=status_code)

# Convenience function
async def check_system_health() -> Dict[str, Any]:
    """Convenience function to check system health"""
    return await health_checker.check_all_services()