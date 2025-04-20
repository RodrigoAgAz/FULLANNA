"""
response_formatter.py

This module provides consistent formatting for all ANNA's responses.
It ensures medical information is presented clearly, accurately, and with appropriate
structure and warnings.
"""

import logging
from typing import List, Dict, Any, Optional, Union

logger = logging.getLogger(__name__)

# Medical disclaimer to use consistently
STANDARD_DISCLAIMER = "This information is for educational purposes only and is not a substitute for professional medical advice."

# Emergency warning text
EMERGENCY_WARNING = "SEEK IMMEDIATE MEDICAL ATTENTION if you experience severe symptoms."

def format_medical_response(
    question: str,
    response_data: Dict[str, Any],
    include_brief_answer: bool = True,
    condition_info: Optional[Dict[str, Any]] = None
) -> List[str]:
    """
    Format a medical response with consistent structure.
    
    Args:
        question: The original user question
        response_data: Dictionary containing response components
        include_brief_answer: Whether to include a brief answer at the beginning
        condition_info: Optional condition-specific information
        
    Returns:
        List of formatted message strings
    """
    messages = []
    
    # 1. Direct brief answer if requested (Implementation #1)
    if include_brief_answer and "brief_answer" in response_data:
        messages.append(response_data["brief_answer"])
    
    # 2. Add detailed information with clear structure
    if "detailed_info" in response_data:
        # If no brief answer but we have details, start with a clean lead-in
        if not (include_brief_answer and "brief_answer" in response_data):
            if "intro" in response_data:
                messages.append(response_data["intro"])
                
        # Add detailed explanation
        if isinstance(response_data["detailed_info"], list):
            messages.extend(response_data["detailed_info"])
        else:
            messages.append(response_data["detailed_info"])
    
    # 3. Add emergency warnings when appropriate (Implementation #8)
    if "emergency_symptoms" in response_data and response_data["emergency_symptoms"]:
        messages.append("\nSEEK IMMEDIATE MEDICAL ATTENTION if you experience:")
        for symptom in response_data["emergency_symptoms"]:
            messages.append(f"• {symptom}")
    
    # 4. Add non-emergency "when to see doctor" guidance (Implementation #4)
    if "when_to_see_doctor" in response_data and response_data["when_to_see_doctor"]:
        messages.append("\nSEEK MEDICAL ADVICE if you experience:")
        for symptom in response_data["when_to_see_doctor"]:
            messages.append(f"• {symptom}")
    
    # 5. Add practical steps when available (Implementation #3)
    if "practical_steps" in response_data and response_data["practical_steps"]:
        messages.append("\nPRACTICAL STEPS:")
        for step in response_data["practical_steps"]:
            messages.append(f"• {step}")
    
    # 6. Add prevention information when relevant (Implementation #5)
    if "prevention" in response_data and response_data["prevention"]:
        messages.append("\nPREVENTION:")
        for measure in response_data["prevention"]:
            messages.append(f"• {measure}")
    
    # 7. Always include medical disclaimer (Implementation #8)
    messages.append(f"\n{STANDARD_DISCLAIMER}")
    
    return messages

def format_symptom_response(
    symptoms: str,
    severity: str,
    recommendations: List[str],
    when_to_seek_help: List[str],
    possible_causes: Optional[List[str]] = None,
    personalized_note: Optional[str] = None
) -> List[str]:
    """
    Format a response for symptom-related queries with safety warnings.
    
    Args:
        symptoms: Description of symptoms
        severity: Assessed severity level (EMERGENCY, HIGH, MEDIUM, LOW)
        recommendations: List of recommended actions
        when_to_seek_help: Warning signs to seek medical help
        possible_causes: Optional list of possible causes
        personalized_note: Optional personalized warning based on patient history
        
    Returns:
        List of formatted message strings
    """
    messages = []
    
    # Add personalized note at the top if provided
    if personalized_note:
        messages.append(personalized_note)
        messages.append("")  # Add a blank line for better readability
    
    # Severity-based formatting (Implementation #4)
    if severity == "EMERGENCY":
        messages.append("🚨 EMERGENCY: SEEK IMMEDIATE MEDICAL ATTENTION")
        messages.append("This may indicate a serious condition requiring immediate care.")
    elif severity == "HIGH":
        messages.append("⚠️ URGENT MEDICAL ATTENTION RECOMMENDED")
        messages.append("These symptoms may require prompt medical evaluation.")
    elif severity == "MEDIUM":
        messages.append("⚕️ MEDICAL ATTENTION ADVISED")
        messages.append("These symptoms should be evaluated by a healthcare provider.")
    else:  # LOW
        messages.append("ℹ️ GENERAL HEALTH INFORMATION")
        messages.append("These symptoms can often be managed with self-care, but monitor for changes.")
    
    # Add possible causes if provided
    if possible_causes and len(possible_causes) > 0:
        messages.append("\nPOSSIBLE CAUSES:")
        for cause in possible_causes:
            messages.append(f"• {cause}")
    
    # Add recommendations
    if recommendations and len(recommendations) > 0:
        messages.append("\nRECOMMENDATIONS:")
        for rec in recommendations:
            messages.append(f"• {rec}")
    
    # Add warning signs
    if when_to_seek_help and len(when_to_seek_help) > 0:
        messages.append("\nSEEK MEDICAL CARE IF YOU EXPERIENCE:")
        for sign in when_to_seek_help:
            messages.append(f"• {sign}")
    
    # Always include medical disclaimer
    messages.append(f"\n{STANDARD_DISCLAIMER}")
    
    return messages

def format_medical_info_response(
    topic: str,
    summary: str,
    details: Dict[str, Any],
    normal_values: Optional[Dict[str, Any]] = None
) -> List[str]:
    """
    Format a response for medical information queries with clear categories.
    
    Args:
        topic: The medical topic being explained
        summary: Brief summary of the topic
        details: Dictionary with detailed information categories
        normal_values: Optional dictionary with normal/abnormal range information
        
    Returns:
        List of formatted message strings
    """
    messages = []
    
    # Brief answer first (Implementation #1)
    messages.append(summary)
    
    # Add details by category with clear headings
    for category, info in details.items():
        if isinstance(info, list) and info:
            messages.append(f"\n{category.upper()}:")
            for item in info:
                messages.append(f"• {item}")
        elif isinstance(info, str) and info:
            messages.append(f"\n{category.upper()}:")
            messages.append(info)
    
    # Add normal vs. abnormal values when relevant (Implementation #9)
    if normal_values:
        messages.append("\nNORMAL RANGES:")
        for name, value_info in normal_values.items():
            normal_range = value_info.get("normal", "Not specified")
            messages.append(f"• {name}: {normal_range}")
            
            # Add abnormal context when available
            if "abnormal" in value_info:
                messages.append(f"  - {value_info['abnormal']}")
    
    # Always include medical disclaimer
    messages.append(f"\n{STANDARD_DISCLAIMER}")
    
    return messages

def format_condition_variants(
    condition: str,
    variants: Dict[str, Dict[str, Any]]
) -> List[str]:
    """
    Format information about condition variants with clear differentiation.
    
    Args:
        condition: The main condition name
        variants: Dictionary of variant types and their information
        
    Returns:
        List of formatted message strings
    """
    messages = []
    
    # Overview of condition
    messages.append(f"Different types of {condition}:")
    
    # Add each variant with consistent structure
    for variant_name, variant_info in variants.items():
        messages.append(f"\n{variant_name.upper()}:")
        
        # Add description
        if "description" in variant_info:
            messages.append(variant_info["description"])
        
        # Add symptoms
        if "symptoms" in variant_info and variant_info["symptoms"]:
            messages.append("Symptoms:")
            for symptom in variant_info["symptoms"]:
                messages.append(f"• {symptom}")
        
        # Add treatment
        if "treatment" in variant_info and variant_info["treatment"]:
            messages.append("Treatment:")
            for treatment in variant_info["treatment"]:
                messages.append(f"• {treatment}")
    
    # Always include medical disclaimer
    messages.append(f"\n{STANDARD_DISCLAIMER}")
    
    return messages