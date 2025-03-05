import json
from fhirclient import client
from fhirclient.models.patient import Patient
from fhirclient.models.humanname import HumanName
from fhirclient.models.address import Address
from fhirclient.models.contactpoint import ContactPoint
from fhirclient.models.extension import Extension
from fhirclient.models.quantity import Quantity
from fhirclient.models.condition import Condition
from fhirclient.models.immunization import Immunization
from fhirclient.models.procedure import Procedure
from fhirclient.models.medicationstatement import MedicationStatement
from fhirclient.models.codeableconcept import CodeableConcept
from fhirclient.models.coding import Coding
from fhirclient.models.fhirreference import FHIRReference
from fhirclient.models.fhirdate import FHIRDate
from fhirclient.models.fhirdatetime import FHIRDateTime
from fhirclient.models.dosage import Dosage
from fhirclient.models.timing import Timing, TimingRepeat
from fhirclient.models.observation import Observation, ObservationReferenceRange


# -----------------------------
# Configuration for FHIR client
# -----------------------------

settings = {
    'app_id': 'chatbot',  # Replace with your app ID
    'api_base': 'http://localhost:8080/fhir'  # Replace with your FHIR server base URL
}

# Initialize FHIR client
smart = client.FHIRClient(settings=settings)

def create_patient():
    # -----------------------------
    # 1. Basic Patient Information
    # -----------------------------

    # Create a new Patient instance
    patient = Patient()

    # Name
    name = HumanName()
    name.given = ['Rodrigo']          # First name
    name.family = 'Agag'          # Last name
    patient.name = [name]

    # Email
    email_contact = ContactPoint()
    email_contact.system = 'email'
    email_contact.value = 'agagrodrigo@gmail.com'
    patient.telecom = [email_contact]

    # Phone Number
    phone_contact = ContactPoint()
    phone_contact.system = 'phone'
    phone_contact.value = '+44 7900 964443'
    patient.telecom.append(phone_contact)

    # Address
    address = Address()
    address.line = ['Via Arcangelo Corelli 3']  # Street address
    address.city = 'Rome'                 # City
    address.state = 'Rome'                # State
    address.postalCode = '00185'            # Postal Code
    address.country = 'Italy'                # Country
    patient.address = [address]

    # Gender
    patient.gender = 'male'

    # Birth Date
    patient.birthDate = FHIRDate('2005-12-13')  # Correctly using FHIRDate

    # -----------------------------
    # 2. Physical Attributes
    # -----------------------------

    # Height Extension
    height_extension = Extension()
    height_extension.url = 'http://example.org/fhir/StructureDefinition/height'
    height_quantity = Quantity()
    height_quantity.value = 175  # Height value
    height_quantity.unit = 'cm'   # Height unit
    height_quantity.system = 'http://unitsofmeasure.org'
    height_quantity.code = 'cm'
    height_extension.valueQuantity = height_quantity
    patient.extension = [height_extension]

    # Weight Extension
    weight_extension = Extension()
    weight_extension.url = 'http://example.org/fhir/StructureDefinition/weight'
    weight_quantity = Quantity()
    weight_quantity.value = 60   # Weight value
    weight_quantity.unit = 'kg'  # Weight unit
    weight_quantity.system = 'http://unitsofmeasure.org'
    weight_quantity.code = 'kg'
    weight_extension.valueQuantity = weight_quantity
    patient.extension.append(weight_extension)

    # -----------------------------
    # 3. Uploading Patient to FHIR Server
    # -----------------------------

    # Create the patient on the FHIR server
    try:
        created_patient = patient.create(smart.server)
        print(f"Raw response from create(): {created_patient}")

        # Determine if 'created_patient' is a dict or a Patient object
        if isinstance(created_patient, dict):
            patient_id = created_patient.get('id')
            if not patient_id:
                print("Error: Patient ID not found in the response.")
                return
        else:
            patient_id = created_patient.id

        print(f"Patient created with ID: {patient_id}")
    except Exception as e:
        print(f"Error creating patient: {e}")
        return

    # -----------------------------
    # 4. Adding Medical Information
    # -----------------------------

    # 4.1. Conditions
    conditions = [
        {
            'code': {
                'coding': [
                    {
                        'system': 'http://snomed.info/sct',
                        'code': '44054006',  # SNOMED code for Small penis syndrome
                        'display': 'Athsma'
                    }
                ]
            },
            'clinicalStatus': {
                'coding': [
                    {
                        'system': 'http://terminology.hl7.org/CodeSystem/condition-clinical',
                        'code': 'active',
                        'display': 'Active'
                    }
                ]
            },
            'verificationStatus': {
                'coding': [
                    {
                        'system': 'http://terminology.hl7.org/CodeSystem/condition-ver-status',
                        'code': 'confirmed',
                        'display': 'Confirmed'
                    }
                ]
            }
        },
        {
            'code': {
                'coding': [
                    {
                        'system': 'http://snomed.info/sct',
                        'code': '195967001',  # SNOMED code for Hayfever
                        'display': 'Hayfever'
                    }
                ]
            },
            'clinicalStatus': {
                'coding': [
                    {
                        'system': 'http://terminology.hl7.org/CodeSystem/condition-clinical',
                        'code': 'active',
                        'display': 'Active'
                    }
                ]
            },
            'verificationStatus': {
                'coding': [
                    {
                        'system': 'http://terminology.hl7.org/CodeSystem/condition-ver-status',
                        'code': 'confirmed',
                        'display': 'Confirmed'
                    }
                ]
            }
        }
    ]

    for cond in conditions:
        condition = Condition()
        
        # Setting the subject using FHIRReference
        condition.subject = FHIRReference()
        condition.subject.reference = f'Patient/{patient_id}'
        
        # Setting the code using CodeableConcept and Coding
        codeable_concept = CodeableConcept()
        coding = Coding()
        coding.system = cond['code']['coding'][0]['system']
        coding.code = cond['code']['coding'][0]['code']
        coding.display = cond['code']['coding'][0]['display']
        codeable_concept.coding = [coding]
        condition.code = codeable_concept
        
        # Setting clinicalStatus
        clinical_status = CodeableConcept()
        clinical_coding = Coding()
        clinical_coding.system = cond['clinicalStatus']['coding'][0]['system']
        clinical_coding.code = cond['clinicalStatus']['coding'][0]['code']
        clinical_coding.display = cond['clinicalStatus']['coding'][0]['display']
        clinical_status.coding = [clinical_coding]
        condition.clinicalStatus = clinical_status
        
        # Setting verificationStatus
        verification_status = CodeableConcept()
        verification_coding = Coding()
        verification_coding.system = cond['verificationStatus']['coding'][0]['system']
        verification_coding.code = cond['verificationStatus']['coding'][0]['code']
        verification_coding.display = cond['verificationStatus']['coding'][0]['display']
        verification_status.coding = [verification_coding]
        condition.verificationStatus = verification_status

        try:
            condition.create(smart.server)
            print(f"Condition '{cond['code']['coding'][0]['display']}' created.")
        except Exception as e:
            print(f"Error creating condition '{cond['code']['coding'][0]['display']}': {e}")

    # 4.2. Vaccines (Immunizations)
    immunizations = [
        {
            'vaccineCode': {
                'coding': [
                    {
                        'system': 'http://hl7.org/fhir/sid/cvx',
                        'code': '207',  # CVX code for Influenza
                        'display': 'Influenza'
                    }
                ]
            },
            'status': 'completed',
            'date': '2023-10-10'
        },
        {
            'vaccineCode': {
                'coding': [
                    {
                        'system': 'http://hl7.org/fhir/sid/cvx',
                        'code': '208',  # CVX code for Pneumococcal
                        'display': 'Pneumococcal'
                    }
                ]
            },
            'status': 'completed',
            'date': '2023-09-15'
        },
        {
            'vaccineCode': {
                'coding': [
                    {
                        'system': 'http://hl7.org/fhir/sid/cvx',
                        'code': '206',  # CVX code for Tetanus
                        'display': 'Tetanus'
                    }
                ]
            },
            'status': 'completed',
            'date': '2023-08-20'
        }
    ]

    for imm in immunizations:
        immunization = Immunization()
        
        # Setting the patient using FHIRReference
        immunization.patient = FHIRReference()
        immunization.patient.reference = f'Patient/{patient_id}'
        
        # Setting the vaccineCode using CodeableConcept and Coding
        vaccine_codeable_concept = CodeableConcept()
        vaccine_coding = Coding()
        vaccine_coding.system = imm['vaccineCode']['coding'][0]['system']
        vaccine_coding.code = imm['vaccineCode']['coding'][0]['code']
        vaccine_coding.display = imm['vaccineCode']['coding'][0]['display']
        vaccine_codeable_concept.coding = [vaccine_coding]
        immunization.vaccineCode = vaccine_codeable_concept
        
        # Setting status
        immunization.status = imm['status']
        
        # Setting date using FHIRDateTime
        immunization.occurrenceDateTime = FHIRDateTime(imm['date'])

        try:
            immunization.create(smart.server)
            print(f"Immunization '{imm['vaccineCode']['coding'][0]['display']}' created.")
        except Exception as e:
            print(f"Error creating immunization '{imm['vaccineCode']['coding'][0]['display']}': {e}")

    # 4.3. Past Procedures
    procedures = [
        {
            'code': {
                'coding': [
                    {
                        'system': 'http://snomed.info/sct',
                        'code': '80146002',  # SNOMED code for Appendectomy
                        'display': 'Elbow dislocation'
                    }
                ]
            },
            'status': 'completed',
            'date': '2022-05-20'
        },
        {
            'code': {
                'coding': [
                    {
                        'system': 'http://snomed.info/sct',
                        'code': '108252007',  # SNOMED code for Root canal surgery
                        'display': 'Root canal surgery'
                    }
                ]
            },
            'status': 'completed',
            'date': '2021-11-10'
        }
    ]

    for proc in procedures:
        procedure = Procedure()
        
        # Setting the subject using FHIRReference
        procedure.subject = FHIRReference()
        procedure.subject.reference = f'Patient/{patient_id}'
        
        # Setting the code using CodeableConcept and Coding
        procedure_codeable_concept = CodeableConcept()
        procedure_coding = Coding()
        procedure_coding.system = proc['code']['coding'][0]['system']
        procedure_coding.code = proc['code']['coding'][0]['code']
        procedure_coding.display = proc['code']['coding'][0]['display']
        procedure_codeable_concept.coding = [procedure_coding]
        procedure.code = procedure_codeable_concept
        
        # Setting status
        procedure.status = proc['status']
        
        # Setting performedDateTime using FHIRDateTime
        procedure.performedDateTime = FHIRDateTime(proc['date'])

        try:
            procedure.create(smart.server)
            print(f"Procedure '{proc['code']['coding'][0]['display']}' created.")
        except Exception as e:
            print(f"Error creating procedure '{proc['code']['coding'][0]['display']}': {e}")

    # 4.4. Current Medications
    medications = [
        {
            'medicationCodeableConcept': {
                'coding': [
                    {
                        'system': 'http://www.nlm.nih.gov/research/umls/rxnorm',
                        'code': '1049630',  # RxNorm code for Salbutamol
                        'display': 'Salbutamol'
                    }
                ]
            },
            'status': 'active',
            'effectiveDateTime': '2023-07-01',
            'dosage': {
                'text': '500mg twice a day',
                'timing': {
                    'repeat': {
                        'frequency': 2,
                        'period': 1,
                        'periodUnit': 'd'
                    }
                },
                'doseQuantity': {
                    'value': 500,
                    'unit': 'mg',
                    'system': 'http://unitsofmeasure.org',
                    'code': 'mg'
                }
            }
        },
        {
            'medicationCodeableConcept': {
                'coding': [
                    {
                        'system': 'http://www.nlm.nih.gov/research/umls/rxnorm',
                        'code': '860975',  # RxNorm code for Lisinopril
                        'display': 'Lisinopril'
                    }
                ]
            },
            'status': 'active',
            'effectiveDateTime': '2023-07-01',
            'dosage': {
                'text': '10mg once a day',
                'timing': {
                    'repeat': {
                        'frequency': 1,
                        'period': 1,
                        'periodUnit': 'd'
                    }
                },
                'doseQuantity': {
                    'value': 10,
                    'unit': 'mg',
                    'system': 'http://unitsofmeasure.org',
                    'code': 'mg'
                }
            }
        }
    ]

    for med in medications:
        medication_statement = MedicationStatement()
        
        # Set subject reference
        medication_statement.subject = FHIRReference()
        medication_statement.subject.reference = f'Patient/{patient_id}'
        
        # Set medication code
        medication_codeable_concept = CodeableConcept()
        medication_coding = Coding()
        medication_coding.system = med['medicationCodeableConcept']['coding'][0]['system']
        medication_coding.code = med['medicationCodeableConcept']['coding'][0]['code']
        medication_coding.display = med['medicationCodeableConcept']['coding'][0]['display']
        medication_codeable_concept.coding = [medication_coding]
        medication_statement.medicationCodeableConcept = medication_codeable_concept
        
        medication_statement.status = med['status']
        medication_statement.effectiveDateTime = FHIRDateTime(med['effectiveDateTime'])

        # Create dosage
        dosage = Dosage()
        dosage.text = med['dosage']['text']
        
        # Fix: Create proper TimingRepeat object
        timing = Timing()
        repeat = TimingRepeat()
        repeat.frequency = med['dosage']['timing']['repeat']['frequency']
        repeat.period = med['dosage']['timing']['repeat']['period']
        repeat.periodUnit = med['dosage']['timing']['repeat']['periodUnit']
        timing.repeat = repeat
        dosage.timing = timing
        
        # Set doseQuantity
        dose_quantity = Quantity()
        dose_quantity.value = med['dosage']['doseQuantity']['value']
        dose_quantity.unit = med['dosage']['doseQuantity']['unit']
        dose_quantity.system = med['dosage']['doseQuantity']['system']
        dose_quantity.code = med['dosage']['doseQuantity']['code']
        dosage.doseQuantity = dose_quantity
        
        medication_statement.dosage = [dosage]

        try:
            medication_statement.create(smart.server)
            print(f"Medication '{med['medicationCodeableConcept']['coding'][0]['display']}' created.")
        except Exception as e:
            print(f"Error creating medication '{med['medicationCodeableConcept']['coding'][0]['display']}': {e}")

    # 4.5. Blood Test Results (Laboratory Observations)
    blood_tests = [
        {
            'date': '2023-11-15',
            'category': 'Complete Blood Count (CBC)',
            'components': [
                {
                    'code': '718-7',
                    'display': 'Hemoglobin',
                    'value': 14.2,
                    'unit': 'g/dL',
                    'reference_range': '13.5-17.5',
                    'interpretation': 'normal'
                },
                {
                    'code': '789-8',
                    'display': 'Red Blood Cells',
                    'value': 4.8,
                    'unit': 'x10^12/L',
                    'reference_range': '4.5-5.9',
                    'interpretation': 'normal'
                },
                {
                    'code': '6690-2',
                    'display': 'White Blood Cells',
                    'value': 7.2,
                    'unit': 'x10^9/L',
                    'reference_range': '4.0-11.0',
                    'interpretation': 'normal'
                },
                {
                    'code': '777-3',
                    'display': 'Platelets',
                    'value': 250,
                    'unit': 'x10^9/L',
                    'reference_range': '150-450',
                    'interpretation': 'normal'
                }
            ]
        },
        {
            'date': '2023-11-15',
            'category': 'Comprehensive Metabolic Panel (CMP)',
            'components': [
                {
                    'code': '2345-7',
                    'display': 'Glucose',
                    'value': 95,
                    'unit': 'mg/dL',
                    'reference_range': '70-100',
                    'interpretation': 'normal'
                },
                {
                    'code': '2160-0',
                    'display': 'Creatinine',
                    'value': 0.9,
                    'unit': 'mg/dL',
                    'reference_range': '0.6-1.2',
                    'interpretation': 'normal'
                },
                {
                    'code': '3094-0',
                    'display': 'Blood Urea Nitrogen',
                    'value': 15,
                    'unit': 'mg/dL',
                    'reference_range': '7-20',
                    'interpretation': 'normal'
                },
                {
                    'code': '2093-3',
                    'display': 'Cholesterol',
                    'value': 180,
                    'unit': 'mg/dL',
                    'reference_range': '< 200',
                    'interpretation': 'normal'
                }
            ]
        },
        {
            'date': '2023-11-15',
            'category': 'Thyroid Function Tests',
            'components': [
                {
                    'code': '3016-3',
                    'display': 'TSH',
                    'value': 2.5,
                    'unit': 'mIU/L',
                    'reference_range': '0.4-4.0',
                    'interpretation': 'normal'
                },
                {
                    'code': '3026-2',
                    'display': 'T4 (Thyroxine)',
                    'value': 1.2,
                    'unit': 'ng/dL',
                    'reference_range': '0.8-1.8',
                    'interpretation': 'normal'
                },
                {
                    'code': '3051-0',
                    'display': 'T3 (Triiodothyronine)',
                    'value': 120,
                    'unit': 'ng/dL',
                    'reference_range': '80-200',
                    'interpretation': 'normal'
                }
            ]
        }
    ]

    for test in blood_tests:
        for component in test['components']:
            observation = Observation()
            
            # Set subject reference
            observation.subject = FHIRReference()
            observation.subject.reference = f'Patient/{patient_id}'
            
            # Set category
            category = CodeableConcept()
            category_coding = Coding()
            category_coding.system = 'http://terminology.hl7.org/CodeSystem/observation-category'
            category_coding.code = 'laboratory'
            category_coding.display = 'Laboratory'
            category.coding = [category_coding]
            category.text = test['category']
            observation.category = [category]
            
            # Set code (what is being measured)
            code = CodeableConcept()
            code_coding = Coding()
            code_coding.system = 'http://loinc.org'
            code_coding.code = component['code']
            code_coding.display = component['display']
            code.coding = [code_coding]
            observation.code = code
            
            # Set value
            value_quantity = Quantity()
            value_quantity.value = component['value']
            value_quantity.unit = component['unit']
            value_quantity.system = 'http://unitsofmeasure.org'
            value_quantity.code = component['unit']
            observation.valueQuantity = value_quantity
            
            # Set status
            observation.status = 'final'
            
            # Set effective date/time
            observation.effectiveDateTime = FHIRDateTime(test['date'])
            
            # Set reference range
            reference_range = ObservationReferenceRange()
            reference_range.text = component['reference_range']
            observation.referenceRange = [reference_range]
            
            # Set interpretation
            interpretation = CodeableConcept()
            interpretation_coding = Coding()
            interpretation_coding.system = 'http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation'
            interpretation_coding.code = component['interpretation']
            interpretation_coding.display = component['interpretation'].capitalize()
            interpretation.coding = [interpretation_coding]
            observation.interpretation = [interpretation]

            try:
                observation.create(smart.server)
                print(f"Blood test result '{component['display']}' created.")
            except Exception as e:
                print(f"Error creating blood test result '{component['display']}': {e}")

    print("All patient data uploaded successfully.")

if __name__ == "__main__":
    create_patient()