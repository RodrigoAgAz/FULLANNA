import json
from datetime import datetime, timedelta, timezone
from fhirclient import client
from fhirclient.models.patient import Patient
from fhirclient.models.observation import Observation, ObservationReferenceRange
from fhirclient.models.diagnosticreport import DiagnosticReport
from fhirclient.models.fhirdate import FHIRDate
from fhirclient.models.fhirdatetime import FHIRDateTime
from fhirclient.models.fhirinstant import FHIRInstant  # Correct import
from fhirclient.models.fhirreference import FHIRReference
from fhirclient.models.quantity import Quantity
from fhirclient.models.codeableconcept import CodeableConcept
from fhirclient.models.coding import Coding
from fhirclient.models.organization import Organization
from fhirclient.models.practitioner import Practitioner
from fhirclient.models.address import Address
from fhirclient.models.humanname import HumanName
from fhirclient.models.reference import Reference

# -----------------------------
# Configuration
# -----------------------------

settings = {
    'app_id': 'anna_test_results_uploader',
    'api_base': 'http://localhost:8080/fhir'  # Replace with your FHIR server URL
}

smart = client.FHIRClient(settings=settings)
PATIENT_ID = '48837'  # Replace with your actual Patient ID

# Test dates (most recent to oldest) with full datetime and timezone, without microseconds
TEST_DATES = {
    'recent': (datetime.now(timezone.utc) - timedelta(days=7)).replace(microsecond=0).isoformat(),
    'previous': (datetime.now(timezone.utc) - timedelta(days=180)).replace(microsecond=0).isoformat(),
    'baseline': (datetime.now(timezone.utc) - timedelta(days=365)).replace(microsecond=0).isoformat()
}

# -----------------------------
# Reference Data
# -----------------------------

LAB_INFO = {
    'name': 'Rome Medical Laboratory',
    'address': {
        'line': ['Via Roma 123'],
        'city': 'Rome',
        'country': 'Italy',
        'postalCode': '00184'
    },
    # 'id': 'lab001'  # Removed to let server assign ID
}

PRACTITIONER_INFO = {
    'name': {
        'given': ['Maria'],
        'family': 'Rossi'
    },
    # 'id': 'pract001',  # Removed to let server assign ID
    'qualification': 'MD Clinical Pathologist'
}

# -----------------------------
# Test Definitions
# -----------------------------

CBC_PANEL = {
    'hemoglobin': {
        'code': '718-7',
        'display': 'Hemoglobin [Mass/volume] in Blood',
        'unit': 'g/dL',
        'reference_range': {'low': 12.0, 'high': 15.5},
        'values': {'recent': 13.5, 'previous': 13.2, 'baseline': 13.8}
    },
    'wbc': {
        'code': '6690-2',
        'display': 'Leukocytes [#/volume] in Blood by Automated count',
        'unit': '10^3/uL',
        'reference_range': {'low': 4.5, 'high': 11.0},
        'values': {'recent': 6.8, 'previous': 7.2, 'baseline': 6.5}
    },
    'platelets': {
        'code': '777-3',
        'display': 'Platelets [#/volume] in Blood by Automated count',
        'unit': '10^3/uL',
        'reference_range': {'low': 150, 'high': 450},
        'values': {'recent': 250, 'previous': 265, 'baseline': 280}
    }
}

METABOLIC_PANEL = {
    'glucose': {
        'code': '2345-7',
        'display': 'Glucose [Mass/volume] in Blood',
        'unit': 'mg/dL',
        'reference_range': {'low': 70, 'high': 100},
        'values': {'recent': 90, 'previous': 88, 'baseline': 85}
    },
    'creatinine': {
        'code': '2160-0',
        'display': 'Creatinine [Mass/volume] in Serum or Plasma',
        'unit': 'mg/dL',
        'reference_range': {'low': 0.7, 'high': 1.3},
        'values': {'recent': 0.9, 'previous': 0.85, 'baseline': 0.88}
    },
    'potassium': {
        'code': '2823-3',
        'display': 'Potassium [Moles/volume] in Serum or Plasma',
        'unit': 'mmol/L',
        'reference_range': {'low': 3.5, 'high': 5.0},
        'values': {'recent': 4.2, 'previous': 4.0, 'baseline': 4.1}
    }
}

LIPID_PANEL = {
    'cholesterol': {
        'code': '2093-3',
        'display': 'Cholesterol [Mass/volume] in Serum or Plasma',
        'unit': 'mg/dL',
        'reference_range': {'low': 0, 'high': 200},
        'values': {'recent': 170, 'previous': 175, 'baseline': 180}
    },
    'triglycerides': {
        'code': '2571-8',
        'display': 'Triglycerides [Mass/volume] in Serum or Plasma',
        'unit': 'mg/dL',
        'reference_range': {'low': 0, 'high': 150},
        'values': {'recent': 120, 'previous': 130, 'baseline': 125}
    },
    'hdl': {
        'code': '2085-9',
        'display': 'HDL Cholesterol',
        'unit': 'mg/dL',
        'reference_range': {'low': 40, 'high': 60},
        'values': {'recent': 45, 'previous': 43, 'baseline': 44}
    }
}

# -----------------------------
# Helper Functions
# -----------------------------

def create_enhanced_observation(patient, test_info, test_date, test_type):
    """Create an enhanced Observation with more metadata."""
    observation = Observation()
    
    # Basic information
    observation.status = 'final'
    
    # Category
    category_coding = Coding()
    category_coding.system = "http://terminology.hl7.org/CodeSystem/observation-category"
    category_coding.code = "laboratory"
    
    category = CodeableConcept()
    category.coding = [category_coding]
    observation.category = [category]
    
    # Code
    code_coding = Coding()
    code_coding.system = "http://loinc.org"
    code_coding.code = test_info['code']
    code_coding.display = test_info['display']
    
    code = CodeableConcept()
    code.coding = [code_coding]
    observation.code = code
    
    # Subject (using FHIRReference)
    observation.subject = FHIRReference({'reference': f'Patient/{patient.id}'})
    
    # Effective date (using FHIRDateTime)
    observation.effectiveDateTime = FHIRDateTime(test_date)
    
    # Value (using Quantity)
    value_quantity = Quantity()
    value_quantity.value = test_info['values'][test_type]
    value_quantity.unit = test_info['unit']
    value_quantity.system = 'http://unitsofmeasure.org'
    value_quantity.code = test_info['unit']
    observation.valueQuantity = value_quantity
    
    # Reference ranges (using ObservationReferenceRange)
    reference_range = ObservationReferenceRange()
    
    low_quantity = Quantity()
    low_quantity.value = test_info['reference_range']['low']
    low_quantity.unit = test_info['unit']
    reference_range.low = low_quantity
    
    high_quantity = Quantity()
    high_quantity.value = test_info['reference_range']['high']
    high_quantity.unit = test_info['unit']
    reference_range.high = high_quantity
    
    observation.referenceRange = [reference_range]
    
    return observation

def create_enhanced_diagnostic_report(patient, observations, code, test_date, lab_org_id, practitioner_id):
    """Create an enhanced DiagnosticReport with more metadata."""
    report = DiagnosticReport()
    
    # Basic information
    report.status = 'final'
    
    # Category with proper CodeableConcept
    category_coding = Coding()
    category_coding.system = "http://terminology.hl7.org/CodeSystem/v2-0074"
    category_coding.code = "LAB"
    
    category = CodeableConcept()
    category.coding = [category_coding]
    report.category = [category]
    
    # Code with proper CodeableConcept
    code_coding = Coding()
    code_coding.system = "http://loinc.org"
    code_coding.code = code['coding'][0]['code']
    code_coding.display = code['coding'][0]['display']
    
    code_concept = CodeableConcept()
    code_concept.coding = [code_coding]
    report.code = code_concept
    
    # Subject and dates
    report.subject = FHIRReference({'reference': f'Patient/{patient.id}'})
    report.effectiveDateTime = FHIRDateTime(test_date)
    report.issued = FHIRInstant(test_date)  # Correct assignment
    
    # Results
    report.result = [FHIRReference({'reference': f'Observation/{obs.id}'}) for obs in observations]
    
    # Performer
    report.performer = [
        FHIRReference({'reference': f'Organization/{lab_org_id}'}),
        FHIRReference({'reference': f'Practitioner/{practitioner_id}'})
    ]
    
    # Conclusion
    report.conclusion = "All results within normal range."
    
    return report

def upload_test_series(patient, panel_data, panel_name, test_date, date_type, lab_org_id, practitioner_id):
    """Upload a series of tests as Observations and a DiagnosticReport."""
    try:
        observations = []
        for test_name, test_info in panel_data.items():
            try:
                observation = create_enhanced_observation(patient, test_info, test_date, test_type=date_type)
                observation_response = observation.create(smart.server)
                # Extracting the ID from the response
                if isinstance(observation_response, dict):
                    obs_id = observation_response.get('id')
                else:
                    obs_id = observation_response.id
                if not obs_id:
                    raise ValueError("No ID returned for Observation.")
                print(f"Uploaded {panel_name} Observation: {test_name} with ID {obs_id}")
                # Assign the ID back to the observation for referencing
                observation.id = obs_id
                observations.append(observation)
            except Exception as e:
                print(f"Error creating observation for {test_name}: {str(e)}")
                continue
        
        if observations:  # Only create report if we have observations
            # Define proper LOINC codes for panels
            panel_loinc_codes = {
                'CBC': '57021-8',        # Complete Blood Count
                'METABOLIC': '24323-8',  # Basic Metabolic Panel
                'LIPID': '5768-6'        # Lipid Panel
            }
            
            if panel_name not in panel_loinc_codes:
                print(f"Unknown panel name: {panel_name}. Skipping DiagnosticReport creation.")
                return
            
            # Create the code structure for the diagnostic report
            report_code = {
                'coding': [{
                    'system': 'http://loinc.org',
                    'code': panel_loinc_codes[panel_name],
                    'display': f'{panel_name} Panel Results'
                }]
            }
            
            report = create_enhanced_diagnostic_report(
                patient=patient,
                observations=observations,
                code=report_code,
                test_date=test_date,
                lab_org_id=lab_org_id,
                practitioner_id=practitioner_id
            )
            report_response = report.create(smart.server)
            # Extracting the ID from the response
            if isinstance(report_response, dict):
                report_id = report_response.get('id')
            else:
                report_id = report_response.id
            if not report_id:
                raise ValueError("No ID returned for DiagnosticReport.")
            print(f"Uploaded {panel_name} DiagnosticReport with ID {report_id}")
    except Exception as e:
        print(f"Error in upload_test_series for {panel_name}: {str(e)}")

def get_patient(patient_id):
    """Retrieve a patient by ID from the FHIR server."""
    try:
        patient = Patient.read(patient_id, smart.server)
        if patient:
            print(f"Found patient: {patient.id}")
            return patient
        else:
            print(f"No patient found with ID: {patient_id}")
            return None
    except Exception as e:
        print(f"Error retrieving patient: {str(e)}")
        return None

def create_or_get_organization():
    """Create lab organization if it doesn't exist, or get existing one."""
    try:
        # Search for existing organization by name
        search = Organization.where(struct={'name': LAB_INFO['name']})
        results = search.perform(smart.server)
        if results and results.entry:
            org = results.entry[0].resource
            print(f"Found existing lab organization: {org.id}")
            return org.id
        else:
            # Create new organization if it doesn't exist
            org = Organization()
            org.name = LAB_INFO['name']
            
            # Create proper Address object
            address = Address()
            address.line = [LAB_INFO['address']['line'][0]]
            address.city = LAB_INFO['address']['city']
            address.country = LAB_INFO['address']['country']
            address.postalCode = LAB_INFO['address']['postalCode']
            
            org.address = [address]  # Set as list of Address objects
            
            try:
                org_response = org.create(smart.server)
                if isinstance(org_response, dict):
                    org_id = org_response.get('id')
                else:
                    org_id = org_response.id
                if not org_id:
                    raise ValueError("No ID returned for Organization.")
                print(f"Created new lab organization with ID: {org_id}")
                return org_id
            except Exception as e:
                print(f"Error creating organization: {str(e)}")
                return None
    except Exception as e:
        print(f"Error searching for organization: {str(e)}")
        return None

def create_or_get_practitioner():
    """Create practitioner if doesn't exist, or get existing one."""
    try:
        # Search for existing practitioner by family name
        search = Practitioner.where(struct={'family': PRACTITIONER_INFO['name']['family']})
        results = search.perform(smart.server)
        if results and results.entry:
            # Further check for given name
            for entry in results.entry:
                pract = entry.resource
                given_names = pract.name[0].given
                if PRACTITIONER_INFO['name']['given'][0] in given_names:
                    print(f"Found existing practitioner: {pract.id}")
                    return pract.id
            # If no exact match, proceed to create
        # Create new practitioner if it doesn't exist
        pract = Practitioner()
        
        # Create proper HumanName object
        name = HumanName()
        name.given = PRACTITIONER_INFO['name']['given']
        name.family = PRACTITIONER_INFO['name']['family']
        
        pract.name = [name]  # Set as list of HumanName objects
        
        # Optionally, add qualifications if needed
        # Skipping qualifications for simplicity
        
        try:
            pract_response = pract.create(smart.server)
            if isinstance(pract_response, dict):
                pract_id = pract_response.get('id')
            else:
                pract_id = pract_response.id
            if not pract_id:
                raise ValueError("No ID returned for Practitioner.")
            print(f"Created new practitioner with ID: {pract_id}")
            return pract_id
        except Exception as e:
            print(f"Error creating practitioner: {str(e)}")
            return None
    except Exception as e:
        print(f"Error searching for practitioner: {str(e)}")
        return None

def main():
    """Main function to upload test results."""
    # Create or get Lab Organization
    lab_org_id = create_or_get_organization()
    if not lab_org_id:
        print("Failed to create or retrieve lab organization. Exiting.")
        return
    
    # Create or get Practitioner
    practitioner_id = create_or_get_practitioner()
    if not practitioner_id:
        print("Failed to create or retrieve practitioner. Exiting.")
        return
    
    # Get patient
    patient = get_patient(PATIENT_ID)
    if not patient:
        print("Patient retrieval failed. Exiting.")
        return
    
    # Upload each panel for each date
    for date_type, test_date in TEST_DATES.items():
        print(f"\nUploading {date_type} test results from {test_date}")
        upload_test_series(
            patient=patient,
            panel_data=CBC_PANEL,
            panel_name='CBC',
            test_date=test_date,
            date_type=date_type,
            lab_org_id=lab_org_id,
            practitioner_id=practitioner_id
        )
        upload_test_series(
            patient=patient,
            panel_data=METABOLIC_PANEL,
            panel_name='METABOLIC',
            test_date=test_date,
            date_type=date_type,
            lab_org_id=lab_org_id,
            practitioner_id=practitioner_id
        )
        upload_test_series(
            patient=patient,
            panel_data=LIPID_PANEL,
            panel_name='LIPID',
            test_date=test_date,
            date_type=date_type,
            lab_org_id=lab_org_id,
            practitioner_id=practitioner_id
        )

if __name__ == "__main__":
    main()